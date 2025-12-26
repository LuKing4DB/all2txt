"""PDF 文本提取器

负责从 PDF 页面中提取文本，包括：
- 词聚类为行
- 字体信息提取
- 表格区域检测
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..main import BoundingBox, normalize_text
from .pdf_utils import clean_font_name


def cluster_words_to_lines(words: List[Dict]) -> List[List[Dict]]:
    """将词聚类为行（按 y 容差）。
    
    Args:
        words: 词列表
        
    Returns:
        行的列表，每行包含多个词
    """
    if not words:
        return []
    
    Y_TOL = 4.0  # 行聚类的 y 容差（像素），适当增加以处理数字和正文在同一行但y值略有差异的情况
    
    # 以 y 中线作为基准，按 y 再按 x 排序
    for w in words:
        w["y_mid"] = (w.get("top", 0.0) + w.get("bottom", 0.0)) / 2.0
    words.sort(key=lambda w: (w["y_mid"], w.get("x0", 0.0)))

    lines: List[List[Dict]] = []
    baselines: List[float] = []
    for w in words:
        y = w["y_mid"]
        if not lines:
            lines.append([w])
            baselines.append(y)
            continue
        # 找与现有 baseline 最近且在容差内的行
        idx = None
        min_d = 1e9
        for i, base in enumerate(baselines):
            d = abs(y - base)
            if d < min_d:
                min_d = d
                idx = i
        if idx is not None and min_d <= Y_TOL:
            lines[idx].append(w)
            # 更新该行基线为加权平均（更稳健）
            baselines[idx] = (baselines[idx] * 0.8) + (y * 0.2)
        else:
            lines.append([w])
            baselines.append(y)

    # 行内按 x0 排序
    for line in lines:
        line.sort(key=lambda t: t.get("x0", 0.0))
    return lines


def is_in_table(bbox: BoundingBox, table_bboxes: List[Tuple]) -> bool:
    """检查文本行是否在表格区域内"""
    for t_bbox in table_bboxes:
        tx0, ttop, tx1, tbottom = t_bbox
        # 检查是否有重叠
        if (bbox.x0 < tx1 and bbox.x1 > tx0 and 
            bbox.top < tbottom and bbox.bottom > ttop):
            return True
    return False


def index_chars_by_y(chars: List[Dict]) -> Dict[int, List[Dict]]:
    """将字符按y坐标索引，加速查找。
    
    Args:
        chars: 字符列表
        
    Returns:
        按y坐标索引的字符字典
    """
    chars_by_y = {}
    for char in chars:
        char_top = char.get('top', 0)
        # 使用y坐标的整数部分作为key，减少搜索范围
        y_key = int(char_top)
        if y_key not in chars_by_y:
            chars_by_y[y_key] = []
        chars_by_y[y_key].append(char)
    return chars_by_y


def extract_fonts_from_line(line_bbox: BoundingBox, chars_by_y: Dict[int, List[Dict]]) -> List[Dict]:
    """从字符中提取该行的字体信息。
    
    Args:
        line_bbox: 行的边界框
        chars_by_y: 按y坐标索引的字符字典
        
    Returns:
        字体信息列表
    """
    x0, top, x1, bottom = line_bbox.x0, line_bbox.top, line_bbox.x1, line_bbox.bottom
    
    # 从chars中提取该行的字体信息（使用预索引优化）
    line_chars = []
    # 只检查bbox范围内的y坐标
    for y_key in range(int(top), int(bottom) + 1):
        if y_key in chars_by_y:
            for c in chars_by_y[y_key]:
                if (c.get('x0', 0) < x1 and c.get('x1', 0) > x0 and
                    c.get('top', 0) < bottom and c.get('bottom', 0) > top):
                    line_chars.append(c)
    
    # 提取唯一的字体信息
    fonts_info = {}
    for char in line_chars:
        font_name = char.get("fontname", "")
        # 清理字体名（处理bytes字面量字符串）
        font_name = clean_font_name(font_name)
        
        font_size = char.get("size", 0.0)
        if font_name and font_size:
            key = (font_name, round(font_size, 2))
            fonts_info[key] = {"name": font_name, "size": round(float(font_size), 2)}
    
    return list(fonts_info.values())


def extract_text_elements(page, page_index: int, table_bboxes: List[Tuple]) -> List[Dict]:
    """提取页面的文本元素。
    
    Args:
        page: pdfplumber Page 对象
        page_index: 页面索引
        table_bboxes: 表格边界框列表
        
    Returns:
        文本元素列表
    """
    elements = []
    
    # 提取文本行（跳过表格区域内的文本）
    # 适当增加y_tolerance以处理数字和正文在同一行但y值略有差异的情况
    words = page.extract_words(x_tolerance=2, y_tolerance=5, keep_blank_chars=False)
    chars = page.chars
    
    # 预先将chars按y坐标索引，加速查找
    chars_by_y = index_chars_by_y(chars)
    
    if words:
        word_lines = cluster_words_to_lines(words)
        for ws in word_lines:
            text = normalize_text(" ".join(w.get("text", "") for w in ws))
            if not text:
                continue
                
            x0 = min(w.get("x0", 0.0) for w in ws)
            x1 = max(w.get("x1", 0.0) for w in ws)
            top = min(w.get("top", 0.0) for w in ws)
            bottom = max(w.get("bottom", 0.0) for w in ws)
            
            # 创建 bbox
            text_bbox = BoundingBox(x0, top, x1, bottom)
            
            # 跳过表格区域内的文本
            if is_in_table(text_bbox, table_bboxes):
                continue
            
            # 提取字体信息
            fonts = extract_fonts_from_line(text_bbox, chars_by_y)
            
            elements.append({
                'type': 'text',
                'y': top,
                'x': x0,
                'data': {
                    'text': text,
                    'bbox': text_bbox,
                    'page_index': page_index,
                    'fonts': fonts
                }
            })
    
    return elements

