"""PDF 文件写入器

提供 PDF 文本行写入文件和兼容接口的功能。
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterator, Tuple

from utils.logger import get_logger
from ..main import TextLine
from .pdf_utils import is_page_number, is_in_bottom_region
from .text_cleaner import fix_double_char_repetition, fix_quadruple_char_repetition

logger = get_logger(__name__)


def write_lines_to_files(
    text_file: Path,
    metadata_file: Path | None,
    text_lines: Iterator[TextLine],
    index_file: Path | None = None,
    page_number_file: Path | None = None,
    coordinate_file: Path | None = None,
) -> Tuple[int, int, int, int]:
    """将文本行写入文件并统计数量。
    
    Args:
        text_file: 文本输出文件路径
        metadata_file: 元数据输出文件路径（可选）
        text_lines: 文本行迭代器
        index_file: 索引文件路径（可选，记录每行对应的页码）
        page_number_file: 页码文件路径（可选，记录页码信息，格式：索引序号|页码）
        coordinate_file: 坐标文件路径（可选，记录每行对应的坐标，格式：x0,top,x1,bottom）
        
    Returns:
        (text_count, metadata_count, image_count, table_count)
    """
    text_count = 0
    metadata_count = 0
    image_count = 0
    table_count = 0
    page_number_count = 0
    
    with open(text_file, 'w', encoding='utf-8') as tf:
        mf_handle = open(metadata_file, 'w', encoding='utf-8') if metadata_file else None
        idx_handle = open(index_file, 'w', encoding='utf-8') if index_file else None
        page_handle = open(page_number_file, 'w', encoding='utf-8') if page_number_file else None
        coord_handle = open(coordinate_file, 'w', encoding='utf-8') if coordinate_file else None
        try:
            for text_line in text_lines:
                # 检查是否为页码（仅对文本行进行检查，不包括图片和表格）
                is_page_num = False
                if not text_line.is_image and not text_line.is_table:
                    # 先检查文本内容是否为页码格式
                    if is_page_number(text_line.text):
                        # 检查是否有必要的坐标信息
                        if not text_line.pdf_anchor:
                            logger.debug(f"页码格式但缺少pdf_anchor: 文本='{text_line.text}'")
                        elif not text_line.pdf_anchor.page_height:
                            logger.debug(f"页码格式但缺少page_height: 文本='{text_line.text}'")
                        elif not text_line.pdf_anchor.bbox:
                            logger.debug(f"页码格式但缺少bbox: 文本='{text_line.text}'")
                        else:
                            # 再检查是否位于页面底部10%区域
                            if is_in_bottom_region(text_line, bottom_percent=0.1):
                                is_page_num = True
                
                if is_page_num:
                    # 页码：不写入主文本文件，写入页码文件
                    page_number_count += 1
                    if page_handle is not None:
                        # 获取实际页码（PDF页码从1开始）
                        if text_line.pdf_anchor:
                            actual_page = text_line.pdf_anchor.page_index + 1  # PDF 页码从 1 开始
                        else:
                            actual_page = 0
                        # 格式：实际页码|捕获页码，输出前去除所有空白以与识别逻辑一致
                        captured_page = re.sub(r'\s+', '', text_line.text.strip())
                        page_handle.write(f"{actual_page}|{captured_page}\n")
                    # 页码不写入索引文件和元数据文件
                    continue
                
                # 非页码内容：在写入前进行去重处理
                cleaned_text = text_line.text
                # 修复二字重复现象（AABB模式）
                cleaned_text = fix_double_char_repetition(cleaned_text)
                # 修复4字重复现象
                cleaned_text = fix_quadruple_char_repetition(cleaned_text)
                # 写入主文本文件
                tf.write(cleaned_text + '\n')
                text_count += 1
                
                # 写入索引文件（行号 -> 页码）
                if idx_handle is not None:
                    if text_line.pdf_anchor:
                        page = text_line.pdf_anchor.page_index + 1  # PDF 页码从 1 开始
                        idx_handle.write(f"{page}\n")
                    else:
                        idx_handle.write("0\n")  # 如果没有页码信息，写 0
                
                # 写入坐标文件（行号 -> 坐标）
                if coord_handle is not None:
                    if text_line.pdf_anchor and text_line.pdf_anchor.bbox:
                        bbox = text_line.pdf_anchor.bbox
                        coord_str = f"{round(bbox.x0, 2)},{round(bbox.top, 2)},{round(bbox.x1, 2)},{round(bbox.bottom, 2)}"
                        coord_handle.write(f"{coord_str}\n")
                    else:
                        coord_handle.write("0,0,0,0\n")  # 如果没有坐标信息，写 0,0,0,0
                
                # 统计图片/表格数量
                if text_line.is_image:
                    image_count += 1
                elif text_line.is_table:
                    table_count += 1
                
                # 写入元数据
                if mf_handle is not None:
                    parts = []
                    # 页号
                    if text_line.pdf_anchor:
                        page = text_line.pdf_anchor.page_index + 1
                        parts.append(str(page))
                    else:
                        parts.append('')
                    
                    # 页面尺寸（第二项）
                    if text_line.pdf_anchor and text_line.pdf_anchor.page_width and text_line.pdf_anchor.page_height:
                        page_size = f"{round(text_line.pdf_anchor.page_width, 2)},{round(text_line.pdf_anchor.page_height, 2)}"
                        parts.append(page_size)
                    else:
                        parts.append('')
                    
                    # 类型（文本/表格/图片）
                    if text_line.is_image:
                        parts.append('image')
                    elif text_line.is_table:
                        parts.append('table')
                    else:
                        parts.append('text')
                    
                    # 边界框
                    if text_line.pdf_anchor and text_line.pdf_anchor.bbox:
                        bbox = text_line.pdf_anchor.bbox
                        bbox_str = f"{round(bbox.x0, 2)},{round(bbox.top, 2)},{round(bbox.x1, 2)},{round(bbox.bottom, 2)}"
                        parts.append(bbox_str)
                    else:
                        parts.append('')
                    
                    # 字体信息（仅文本行）
                    if not text_line.is_table and not text_line.is_image:
                        if text_line.extras and 'fonts' in text_line.extras:
                            font_parts = []
                            for font in text_line.extras['fonts']:
                                font_str = f"{font['name']},{font['size']}"
                                font_parts.append(font_str)
                            if font_parts:
                                parts.append(';'.join(font_parts))
                            else:
                                parts.append('')
                        else:
                            parts.append('')
                    else:
                        parts.append('')
                    
                    mf_handle.write('|'.join(parts) + '\n')
                    metadata_count += 1
        finally:
            if mf_handle is not None:
                mf_handle.close()
            if idx_handle is not None:
                idx_handle.close()
            if page_handle is not None:
                page_handle.close()
            if coord_handle is not None:
                coord_handle.close()
    
    # 如果有页码，记录日志
    if page_number_count > 0:
        logger.info(f"过滤了 {page_number_count} 个页码")
    
    return text_count, metadata_count, image_count, table_count


def extract_images_from_lines(
    text_lines: Iterator[TextLine],
    output_dir: Path,
    debug: bool = False,
) -> int:
    """从文本行迭代器中提取图片。
    
    Args:
        text_lines: 文本行迭代器
        output_dir: 输出目录（将在此目录下创建 images 子目录）
        debug: 是否打印调试信息
        
    Returns:
        提取并保存的图片总数
    """
    total_images = 0
    for line in text_lines:
        if line.is_image:
            total_images += 1
    if debug and total_images > 0:
        logger.debug(f"总共提取了 {total_images} 张图片到 {output_dir / 'images'}")
    return total_images


def extract_tables_from_lines(
    text_lines: Iterator[TextLine],
    output_dir: Path,
    debug: bool = False,
) -> int:
    """从文本行迭代器中提取表格。
    
    Args:
        text_lines: 文本行迭代器
        output_dir: 输出目录（将在此目录下创建 tables 子目录）
        debug: 是否打印调试信息
        
    Returns:
        提取并保存的表格总数
    """
    total_tables = 0
    for line in text_lines:
        if line.is_table:
            total_tables += 1
    if debug and total_tables > 0:
        logger.debug(f"总共提取了 {total_tables} 个表格到 {output_dir / 'tables'}")
    return total_tables

