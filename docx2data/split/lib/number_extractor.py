"""
数字提取模块
从匹配的文本中提取数字序号（支持阿拉伯数字和中文数字）
"""

import re
from typing import Optional


# 中文数字映射表（按长度降序排列，便于匹配较长的数字）
CHINESE_NUMBERS = {
    # 九十到九十九
    '九十一': 91, '九十二': 92, '九十三': 93, '九十四': 94, '九十五': 95,
    '九十六': 96, '九十七': 97, '九十八': 98, '九十九': 99, '九十': 90,
    # 八十到八十九
    '八十一': 81, '八十二': 82, '八十三': 83, '八十四': 84, '八十五': 85,
    '八十六': 86, '八十七': 87, '八十八': 88, '八十九': 89, '八十': 80,
    # 七十到七十九
    '七十一': 71, '七十二': 72, '七十三': 73, '七十四': 74, '七十五': 75,
    '七十六': 76, '七十七': 77, '七十八': 78, '七十九': 79, '七十': 70,
    # 六十到六十九
    '六十一': 61, '六十二': 62, '六十三': 63, '六十四': 64, '六十五': 65,
    '六十六': 66, '六十七': 67, '六十八': 68, '六十九': 69, '六十': 60,
    # 五十到五十九
    '五十一': 51, '五十二': 52, '五十三': 53, '五十四': 54, '五十五': 55,
    '五十六': 56, '五十七': 57, '五十八': 58, '五十九': 59, '五十': 50,
    # 四十到四十九
    '四十一': 41, '四十二': 42, '四十三': 43, '四十四': 44, '四十五': 45,
    '四十六': 46, '四十七': 47, '四十八': 48, '四十九': 49, '四十': 40,
    # 三十一到三十九
    '三十一': 31, '三十二': 32, '三十三': 33, '三十四': 34, '三十五': 35,
    '三十六': 36, '三十七': 37, '三十八': 38, '三十九': 39, '三十': 30,
    # 二十一到二十九
    '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25,
    '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '二十': 20,
    # 十一到十九
    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
    '十六': 16, '十七': 17, '十八': 18, '十九': 19, '十': 10,
    # 一到九
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9,
}

# 按长度降序排列的中文数字列表，用于匹配
CHINESE_NUMBERS_SORTED = sorted(CHINESE_NUMBERS.keys(), key=len, reverse=True)


def _extract_arabic_number(text: str) -> Optional[int]:
    """
    从文本开头提取阿拉伯数字
    
    Args:
        text: 待提取的文本
    
    Returns:
        提取的数字，如果无法提取则返回 None
    """
    number_match = re.match(r'^(\d+)', text)
    if number_match:
        return int(number_match.group(1))
    return None


def _extract_chinese_number(text: str) -> Optional[int]:
    """
    从文本开头提取中文数字
    
    Args:
        text: 待提取的文本
    
    Returns:
        提取的数字，如果无法提取则返回 None
    """
    for chinese_num in CHINESE_NUMBERS_SORTED:
        if text.startswith(chinese_num):
            return CHINESE_NUMBERS[chinese_num]
    return None


def _extract_number_from_text(text: str) -> Optional[int]:
    """
    从文本中提取数字（优先阿拉伯数字，其次中文数字）
    
    Args:
        text: 待提取的文本
    
    Returns:
        提取的数字，如果无法提取则返回 None
    """
    # 优先尝试提取阿拉伯数字
    number = _extract_arabic_number(text)
    if number is not None:
        return number
    
    # 尝试提取中文数字
    return _extract_chinese_number(text)


def extract_number_from_match(matched_text: str) -> Optional[int]:
    """
    从匹配的文本中提取数字序号
    
    支持多种格式：
    - "第X章"、"第X节"、"第X条"、"第X项" 等（X可以是阿拉伯数字或中文数字）
    - "X."、"X、" 等（X在开头）
    - "一、"、"二、" 等（中文数字在开头）
    - "（一）"、"（二）" 等（中文数字在括号中）
    - "（1）"、"（2）" 等（阿拉伯数字在括号中）
    - 纯数字或纯中文数字
    
    Args:
        matched_text: 正则表达式匹配的文本，例如：
            - "1.招标条件"
            - "一、工程概况"
            - "（一）总则"
            - "（1）说明"
            - "第1章"
            - "第一章  招标公告"
            - "第一节 一般要求"
            - "第一条 总则"
            - "第一项 说明"
    
    Returns:
        提取的数字序号，如果无法提取则返回 None
    """
    if not matched_text:
        return None
    
    # 策略1: 尝试从文本开头提取数字（支持 "1."、"一、" 等格式）
    # 优先从开头提取，因为这是标题的主要格式
    number = _extract_number_from_text(matched_text)
    if number is not None:
        return number
    
    # 策略2: 尝试从括号格式中提取（支持 "（一）"、"（1）" 等格式）
    # 匹配中文括号或英文括号中的数字
    paren_pattern = r'[（(]([一二三四五六七八九十百千万\d]+)[）)]'
    paren_match = re.search(paren_pattern, matched_text)
    if paren_match:
        number_text = paren_match.group(1)
        number = _extract_number_from_text(number_text)
        if number is not None:
            return number
    
    # 策略3: 尝试从"第X..."格式中提取（支持章、节、条、项、部分、册等）
    # 匹配"第"和后续单位词之间的内容
    # 注意：只有当开头没有数字时才使用这个策略，避免误匹配文本中的"第X条"等
    di_pattern = r'第([一二三四五六七八九十百千万\d]+)(章|节|条|项|部分|编|卷|篇|部|册)'
    di_match = re.search(di_pattern, matched_text)
    if di_match:
        number_text = di_match.group(1)
        number = _extract_number_from_text(number_text)
        if number is not None:
            return number
    
    # 如果所有策略都失败，返回 None
    return None

