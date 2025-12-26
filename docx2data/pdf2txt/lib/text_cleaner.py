"""
文本清理工具模块
用于修复PDF提取过程中产生的文本错误
"""

import re
import unicodedata


def _is_valid_char(char: str) -> bool:
    """检查字符是否为有效的可处理字符（非空白、非控制字符）"""
    return not char.isspace() and unicodedata.category(char)[0] != 'C'


def _is_chinese_char(char: str) -> bool:
    """检查字符是否为中文字符（汉字）"""
    if not char:
        return False
    # CJK统一汉字范围：\u4e00-\u9fff
    # CJK扩展A范围：\u3400-\u4dbf
    code = ord(char)
    return (0x4e00 <= code <= 0x9fff) or (0x3400 <= code <= 0x4dbf)


def _is_chinese_symbol(char: str) -> bool:
    """检查字符是否为中文符号"""
    if not char:
        return False
    code = ord(char)
    # CJK符号和标点：\u3000-\u303f
    # 全角字符范围：\uff00-\uffef（包括全角标点、数字、字母等）
    return (0x3000 <= code <= 0x303f) or (0xff00 <= code <= 0xffef)


def _is_chinese_or_symbol(char: str) -> bool:
    """检查字符是否为中文字符或中文符号"""
    return _is_chinese_char(char) or _is_chinese_symbol(char)


def _is_aabb_pattern(text: str, i: int) -> tuple[bool, str, str]:
    """检查从位置i开始是否为AABB模式（仅针对中文），返回(是否匹配, char1, char2)"""
    if i + 3 >= len(text):
        return False, '', ''
    c1, c2 = text[i], text[i+2]
    if (text[i] == text[i+1] and text[i+2] == text[i+3] and 
        c1 != c2 and _is_chinese_char(c1) and _is_chinese_char(c2) and
        _is_valid_char(c1) and _is_valid_char(c2)):
        return True, c1, c2
    return False, '', ''


def _is_aa_pattern(text: str, i: int) -> tuple[bool, str]:
    """检查从位置i开始是否为AA模式（仅针对中文），返回(是否匹配, char)"""
    if (i + 1 >= len(text) or text[i] != text[i+1] or 
        not _is_chinese_char(text[i]) or not _is_valid_char(text[i])):
        return False, ''
    return True, text[i]


def _is_fully_repetition_pattern(text: str) -> bool:
    """
    检查整行是否完全由AABB和AA模式组成（仅针对中文部分）
    
    只检查中文部分是否完全符合AABBCCDD...模式。
    中文符号和非中文字符（如英文、数字、英文标点）会被跳过，不参与模式检测。
    如果中文部分完全符合AABBCCDD模式，返回True；否则返回False。
    
    Args:
        text: 待检查的文本
        
    Returns:
        bool: 如果中文部分完全由AABB和AA模式组成返回True，否则返回False
    """
    if not text or len(text) < 2:
        return False
    
    i = 0
    has_aabb = False
    has_chinese = False  # 标记是否有中文字符
    
    while i < len(text):
        # 跳过中文符号和非中文字符（允许存在，但不参与模式检测）
        if _is_chinese_symbol(text[i]) or not _is_chinese_char(text[i]):
            i += 1
            continue
        
        # 标记有中文字符
        has_chinese = True
        
        # 优先检查AABB模式
        is_aabb, _, _ = _is_aabb_pattern(text, i)
        if is_aabb:
            has_aabb = True
            i += 4
            continue
        # 检查AA模式
        is_aa, _ = _is_aa_pattern(text, i)
        if is_aa:
            i += 2
            continue
        # 如果遇到普通字符（非AABB也非AA的中文字符），说明不是完全由重复模式组成
        return False
    
    # 必须至少有一个AABB模式且有中文字符才认为是完全重复模式
    return has_aabb and has_chinese


def fix_double_char_repetition(text: str) -> str:
    """
    修复二字重复现象（AABB模式，仅针对中文）
    
    只检查中文部分是否完全符合AABBCCDD...模式。
    如果中文部分完全符合，则对中文部分去重；否则不去重。
    中文符号和非中文字符（如英文、数字、英文标点）会被保留，不参与去重检测。
    
    例如：
    - "高高兴兴" -> "高兴"（完全符合AABB）
    - "高高兴兴快快乐乐" -> "高兴快乐"（完全符合AABBCCDD）
    - "竞竞争争性性磋磋商商文文件件" -> "竞争性磋商文件"（完全符合AABBCCDDEEFF）
    - "采采购购计计划划编编号号::440101" -> "采购计划编号::440101"（中文部分完全符合，去重）
    - "竞竞争争性磋商文件" -> "竞竞争争性磋商文件"（不去重，中文部分不完全符合）
    - "竞争性磋磋商商文件" -> "竞争性磋磋商商文件"（不去重，中文部分不完全符合）
    - "看看" -> "看看"（不去重，没有AABB模式）
    - "高高兴兴，快快乐乐" -> "高兴，快乐"（中文符号保留）
    
    策略：
    1. 检查中文部分是否完全由AABB和AA模式组成（跳过中文符号和非中文字符）
    2. 如果完全符合，则处理中文部分：AABB->AB, AA->A（中文符号和非中文字符保持不变）
    3. 如果只是部分符合，则不处理
    
    Args:
        text: 待修复的文本
        
    Returns:
        修复后的文本
    """
    if not text or len(text) < 2:
        return text
    
    # 检查整行是否完全由AABB和AA模式组成
    if not _is_fully_repetition_pattern(text):
        return text
    
    # 处理文本：AABB->AB, AA->A（中文符号和非中文字符保持不变）
    result = []
    i = 0
    while i < len(text):
        # 中文符号和非中文字符保持不变
        if _is_chinese_symbol(text[i]) or not _is_chinese_char(text[i]):
            result.append(text[i])
            i += 1
            continue
        
        is_aabb, c1, c2 = _is_aabb_pattern(text, i)
        if is_aabb:
            result.append(c1)
            result.append(c2)
            i += 4
            continue
        is_aa, char = _is_aa_pattern(text, i)
        if is_aa:
            result.append(char)
            i += 2
            continue
        # 理论上不应该到这里，因为已经检查过中文部分完全符合模式
        result.append(text[i])
        i += 1
    
    return ''.join(result)


def _is_punctuation(char: str) -> bool:
    """检查字符是否为标点符号（中英文）"""
    if not char:
        return False
    # 使用Unicode类别判断
    category = unicodedata.category(char)
    # P* 类别表示所有标点符号
    if category.startswith('P'):
        return True
    # 检查常见的中文标点符号范围
    code = ord(char)
    # CJK符号和标点：\u3000-\u303f
    # 全角字符范围：\uff00-\uffef（包括全角标点）
    if (0x3000 <= code <= 0x303f) or (0xff00 <= code <= 0xffef):
        return True
    return False


def collapse_punctuation_repetition(text: str) -> str:
    """
    折叠连续出现的所有中英文标点符号
    
    将连续出现的相同标点符号压缩为单个符号。
    例如：
    - "::" -> ":"
    - "；；" -> "；"
    - "，，" -> "，"
    - "。。" -> "。"
    - "？？" -> "？"
    - "！！" -> "！"
    - "——" -> "—"
    - "（（" -> "（"
    - "））" -> "）"
    
    Args:
        text: 待处理的文本
        
    Returns:
        处理后的文本
    """
    if not text:
        return text
    
    result = []
    i = 0
    while i < len(text):
        char = text[i]
        if _is_punctuation(char):
            # 找到连续相同的标点符号
            result.append(char)
            i += 1
            # 跳过后续相同的标点符号
            while i < len(text) and text[i] == char and _is_punctuation(text[i]):
                i += 1
        else:
            result.append(char)
            i += 1
    
    return ''.join(result)


def fix_quadruple_char_repetition(text: str) -> str:
    """
    修复4字重复现象（每个字符重复4次）
    
    例如：
    - "湖湖湖湖北北北北城城城城" -> "湖北城"
    - "目目目目录录录录" -> "目录"
    - "金金金金山山山山大大大大道道道道" -> "金山大道"
    
    只修复明确的4字重复模式，避免误修复正常内容。
    策略：检测连续多个字符都是4字重复的情况，这是PDF提取错误的典型特征。
    
    Args:
        text: 待修复的文本
        
    Returns:
        修复后的文本
    """
    if not text or len(text) < 4:
        return text
    
    result = []
    i = 0
    while i < len(text):
        # 检查4字重复模式
        if i + 3 < len(text):
            char = text[i]
            if (char == text[i+1] == text[i+2] == text[i+3] and _is_valid_char(char)):
                result.append(char)
                i += 4
                continue
        result.append(text[i])
        i += 1
    
    return ''.join(result)

