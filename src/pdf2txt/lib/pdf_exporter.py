"""PDF 导出器

负责导出 PDF 页面元素（文本、图片、表格）为文件。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
import json

# 尝试导入 orjson（高性能JSON库），如果不可用则使用标准库json
try:
    import orjson
    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

from utils.logger import get_logger
from ..main import BoundingBox, PdfAnchor, TextLine

logger = get_logger(__name__)


def prepare_export_dirs(
    output_dir: Optional[Path],
    save_images: bool,
    save_tables: bool,
) -> Tuple[Optional[Path], Optional[Path]]:
    """准备导出目录。
    
    Args:
        output_dir: 输出根目录
        save_images: 是否保存图片
        save_tables: 是否保存表格
        
    Returns:
        (images_dir, tables_dir)
    """
    images_dir = None
    tables_dir = None
    
    if output_dir is not None:
        if save_images:
            images_dir = output_dir / 'images'
            images_dir.mkdir(parents=True, exist_ok=True)
        if save_tables:
            tables_dir = output_dir / 'tables'
            tables_dir.mkdir(parents=True, exist_ok=True)
    
    return images_dir, tables_dir


def create_text_line(data: Dict, line_idx: int, page_width: float = None, page_height: float = None) -> TextLine:
    """创建文本行的 TextLine 对象"""
    extras = {'fonts': data.get('fonts', [])} if data.get('fonts') else None
    return TextLine(
        line_index=line_idx,
        text=data['text'],
        avg_font_size=None,
        pdf_anchor=PdfAnchor(page_index=data['page_index'], bbox=data['bbox'], page_width=page_width, page_height=page_height),
        extras=extras,
    )


def create_image_line(data: Dict, line_idx: int, page_width: float = None, page_height: float = None) -> TextLine:
    """创建图片行的 TextLine 对象"""
    img_filename = f"page_{data['page_index'] + 1}_{data['img_number']}.png"
    img_rel_path = f"images/{img_filename}"
    
    img_obj = data['img']
    img_bbox = BoundingBox(
        float(img_obj.get('x0', 0)),
        float(img_obj.get('top', 0)),
        float(img_obj.get('x1', 0)),
        float(img_obj.get('bottom', 0))
    )
    
    # 使用与 DOCX 一致的占位符格式：{{image_page_index_序号}}
    # page_index 是 0-based，页码是 page_index + 1
    # img_number 是该页中的图片序号（从1开始）
    page_number = data['page_index'] + 1
    img_number = data['img_number']
    
    return TextLine(
        line_index=line_idx,
        text=f"{{{{image_{page_number}_{img_number}}}}}",
        avg_font_size=None,
        pdf_anchor=PdfAnchor(page_index=data['page_index'], bbox=img_bbox, page_width=page_width, page_height=page_height),
        is_image=True,
        image_path=img_rel_path,
    )


def create_table_line(data: Dict, line_idx: int, page_width: float = None, page_height: float = None) -> TextLine:
    """创建表格行的 TextLine 对象"""
    table_filename = f"page_{data['page_index'] + 1}_{data['table_number']}.json"
    table_rel_path = f"tables/{table_filename}"
    
    table_obj = data['table']
    table_bbox = BoundingBox(
        float(table_obj.bbox[0]),  # x0
        float(table_obj.bbox[1]),  # top
        float(table_obj.bbox[2]),  # x1
        float(table_obj.bbox[3])   # bottom
    )
    
    # 使用与 DOCX 一致的占位符格式：{{table_page_index_序号}}
    # page_index 是 0-based，页码是 page_index + 1
    # table_number 是该页中的表格序号（从1开始）
    page_number = data['page_index'] + 1
    table_number = data['table_number']
    
    return TextLine(
        line_index=line_idx,
        text=f"{{{{table_{page_number}_{table_number}}}}}",
        avg_font_size=None,
        pdf_anchor=PdfAnchor(page_index=data['page_index'], bbox=table_bbox, page_width=page_width, page_height=page_height),
        is_table=True,
        table_path=table_rel_path,
    )


def save_image(page, data: Dict, images_dir: Path, debug: bool = False) -> None:
    """保存图片到磁盘
    
    Args:
        page: pdfplumber Page 对象
        data: 图片数据字典
        images_dir: 图片输出目录
        debug: 是否输出调试信息
    """
    try:
        img_obj = data['img']
        bbox = (
            img_obj.get('x0', 0),
            img_obj.get('top', 0),
            img_obj.get('x1', 0),
            img_obj.get('bottom', 0),
        )
        cropped_page = page.crop(bbox)
        page_img = cropped_page.to_image(resolution=150)
        
        img_filename = f"page_{data['page_index'] + 1}_{data['img_number']}.png"
        page_img.save(images_dir / img_filename)
        
        if debug:
            logger.debug(f"提取图片: {img_filename}")
    except Exception as e:
        if debug:
            logger.warning(f"提取图片失败 (页 {data['page_index'] + 1}, 序号 {data.get('img_number')}): {e}")


def save_table_as_json(table, table_data: List[List], output_path: Path) -> None:
    """保存表格为 JSON 文件（简化格式）
    
    Args:
        table: pdfplumber Table 对象
        table_data: 提取的表格数据（二维数组）
        output_path: 输出文件路径
    """
    # 构建简化的 JSON 数据结构
    json_data = {
        "data": table_data,  # 二维数组：表格数据
        "rows": len(table_data),  # 行数
        "cols": len(table_data[0]) if table_data else 0  # 列数
    }
    
    # 保存为 JSON 文件（优先使用 orjson 高性能库，否则使用标准库json）
    if ORJSON_AVAILABLE:
        with open(output_path, 'wb') as f:
            f.write(orjson.dumps(json_data, option=orjson.OPT_INDENT_2))
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)


def crop_table_region(page, bbox: tuple, output_path: Path) -> None:
    """裁剪表格区域并保存为图片（MVP版本）
    
    Args:
        page: pdfplumber Page 对象
        bbox: 边界框 (x0, top, x1, bottom)
        output_path: 输出文件路径
    """
    x0, top, x1, bottom = bbox
    
    # 扩展边界（留点边距）
    margin = 5
    expanded_bbox = (
        max(0, x0 - margin),
        max(0, top - margin),
        min(page.width, x1 + margin),
        min(page.height, bottom + margin)
    )
    
    # 裁剪并保存
    cropped_page = page.crop(expanded_bbox)
    img = cropped_page.to_image(resolution=150)
    img.save(output_path)


def save_table(
    page,
    data: Dict,
    tables_dir: Path,
    table_images: bool = False,
    debug: bool = False,
) -> None:
    """保存表格到磁盘
    
    Args:
        page: pdfplumber Page 对象
        data: 表格数据字典
        tables_dir: 表格输出目录
        table_images: 是否保存表格截图
        debug: 是否输出调试信息
    """
    try:
        table_obj = data['table']
        table_data = table_obj.extract()
        if not table_data or len(table_data) == 0:
            return
        
        table_filename = f"page_{data['page_index'] + 1}_{data['table_number']}.json"
        json_path = tables_dir / table_filename
        save_table_as_json(table_obj, table_data, json_path)
        
        if table_images:
            png_path = tables_dir / table_filename.replace('.json', '.png')
            crop_table_region(page, table_obj.bbox, png_path)
        
        if debug:
            rows = len(table_data)
            cols = len(table_data[0]) if table_data else 0
            img_info = " (+PNG)" if table_images else ""
            logger.debug(f"提取表格: {table_filename[:-5]} ({rows}行×{cols}列){img_info}")
    except Exception as e:
        if debug:
            logger.warning(f"提取表格失败 (页 {data['page_index'] + 1}, 序号 {data.get('table_number')}): {e}")


def output_elements(
    elements: List[Dict],
    page,
    images_dir: Optional[Path],
    tables_dir: Optional[Path],
    save_images: bool,
    save_tables: bool,
    table_images: bool,
    debug: bool,
    start_line_idx: int,
) -> Iterator[TextLine]:
    """输出元素为 TextLine。
    
    Args:
        elements: 元素列表
        page: pdfplumber Page 对象
        images_dir: 图片输出目录
        tables_dir: 表格输出目录
        save_images: 是否保存图片
        save_tables: 是否保存表格
        table_images: 是否保存表格截图
        debug: 是否输出调试信息
        start_line_idx: 起始行索引
        
    Yields:
        TextLine 对象
    """
    # 获取页面尺寸
    page_width = page.width if hasattr(page, 'width') else None
    page_height = page.height if hasattr(page, 'height') else None
    
    for i, elem in enumerate(elements):
        line_idx = start_line_idx + i
        
        if elem['type'] == 'text':
            yield create_text_line(elem['data'], line_idx, page_width, page_height)
        
        elif elem['type'] == 'image':
            # 需要则保存图片
            if images_dir is not None and save_images:
                save_image(page, elem['data'], images_dir, debug)
            
            yield create_image_line(elem['data'], line_idx, page_width, page_height)
        
        elif elem['type'] == 'table':
            # 需要则保存表格数据与可选截图
            if tables_dir is not None and save_tables:
                save_table(page, elem['data'], tables_dir, table_images, debug)
            
            yield create_table_line(elem['data'], line_idx, page_width, page_height)

