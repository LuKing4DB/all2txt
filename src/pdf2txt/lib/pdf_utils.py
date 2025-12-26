"""PDF 处理工具函数

提供 PDF 文本处理的辅助函数。
"""
from __future__ import annotations

import ast
import re


def clean_font_name(font_name):
    """清理字体名，将bytes字面量字符串转换为实际字符串
    
    处理两种情况：
    1. 真实bytes对象: b'xxx'
    2. bytes字面量字符串: "b'xxx'"
    
    Args:
        font_name: 字体名字符串或bytes对象
        
    Returns:
        str: 清理后的字体名字符串
    """
    if not font_name:
        return ""
    
    # 如果已经是字符串但看起来像bytes字面量
    if isinstance(font_name, str) and (font_name.startswith("b'") or font_name.startswith('b"')):
        try:
            # 使用ast.literal_eval将字符串转换为实际bytes
            actual_bytes = ast.literal_eval(font_name)
            if isinstance(actual_bytes, bytes):
                # 尝试多种编码解码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                    try:
                        decoded = actual_bytes.decode(encoding)
                        return decoded
                    except:
                        continue
                # 如果都失败，返回hex表示
                return f"<hex:{actual_bytes.hex()}>"
        except:
            pass
    
    # 如果本身就是bytes对象
    if isinstance(font_name, bytes):
        for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
            try:
                decoded = font_name.decode(encoding)
                return decoded
            except:
                continue
        return f"<hex:{font_name.hex()}>"
    
    # 其他情况直接返回
    return font_name


def is_page_number(text):
    """
    判断文本是否为页码
    
    页码特征：
    - 单行文本
    - 主要是数字或罗马数字，可能包含少量文字（如"第1页"、"Page 1"、"Page I"等）
    - 通常较短（不超过20个字符）
    - 可能包含常见的页码关键词
    
    Args:
        text: 文本内容（可能包含空格，会去除首尾空白）
        
    Returns:
        bool: 如果是页码返回True，否则返回False
    """
    if not text:
        return False
    
    # 去除首尾空白并压缩所有空白，避免因空格导致识别失败
    text_clean = text.strip()
    text_compact = re.sub(r'\s+', '', text_clean)
    
    if len(text_compact) == 0 or len(text_compact) > 20:
        return False
    
    # 纯数字（1-9999之间的数字，常见页码范围）
    if re.match(r'^\d{1,4}$', text_compact):
        return True
    
    # 罗马数字模式（匹配常见的罗马数字，支持大小写）
    # 匹配：I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XIV, XV, XVI, XVII, XVIII, XIX, XX 等
    # 使用简化的罗马数字模式，匹配常见的页码范围（一般不超过XXX）
    roman_numeral_pattern = r'^[IVXLCDMivxlcdm]+$'
    if re.match(roman_numeral_pattern, text_compact):
        # 验证是否为有效的罗马数字格式（简单验证：只包含有效的罗马数字字符）
        # 这里不做严格的罗马数字有效性验证，因为页码中的罗马数字通常都是有效的
        if len(text_compact) <= 10:  # 页码中的罗马数字通常不会太长
            return True
    
    # 包含页码关键词的模式（支持阿拉伯数字和罗马数字）
    page_patterns = [
        r'^第\d+页$',  # 第1页
        r'^第\d+页/共\d+页$',  # 第1页/共10页
        r'^第[IVXLCDMivxlcdm]+页$',  # 第I页
        r'^-\s*第\d+页\s*-$',  # -第1页- 或 - 第1页 -
        r'^-\s*第[IVXLCDMivxlcdm]+页\s*-$',  # -第I页- 或 - 第I页 -
        r'^Page\s*\d+$',  # Page 1
        r'^Page\s*[IVXLCDMivxlcdm]+$',  # Page I
        r'^P\.?\s*\d+$',  # P.1 或 P 1
        r'^P\.?\s*[IVXLCDMivxlcdm]+$',  # P.I 或 P I
        r'^\d+/\d+$',  # 1/100
        r'^-\s*\d+\s*-$',  # - 1 -
        r'^-\s*[IVXLCDMivxlcdm]+\s*-$',  # - I -
        r'^\d+\s*/\s*\d+$',  # 1 / 100
        r'^[IVXLCDMivxlcdm]+\s*/\s*[IVXLCDMivxlcdm]+$',  # I / X
    ]
    
    for pattern in page_patterns:
        # 同时尝试原始空格和压缩空格后的形式
        if re.match(pattern, text_clean, re.IGNORECASE) or re.match(pattern, text_compact, re.IGNORECASE):
            return True
    
    # 检查是否主要是数字（数字占比超过70%）
    digit_count = sum(1 for c in text_compact if c.isdigit())
    if len(text_compact) > 0 and digit_count / len(text_compact) > 0.7:
        # 如果主要是数字且长度较短，可能是页码
        if len(text_compact) <= 10:
            return True
    
    # 检查是否主要是罗马数字字符（罗马数字字符占比超过70%）
    roman_chars = set('IVXLCDMivxlcdm')
    roman_count = sum(1 for c in text_compact if c in roman_chars)
    if len(text_compact) > 0 and roman_count / len(text_compact) > 0.7:
        # 如果主要是罗马数字字符且长度较短，可能是页码
        if len(text_compact) <= 10:
            return True
    
    return False


def is_in_bottom_region(text_line, bottom_percent: float = 0.1) -> bool:
    """
    检查文本行是否位于页面底部指定百分比区域内
    
    Args:
        text_line: TextLine 对象
        bottom_percent: 底部区域百分比（默认0.1，即底部10%）
        
    Returns:
        bool: 如果文本位于底部区域返回True，否则返回False
    """
    # 只对PDF文档进行检查
    if not text_line.pdf_anchor:
        return False
    
    # 需要页面高度和边界框信息
    if not text_line.pdf_anchor.page_height or not text_line.pdf_anchor.bbox:
        return False
    
    page_height = text_line.pdf_anchor.page_height
    bbox = text_line.pdf_anchor.bbox
    
    # pdfplumber坐标系说明：
    # 根据实际测试，pdfplumber使用的坐标系可能是：
    # - y=0在页面顶部
    # - y增大向下（向页面底部）
    # - top是文本行的上边缘（y坐标，从顶部开始计算）
    # - bottom是文本行的下边缘（y坐标，从顶部开始计算）
    # - top < bottom（因为top在上，bottom在下）
    # - 值越大，文本越靠下（离顶部越远）
    
    # 计算底部区域的阈值（底部10%区域：y >= page_height * 0.9）
    bottom_threshold = page_height * (1 - bottom_percent)
    
    # 使用文本行的bottom坐标（文本行的下边缘）来判断
    # 如果文本行的bottom在底部区域内（bottom >= bottom_threshold），则认为它在底部
    # 或者使用top坐标，如果top也在底部区域内
    text_bottom = bbox.bottom
    text_top = bbox.top
    
    # 检查文本是否在底部区域内
    # 如果文本的下边缘或上边缘在底部10%区域内，就认为它在底部
    # 使用bottom更准确，因为页码通常在页面最底部
    return text_bottom >= bottom_threshold

