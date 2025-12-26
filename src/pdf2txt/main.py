"""PDF 文档转换器：PDF → <文件名>.txt

专注于 PDF 文档的文本提取和转换。
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import time
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple



# ============================================================================
# 适配器基础类和数据结构（从 adapter_base 合并）
# ============================================================================

@dataclass(frozen=True)
class TextLine:
    """统一的"文本行/片段"模型，用于跨 PDF/DOCX/Excel 适配器传递。

    语义映射：
    - PDF: 由词聚类出的物理行；几何与页信息在 pdf_anchor 中体现。
    - DOCX: 段落/标题等逻辑块；位置用 docx_anchor 标注（节/段/运行范围）。
    - Excel: 单元格/表头文本；位置用 xlsx_anchor 标注（sheet/row/col/A1）。

    字段：
    - line_index: 文档级递增序号（或适配器内部生成的稳定序号）。
    - text: 规范化后的纯文本（例如合并多空格、去不换行空格）。
    - avg_font_size: 可选字号（适配器能提供时赋值）。
    - pdf_anchor/docx_anchor/xlsx_anchor: 对应格式的定位锚点（一般仅会设置其中一个）。
    - is_image: 是否为图片引用行
    - image_path: 图片相对路径（当 is_image=True 时有效）
    - is_table: 是否为表格引用行
    - table_path: 表格文件相对路径（当 is_table=True 时有效）
    - extras: 预留扩展
    """
    line_index: int  # 文档内的稳定顺序编号
    text: str        # 规范化纯文本
    avg_font_size: Optional[float] = None
    # 可选的格式特有锚点/属性（保持抽象层统一，具体适配器按需填充）
    pdf_anchor: Optional["PdfAnchor"] = None
    docx_anchor: Optional["DocxAnchor"] = None
    xlsx_anchor: Optional["XlsxAnchor"] = None
    is_image: bool = False  # 是否为图片引用行
    image_path: Optional[str] = None  # 图片相对路径
    is_table: bool = False  # 是否为表格引用行
    table_path: Optional[str] = None  # 表格文件相对路径
    extras: Optional[dict] = None  


@dataclass(frozen=True)
class BoundingBox:
    """轴对齐矩形（x0, top, x1, bottom）。

    - 不包含页号；页信息请在对应的锚点对象中提供（如 PdfAnchor.page_index）。
    - 坐标系由具体适配器定义：PDF 建议使用 pdfplumber 的页面坐标。
    - 仅当来源具备几何信息时才会赋值；对于 DOCX/Excel 通常不使用。
    """
    x0: float
    top: float
    x1: float
    bottom: float

@dataclass(frozen=True)
class PdfAnchor:
    """PDF 页级/对象级定位信息。坐标系为 PDF 页面坐标。"""
    page_index: int
    bbox: Optional[BoundingBox] = None
    object_ids: Optional[tuple[int, ...]] = None
    reading_order_id: Optional[int] = None
    page_width: Optional[float] = None
    page_height: Optional[float] = None


@dataclass(frozen=True)
class DocxAnchor:
    """DOCX 逻辑定位（无像素坐标）。索引推荐使用 0 基。"""
    section_index: int
    para_index: int
    run_start: int
    run_end: int
    style_name: Optional[str] = None
    heading_level: Optional[int] = None


@dataclass(frozen=True)
class XlsxAnchor:
    """Excel 单元格定位。row/col 通常为 1 基；A1 可作为冗余易读表示。"""
    sheet: str
    row: int
    col: int
    a1: Optional[str] = None


class DocumentAdapter(ABC):
    """文档适配器抽象基类：为不同来源（PDF/DOCX/Excel…）提供统一的行流接口。"""
    
    @abstractmethod
    def iter_lines(self) -> Iterator[TextLine]:
        """生成文档文本行迭代器。"""
        ...
    
    @abstractmethod
    def num_pages(self) -> int:
        """返回页数；无页概念的来源（DOCX/Excel）可返回 0。"""
        ...
    
    @abstractmethod
    def write_outputs(
        self,
        text_file: Path,
        metadata_file: Optional[Path] = None,
        *,
        extract_images: bool = True,
        extract_tables: bool = True,
        table_images: bool = False,
        debug: bool = False,
        index_file: Optional[Path] = None,
    ) -> Tuple[int, int, int, int, float, float, float]:
        """一次遍历完成文本与可选元数据输出，并按需同时导出图片与表格。
        
        Args:
            text_file: 文本输出文件路径
            metadata_file: 元数据输出文件路径（为 None 时不写出元数据）
            extract_images: 是否提取图片（某些格式有效）
            extract_tables: 是否提取表格（某些格式有效）
            table_images: 是否为表格保存截图（PNG）
            debug: 是否输出调试信息
            index_file: 索引文件路径（可选，记录每行对应的页码）
        
        Returns:
            (text_count, metadata_count, image_count, table_count, text_time, image_time, table_time)
        """
        ...


def normalize_text(text: str) -> str:
    """最小规范化（面向 CJK 的稳健清理）。

    - NFKC 规范化（全角/兼容字符归一）
    - 去除不换行空格与控制字符
    - 移除替代字符 U+FFFD
    - 修复二字重复现象（AABB模式，如"高高兴兴" -> "高兴"）
    - 折叠连续的冒号/分号（中英文）“::”“；；”
    - 修复4字重复现象（每个字符重复4次）
    - 只保留英文单词之间的空格，其他空格全部去除
    - 压缩多空格
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("\u00a0", " ")
    # 过滤控制类字符与 REPLACEMENT CHARACTER
    s = "".join(ch for ch in s if (unicodedata.category(ch)[0] != "C" and ch != "\ufffd"))
    
    # 修复二字重复现象（AABB模式，在处理空格之前，避免空格干扰检测）
    s = fix_double_char_repetition(s)
    
    # 修复4字重复现象（在处理空格之前，避免空格干扰检测）
    s = fix_quadruple_char_repetition(s)
    
    # 折叠连续出现的所有中英文标点符号（在修复重复字符之后，处理空格之前）
    # 处理因PDF加粗导致的标点重复问题，如"、、"、"：："等
    s = collapse_punctuation_repetition(s)
    
    # 只保留英文单词之间的空格
    # 策略：先在连续英文单词之间保留空格，然后将其他所有空格去除
    
    # 匹配连续的英文单词（字母+数字），并保护它们之间的空格
    english_pattern = re.compile(r'([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)*)')
    
    def replace_spaces(text):
        """将非英文文本中的空格全部去掉"""
        return re.sub(r'\s+', '', text)
    
    # 先用特殊标记保护英文单词及其内部空格
    protected_parts = []
    replacement_map = {}
    
    def protect_english(match):
        marker = f'__ENGLISH_{len(protected_parts)}__'
        protected_parts.append(match.group(0))
        replacement_map[marker] = match.group(0)
        return marker
    
    # 替换所有英文序列为标记
    s_protected = english_pattern.sub(protect_english, s)
    
    # 移除所有剩余空格
    s_no_spaces = replace_spaces(s_protected)
    
    # 恢复英文序列，保留其内部空格
    result = s_no_spaces
    for marker, original in replacement_map.items():
        result = result.replace(marker, original)
    
    return result


# ============================================================================
# PDF 转换器主逻辑
# ============================================================================

# 模块内导入（兼容包运行与脚本直接运行）
try:
    from .lib.pdf_parallel import process_pdf_parallel
    from .lib.pdf_writer import write_lines_to_files
    from .lib.pdf_precheck import precheck_and_fix_pdf
    from .lib.text_cleaner import (
        fix_quadruple_char_repetition,
        fix_double_char_repetition,
        collapse_punctuation_repetition,
    )
except Exception:  # 允许脚本直接运行时的相对导入失败
    import sys
    from pathlib import Path as _Path
    _CURRENT_DIR = _Path(__file__).resolve().parent
    _SRC_DIR = _CURRENT_DIR.parent  # src 目录
    # 将 src 目录添加到 sys.path，以便使用包路径导入
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))
    from pdf2txt.lib.pdf_parallel import process_pdf_parallel
    from pdf2txt.lib.pdf_writer import write_lines_to_files
    from pdf2txt.lib.pdf_precheck import precheck_and_fix_pdf
    from pdf2txt.lib.text_cleaner import (
        fix_quadruple_char_repetition,
        fix_double_char_repetition,
        collapse_punctuation_repetition,
    )

# 导入日志模块
try:
    from utils.logger import get_logger
except ImportError:
    # 如果直接运行脚本，可能需要添加路径
    import sys
    from pathlib import Path as _Path
    _CURRENT_DIR = _Path(__file__).resolve().parent
    _SRC_DIR = _CURRENT_DIR.parent  # src 目录
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))
    from utils.logger import get_logger

logger = get_logger(__name__)

def convert_pdf(
    file_path: str,
    output_dir: Path,
    extract_images: bool = False,
    extract_tables: bool = False,
    table_images: bool = False,
    export_metadata: bool = False,
    num_workers: int = 0,
    debug: bool = False
):
    """PDF 文档转换：失败自动回滚。
    
    Args:
        file_path: PDF 文件路径
        output_dir: 输出目录
        extract_images: 是否提取图片
        extract_tables: 是否提取表格
        table_images: 是否保存表格截图（PNG）
        export_metadata: 是否导出元数据（NDJSON格式，包含bbox和字体信息）
        num_workers: 并行处理的工作进程数（0=自动，1=串行）
        debug: 是否打印调试信息
    """
    # 验证文件类型
    path = Path(file_path)
    if path.suffix.lower() != '.pdf':
        raise ValueError(f"不支持的文件类型: {path.suffix}。仅支持 PDF 文件")
    
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 预检和自动修复 PDF（如果需要）
    actual_pdf_path, was_fixed = precheck_and_fix_pdf(
        file_path,
        auto_fix=True,
        timeout=10,
        debug=debug
    )
    
    if was_fixed:
        logger.info("已使用修复后的 PDF 文件进行处理")
    
    # 开始总计时
    total_start = time.time()
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="pdf2txt_"))
    
    try:
        if debug:
            logger.debug(f"临时目录: {temp_dir}")
        
        # 提取文本（和元数据，如果需要）
        text_start = time.time()
        text_file = temp_dir / 'text.txt'
        
        # 创建元数据文件（如果需要）
        metadata_file = (temp_dir / 'metadata_pdf.txt') if export_metadata else None
        
        # 创建索引文件（记录每行对应的页码）
        index_file = temp_dir / 'index.txt'
        
        # 创建坐标文件（记录每行对应的坐标）
        coordinate_file = temp_dir / 'coordinate.txt'
        
        # 并行处理 PDF（使用实际的文件路径，可能是修复后的文件）
        all_text_lines, image_count, table_count = process_pdf_parallel(
            actual_pdf_path,
            temp_dir,
            num_workers=num_workers,
            save_images=extract_images,
            save_tables=extract_tables,
            table_images=table_images,
            debug=debug,
        )
        
        # 生成页码文件路径
        page_number_file = temp_dir / 'text_page.txt'
        
        # 写入文本文件和元数据文件
        line_count, metadata_count, _, _ = write_lines_to_files(
            text_file,
            metadata_file,
            iter(all_text_lines),
            index_file=index_file,
            page_number_file=page_number_file,
            coordinate_file=coordinate_file,
        )
        
        text_time = time.time() - text_start
        
        if debug:
            if export_metadata:
                logger.debug(f"提取了 {line_count} 行文本和 {metadata_count} 行元数据")
            else:
                logger.debug(f"提取了 {line_count} 行文本")
        
        # 验证文件存在
        if not text_file.exists():
            raise RuntimeError("文本文件生成失败")
        
        # 原子性移动（成功后才替换）
        move_start = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用源文件名作为输出文件名
        source_stem = Path(file_path).stem
        output_text_file = output_dir / f'{source_stem}.txt'
        
        # 删除旧的输出目录内容
        if output_text_file.exists():
            output_text_file.unlink()
            if debug:
                logger.debug(f"删除旧文件: {output_text_file}")
        
        # 移动文本文件
        shutil.move(str(text_file), str(output_text_file))
        
        if debug:
            logger.debug(f"文件已移动到: {output_text_file}")
        
        # 移动索引文件
        if index_file.exists():
            source_stem = Path(file_path).stem
            output_index_file = output_dir / f'{source_stem}_index.txt'
            if output_index_file.exists():
                output_index_file.unlink()
                if debug:
                    logger.debug(f"删除旧索引文件: {output_index_file}")
            shutil.move(str(index_file), str(output_index_file))
            if debug:
                logger.debug(f"索引文件已移动到: {output_index_file}")
        
        # 移动页码文件（如果存在）
        if page_number_file.exists():
            source_stem = Path(file_path).stem
            output_page_file = output_dir / f'{source_stem}_page.txt'
            if output_page_file.exists():
                output_page_file.unlink()
                if debug:
                    logger.debug(f"删除旧页码文件: {output_page_file}")
            shutil.move(str(page_number_file), str(output_page_file))
            if debug:
                logger.debug(f"页码文件已移动到: {output_page_file}")
        
        # 移动坐标文件（如果存在）
        if coordinate_file.exists():
            source_stem = Path(file_path).stem
            output_coordinate_file = output_dir / f'{source_stem}_coordinate.txt'
            if output_coordinate_file.exists():
                output_coordinate_file.unlink()
                if debug:
                    logger.debug(f"删除旧坐标文件: {output_coordinate_file}")
            shutil.move(str(coordinate_file), str(output_coordinate_file))
            if debug:
                logger.debug(f"坐标文件已移动到: {output_coordinate_file}")
        
        # 移动图片目录（如果存在）
        temp_images_dir = temp_dir / 'images'
        if temp_images_dir.exists():
            output_images_dir = output_dir / 'images'
            if output_images_dir.exists():
                shutil.rmtree(output_images_dir)
                if debug:
                    logger.debug(f"删除旧图片目录: {output_images_dir}")
            shutil.move(str(temp_images_dir), str(output_images_dir))
            if debug:
                logger.debug(f"图片目录已移动到: {output_images_dir}")
        
        # 移动表格目录（如果存在）
        temp_tables_dir = temp_dir / 'tables'
        if temp_tables_dir.exists():
            output_tables_dir = output_dir / 'tables'
            if output_tables_dir.exists():
                shutil.rmtree(output_tables_dir)
                if debug:
                    logger.debug(f"删除旧表格目录: {output_tables_dir}")
            shutil.move(str(temp_tables_dir), str(output_tables_dir))
            if debug:
                logger.debug(f"表格目录已移动到: {output_tables_dir}")
        
        # 移动元数据文件（如果存在）
        if metadata_file and metadata_file.exists():
            output_metadata_file = output_dir / 'metadata_pdf.txt'
            if output_metadata_file.exists():
                output_metadata_file.unlink()
                if debug:
                    logger.debug(f"删除旧元数据文件: {output_metadata_file}")
            shutil.move(str(metadata_file), str(output_metadata_file))
            if debug:
                logger.debug(f"元数据文件已移动到: {output_metadata_file}")
        move_time = time.time() - move_start
        
        # 计算总时间
        total_time = time.time() - total_start
        
        # 输出成功信息（带时间统计）
        success_msg = f"转换成功: {line_count} 行文本"
        if image_count > 0:
            success_msg += f", {image_count} 张图片"
        if table_count > 0:
            success_msg += f", {table_count} 个表格"
        if metadata_count > 0:
            success_msg += f", {metadata_count} 行元数据"
        success_msg += f" -> {output_dir}"
        logger.info(success_msg)
        
        # 输出时间统计
        time_info = f"总耗时: {total_time:.2f}s ("
        time_parts = []
        if text_time > 0:
            if export_metadata:
                time_parts.append(f"文本+元数据: {text_time:.2f}s")
            else:
                time_parts.append(f"文本: {text_time:.2f}s")
        if move_time > 0:
            time_parts.append(f"移动: {move_time:.2f}s")
        
        time_info += ", ".join(time_parts) + ")"
        logger.info(time_info)
        
    except Exception as e:
        logger.error(f"转换失败: {e}", exc_info=True)
        raise
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            if debug:
                logger.debug(f"清理临时目录: {temp_dir}")
        
        # 注意：修复后的 PDF 文件（带 _fixed 后缀）会保留在原文件目录下，供后续使用
        if was_fixed and actual_pdf_path != file_path:
            if debug:
                logger.debug(f"修复后的 PDF 文件已保留: {actual_pdf_path}")


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(
        description="PDF 文档转换器：PDF → <文件名>.txt",
        epilog="""
示例：
  # 转换 PDF 文档（默认输出到以源文件名命名的文件夹）
  %(prog)s document.pdf
  # 输出: document/document.txt 和 document/document_index.txt
  
  # 指定输出目录
  %(prog)s document.pdf --out intermediate/doc001
  # 输出: intermediate/doc001/<文件名>.txt 和 intermediate/doc001/<文件名>_index.txt
  
  # 查看调试信息
  %(prog)s document.pdf --debug
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="PDF 文件路径")
    parser.add_argument("--out", help="输出目录（可选，默认输出到输入文件同级目录）")
    parser.add_argument("--images", action="store_true", help="提取图片（默认：不提取）")
    parser.add_argument("--tables", action="store_true", help="提取表格（默认：不提取）")
    parser.add_argument("--table-images", action="store_true", help="保存表格截图（PNG，默认：否）")
    parser.add_argument("--metadata", action="store_true", 
                        help="导出元数据到NDJSON（默认：不导出）")
    parser.add_argument("--workers", type=int, default=0,
                        help="并行处理的工作进程数（0=自动，1=串行，默认：0）")
    parser.add_argument("--debug", action="store_true", help="打印调试信息")
    
    args = parser.parse_args()
    
    file_path = Path(args.file)
    
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return 1
    
    # 验证文件类型
    if file_path.suffix.lower() != '.pdf':
        logger.error(f"不支持的文件类型: {file_path.suffix}。仅支持 PDF 文件")
        return 1
    
    # 如果没有指定输出目录，使用默认逻辑：输出到以源文件名命名的文件夹内
    if args.out:
        output_dir = Path(args.out)
        use_default_output = False
    else:
        # 默认输出到以源文件名命名的文件夹内
        input_dir = file_path.parent
        input_stem = file_path.stem  # 文件名（不含扩展名）
        output_dir = input_dir / input_stem  # 创建以源文件名命名的文件夹
        use_default_output = True
        output_text_file = output_dir / f"{input_stem}.txt"
        output_index_file = output_dir / f"{input_stem}_index.txt"
    
    try:
        if use_default_output:
            # 使用默认输出：先转换到临时目录，然后移动到最终位置并重命名
            temp_output_dir = Path(tempfile.mkdtemp(prefix="pdf2txt_"))
            try:
                convert_pdf(
                    str(file_path), 
                    temp_output_dir, 
                    extract_images=args.images,
                    extract_tables=args.tables,
                    table_images=args.table_images,
                    export_metadata=args.metadata,
                    num_workers=args.workers,
                    debug=args.debug
                )
                
                # 确保输出目录存在
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 移动并重命名文件（从临时目录的<文件名>.txt移动到最终位置）
                source_stem = file_path.stem
                temp_text_file = temp_output_dir / f'{source_stem}.txt'
                if temp_text_file.exists():
                    if output_text_file.exists():
                        output_text_file.unlink()
                    shutil.move(str(temp_text_file), str(output_text_file))
                    if args.debug:
                        logger.debug(f"文本文件已输出到: {output_text_file}")
                
                # 移动索引文件（从临时目录的<文件名>_index.txt移动到最终位置）
                temp_index_file = temp_output_dir / f'{source_stem}_index.txt'
                if temp_index_file.exists():
                    if output_index_file.exists():
                        output_index_file.unlink()
                    shutil.move(str(temp_index_file), str(output_index_file))
                    if args.debug:
                        logger.debug(f"索引文件已输出到: {output_index_file}")
                
                # 移动页码文件（如果存在）
                source_stem = file_path.stem
                if (temp_output_dir / f'{source_stem}_page.txt').exists():
                    output_page_file = output_dir / f"{source_stem}_page.txt"
                    if output_page_file.exists():
                        output_page_file.unlink()
                    shutil.move(str(temp_output_dir / f'{source_stem}_page.txt'), str(output_page_file))
                    if args.debug:
                        logger.debug(f"页码文件已输出到: {output_page_file}")
                
                # 移动坐标文件（如果存在）
                if (temp_output_dir / f'{source_stem}_coordinate.txt').exists():
                    output_coordinate_file = output_dir / f"{source_stem}_coordinate.txt"
                    if output_coordinate_file.exists():
                        output_coordinate_file.unlink()
                    shutil.move(str(temp_output_dir / f'{source_stem}_coordinate.txt'), str(output_coordinate_file))
                    if args.debug:
                        logger.debug(f"坐标文件已输出到: {output_coordinate_file}")
                
                # 移动其他文件（如果有）
                for item in temp_output_dir.iterdir():
                    if item.is_file() and item.name not in [f'{source_stem}.txt', f'{source_stem}_index.txt', f'{source_stem}_page.txt', f'{source_stem}_coordinate.txt']:
                        # 元数据文件等，移动到输出目录
                        shutil.move(str(item), str(output_dir / item.name))
                    elif item.is_dir():
                        # 图片、表格目录等，移动到输出目录
                        shutil.move(str(item), str(output_dir / item.name))
                
            finally:
                # 清理临时目录
                if temp_output_dir.exists():
                    shutil.rmtree(temp_output_dir)
        else:
            # 使用指定的输出目录
            convert_pdf(
                str(file_path), 
                output_dir, 
                extract_images=args.images,
                extract_tables=args.tables,
                table_images=args.table_images,
                export_metadata=args.metadata,
                num_workers=args.workers,
                debug=args.debug
            )
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"{e}")
        return 1
    except Exception as e:
        logger.error(f"转换失败: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

