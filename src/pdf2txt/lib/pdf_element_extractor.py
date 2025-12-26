"""PDF 页面元素提取器

负责从 PDF 页面中提取所有元素（文本、图片、表格），并排序编号。
"""
from __future__ import annotations

from typing import Dict, List

from .pdf_text_extractor import extract_text_elements


def extract_image_elements(page, page_index: int) -> List[Dict]:
    """提取页面的图片元素。
    
    Args:
        page: pdfplumber Page 对象
        page_index: 页面索引
        
    Returns:
        图片元素列表
    """
    elements = []
    
    if hasattr(page, 'images'):
        for img_idx, img in enumerate(page.images):
            y_top = img.get('top', 0)
            x0 = img.get('x0', 0)
            elements.append({
                'type': 'image',
                'y': y_top,
                'x': x0,
                'data': {
                    'page_index': page_index,
                    'img_idx': img_idx,
                    'img': img
                }
            })
    
    return elements


def is_valid_table(table) -> bool:
    """判断表格是否为有效的表格。
    
    过滤规则：暂时不过滤无边框表格，接受所有能被提取数据的表格。
    
    Args:
        table: pdfplumber Table 对象
        
    Returns:
        bool: 如果能提取到数据返回True，否则返回False
    """
    # 检查表格是否能提取到有效数据
    try:
        table_data = table.extract()
        # 如果能提取到数据且至少有一行，认为是有效表格
        if table_data and len(table_data) > 0:
            return True
    except Exception:
        # 提取失败，认为不是有效表格
        pass
    
    return False


def extract_table_elements(tables, page_index: int) -> List[Dict]:
    """提取页面的表格元素。
    
    Args:
        tables: 表格列表
        page_index: 页面索引
        
    Returns:
        表格元素列表（已过滤误识别的表格）
    """
    elements = []
    
    if tables:
        for table_idx, table in enumerate(tables):
            # 过滤误识别的表格
            if not is_valid_table(table):
                continue
            
            y_top = table.bbox[1]  # top
            x0 = table.bbox[0]  # left
            elements.append({
                'type': 'table',
                'y': y_top,
                'x': x0,
                'data': {
                    'page_index': page_index,
                    'table_idx': table_idx,
                    'table': table
                }
            })
    
    return elements


def number_elements(elements: List[Dict]) -> None:
    """为图片和表格元素编号。
    
    Args:
        elements: 元素列表
    """
    img_counter = 1
    table_counter = 1
    for elem in elements:
        if elem['type'] == 'image':
            elem['data']['img_number'] = img_counter
            img_counter += 1
        elif elem['type'] == 'table':
            elem['data']['table_number'] = table_counter
            table_counter += 1


def extract_page_elements(page, page_index: int) -> List[Dict]:
    """提取页面的所有元素（文本、图片、表格）。
    
    Args:
        page: pdfplumber Page 对象
        page_index: 页面索引
        
    Returns:
        页面元素列表
    """
    page_elements = []
    
    # 先提取表格信息，过滤误识别的表格
    tables = page.find_tables()
    # 只使用有效表格的边界框来过滤文本（避免误识别表格区域的文本被跳过）
    valid_tables = [table for table in tables] if tables else []
    valid_table_bboxes = [table.bbox for table in valid_tables if is_valid_table(table)]
    
    # 提取文本行（跳过有效表格区域内的文本）
    page_elements.extend(extract_text_elements(page, page_index, valid_table_bboxes))
    
    # 提取图片信息
    page_elements.extend(extract_image_elements(page, page_index))
    
    # 提取表格信息（只提取有效表格）
    page_elements.extend(extract_table_elements(valid_tables, page_index))
    
    # 按 y 坐标排序（同一 y 按 x 排序）
    page_elements.sort(key=lambda e: (e['y'], e['x']))
    
    # 为每页的图片和表格重新编号
    number_elements(page_elements)
    
    return page_elements

