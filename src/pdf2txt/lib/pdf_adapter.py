"""PDF 文档适配器

协调 PDF 转换的各个组件：
- 使用 pdf_element_extractor 提取页面元素
- 使用 pdf_exporter 导出元素
- 支持多进程并行处理
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pdfplumber

from ..main import DocumentAdapter, TextLine
from .pdf_element_extractor import extract_page_elements
from .pdf_exporter import (
    output_elements,
    prepare_export_dirs,
)
from .pdf_parallel import process_pdf_parallel
from .pdf_writer import (
    write_lines_to_files,
    extract_images_from_lines,
    extract_tables_from_lines,
)


@dataclass
class PdfAdapter(DocumentAdapter):
    """PDF 文档适配器，实现 DocumentAdapter 接口"""
    
    path: str
    
    # 运行期导出配置（由上层在遍历前可选设置）
    _export_output_dir: Optional[Path] = None
    _export_save_images: bool = False
    _export_save_tables: bool = False
    _export_table_images: bool = False
    _export_debug: bool = False
    
    # 页码范围（1-based，包含式）；None 表示不限制
    _page_start: Optional[int] = None
    _page_end: Optional[int] = None

    def set_export_options(
        self,
        *,
        output_dir: Optional[Path],
        save_images: bool = False,
        save_tables: bool = False,
        table_images: bool = False,
        debug: bool = False,
    ) -> None:
        """设置导出选项，使 iter_lines 在遍历过程中同步落盘图片/表格。

        说明：
        - 仅当设置了 output_dir 时才会执行保存；否则仅产出引用行。
        - save_images/save_tables 分别控制是否保存图片/表格工件。
        - table_images 控制是否额外保存表格截图 PNG。
        - debug 为 True 时打印导出明细。
        """
        self._export_output_dir = output_dir
        self._export_save_images = save_images
        self._export_save_tables = save_tables
        self._export_table_images = table_images
        self._export_debug = debug

    def set_page_range(self, start: Optional[int] = None, end: Optional[int] = None) -> None:
        """设置页码范围（1-based，包含式）。

        Args:
            start: 起始页（>=1），None 表示不限制起始
            end: 结束页（>=start），None 表示不限制结束

        注意：若仅设置 end 或 start，将被视为开放区间另一端无限制。
        """
        self._page_start = start if (start is None or start >= 1) else 1
        self._page_end = end if (end is None or (self._page_start is None or end >= self._page_start)) else end

    def iter_lines(self) -> Iterator[TextLine]:
        """单次遍历：产出文本/图片/表格引用行，并按需直接落盘图片与表格。

        算法要点：
        - 以词为粒度提取（pdfplumber.extract_words），按 y 容差聚类为行。
        - 跳过表格区域内的文本；字符级扫描统计该行字体集合。
        - 同页收集文本/图片/表格元素，按 (y,x) 排序后依次输出。
        - 若通过 set_export_options 配置了导出目录，则在输出图片/表格引用行前即时保存对应 PNG/JSON（以及可选表格截图）。

        备注：未实现列检测与连字符合并，可基于此继续增强。
        """
        global_line_idx = 0  # 全局行号计数器
        
        with pdfplumber.open(self.path) as pdf:
            for p_idx, page in enumerate(pdf.pages):
                page_no = p_idx + 1  # 1-based
                if self._should_skip_page(page_no):
                    continue
                
                # 提取页面所有元素
                page_elements = extract_page_elements(page, p_idx)
                
                # 准备输出目录（如需导出）
                images_dir, tables_dir = prepare_export_dirs(
                    self._export_output_dir,
                    self._export_save_images,
                    self._export_save_tables,
                )
                
                # 输出排序后的元素
                for text_line in output_elements(
                    page_elements,
                    page,
                    images_dir,
                    tables_dir,
                    self._export_save_images,
                    self._export_save_tables,
                    self._export_table_images,
                    self._export_debug,
                    global_line_idx,
                ):
                    yield text_line
                    global_line_idx += 1
    
    def _should_skip_page(self, page_no: int) -> bool:
        """判断是否应跳过该页"""
        if self._page_start is not None and page_no < self._page_start:
            return True
        if self._page_end is not None and page_no > self._page_end:
            return True
        return False

    def num_pages(self) -> int:
        """返回 PDF 页数"""
        with pdfplumber.open(self.path) as pdf:
            return len(pdf.pages)
    
    def write_outputs(
        self,
        text_file: Path,
        metadata_file: Optional[Path] = None,
        *,
        extract_images: bool = True,
        extract_tables: bool = True,
        table_images: bool = False,
        debug: bool = False,
        num_workers: int = 0,
        index_file: Optional[Path] = None,
    ) -> Tuple[int, int, int, int, float, float, float]:
        """一次遍历完成文本与可选元数据输出，并按需同时导出图片与表格。

        Args:
            text_file: 文本输出文件路径
            metadata_file: 元数据输出文件路径（为 None 时不写出元数据）
            extract_images: 是否提取图片（PDF 有效）
            extract_tables: 是否提取表格（PDF 有效）
            table_images: 是否为表格保存截图（PNG）
            debug: 是否输出调试信息
            num_workers: 并行处理的工作进程数（0=自动，1=串行）
            index_file: 索引文件路径（可选，记录每行对应的页码）

        Returns:
            (text_count, metadata_count, image_count, table_count, text_time, image_time, table_time)
        """
        import time
        
        base_dir = text_file.parent
        text_start = time.time()
        
        # 统一使用并行处理逻辑（num_workers=1 时为串行）
        all_text_lines, image_count, table_count = process_pdf_parallel(
            self.path,
            base_dir,
            num_workers=num_workers,
            save_images=extract_images,
            save_tables=extract_tables,
            table_images=table_images,
            debug=debug,
        )
        
        # 生成页码文件路径（基于文本文件路径，类似DOCX的处理方式）
        # 例如：text.txt -> text_page.txt
        # 确保父目录存在
        text_file.parent.mkdir(parents=True, exist_ok=True)
        page_number_file = text_file.parent / (text_file.stem + '_page.txt')
        
        # 写入文本文件和元数据文件
        text_count, metadata_count, _, _ = write_lines_to_files(
            text_file, metadata_file, iter(all_text_lines), index_file=index_file, page_number_file=page_number_file
        )
        
        text_time = time.time() - text_start
        image_time = 0.0
        table_time = 0.0

        return (
            text_count,
            metadata_count,
            image_count,
            table_count,
            text_time,
            image_time,
            table_time,
        )
    
    def extract_images(self, output_dir: Path, debug: bool = False) -> int:
        """兼容接口：复用 iter_lines 的单次遍历导出图片逻辑。

        Args:
            output_dir: 输出目录（将在此目录下创建 images 子目录）
            debug: 是否打印调试信息

        Returns:
            提取并保存的图片总数
        """
        self.set_export_options(
            output_dir=output_dir,
            save_images=True,
            save_tables=False,
            table_images=False,
            debug=debug,
        )
        return extract_images_from_lines(self.iter_lines(), output_dir, debug)
    
    def extract_tables(self, output_dir: Path, save_images: bool = False, debug: bool = False) -> int:
        """兼容接口：复用 iter_lines 的单次遍历导出表格逻辑。

        Args:
            output_dir: 输出目录（将在此目录下创建 tables 子目录）
            save_images: 是否保存表格区域截图（PNG）
            debug: 是否打印调试信息

        Returns:
            提取并保存的表格总数
        """
        self.set_export_options(
            output_dir=output_dir,
            save_images=False,
            save_tables=True,
            table_images=save_images,
            debug=debug,
        )
        return extract_tables_from_lines(self.iter_lines(), output_dir, debug)
