"""PDF 并行处理模块

提供多进程并行处理 PDF 页面的功能。
"""
from __future__ import annotations

import multiprocessing as mp
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pdfplumber

from utils.logger import get_logger
from ..main import TextLine
from .pdf_element_extractor import extract_page_elements
from .pdf_exporter import (
    output_elements,
    prepare_export_dirs,
)

logger = get_logger(__name__)


def _process_page_range_worker(args: Tuple) -> Dict[str, Any]:
    """工作进程：处理指定页码范围。
    
    Args:
        args: (pdf_path, page_start, page_end, output_dir_str, 
               save_images, save_tables, table_images, debug)
        
    Returns:
        包含处理结果的字典
    """
    (
        pdf_path,
        page_start,
        page_end,
        output_dir_str,
        save_images,
        save_tables,
        table_images,
        debug,
    ) = args
    
    # 转换回 Path 对象
    output_dir = Path(output_dir_str) if output_dir_str else None
    
    # 打开 PDF（每个进程独立打开）
    text_lines = []
    image_count = 0
    table_count = 0
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # 遍历指定页码范围
            for p_idx in range(page_start - 1, page_end):  # pdfplumber 使用 0-based
                if p_idx >= len(pdf.pages):
                    break
                    
                page = pdf.pages[p_idx]
                
                # 提取页面所有元素
                page_elements = extract_page_elements(page, p_idx)
                
                # 准备输出目录
                images_dir, tables_dir = prepare_export_dirs(
                    output_dir,
                    save_images,
                    save_tables,
                )
                
                # 输出排序后的元素（使用相对行号，后续重新编号）
                page_start_line_idx = len(text_lines)
                for text_line in output_elements(
                    page_elements,
                    page,
                    images_dir,
                    tables_dir,
                    save_images,
                    save_tables,
                    table_images,
                    debug,
                    page_start_line_idx,  # 使用相对行号
                ):
                    # 创建新的 TextLine，保持属性但更新行号
                    # 注意：行号将在主进程中重新编号
                    text_lines.append(text_line)
                    
                    # 统计图片/表格
                    if text_line.is_image:
                        image_count += 1
                    elif text_line.is_table:
                        table_count += 1
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'page_range': (page_start, page_end),
            'text_lines': [],
            'image_count': 0,
            'table_count': 0,
        }
    
    return {
        'success': True,
        'text_lines': text_lines,
        'image_count': image_count,
        'table_count': table_count,
        'page_range': (page_start, page_end),
    }


def process_pdf_parallel(
    pdf_path: str,
    output_dir: Path,
    num_workers: int = 0,
    save_images: bool = True,
    save_tables: bool = True,
    table_images: bool = False,
    debug: bool = False,
) -> Tuple[List[TextLine], int, int]:
    """并行处理 PDF 文档。
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        num_workers: 工作进程数（0 表示使用 CPU 核心数）
        save_images: 是否保存图片
        save_tables: 是否保存表格
        table_images: 是否保存表格截图
        debug: 是否输出调试信息
        
    Returns:
        (text_lines, image_count, table_count)
    """
    # 获取总页数
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
    
    if total_pages == 0:
        return [], 0, 0
    
    # 确定工作进程数
    if num_workers <= 0:
        num_workers = mp.cpu_count()
    
    # 避免过度并行（每进程至少处理 1 页）
    num_workers = min(num_workers, total_pages)
    
    # 计算每段页码范围
    pages_per_worker = (total_pages + num_workers - 1) // num_workers
    page_ranges = []
    
    for i in range(num_workers):
        start = i * pages_per_worker + 1  # 1-based
        end = min((i + 1) * pages_per_worker, total_pages)
        if start <= total_pages:
            page_ranges.append((start, end))
    
    if debug:
        logger.debug(f"并行处理: {total_pages} 页, {num_workers} 进程, 分段: {page_ranges}")
    
    # 准备任务参数（将 Path 转换为字符串以便 pickle）
    tasks = [
        (
            pdf_path,
            page_start,
            page_end,
            str(output_dir) if output_dir else None,
            save_images,
            save_tables,
            table_images,
            debug,
        )
        for page_start, page_end in page_ranges
    ]
    
    # 使用进程池并行处理
    start_time = time.time()
    with mp.Pool(processes=num_workers) as pool:
        results = pool.map(_process_page_range_worker, tasks)
    
    if debug:
        elapsed = time.time() - start_time
        logger.debug(f"并行处理完成，耗时: {elapsed:.2f}s")
    
    # 合并结果并按页顺序排序
    all_text_lines = []
    total_images = 0
    total_tables = 0
    global_line_idx = 0
    
    # 按页顺序合并结果
    for result in results:
        if not result['success']:
            if debug:
                logger.error(f"处理失败: {result.get('error', 'unknown')}")
            continue
        
        # 重新编号行号，确保全局唯一且连续
        for text_line in result['text_lines']:
            # 使用 replace 更新 line_index，避免重复所有字段
            new_line = replace(text_line, line_index=global_line_idx)
            all_text_lines.append(new_line)
            global_line_idx += 1
        
        total_images += result['image_count']
        total_tables += result['table_count']
    
    return all_text_lines, total_images, total_tables

