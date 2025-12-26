"""
有序列表检测模块
用于检测文件中的有序列表区域
"""

import re
import sys
from pathlib import Path
from typing import Optional, List, Set, Tuple

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# 添加split/lib目录到路径，以便支持直接导入
split_lib_dir = Path(__file__).parent
if str(split_lib_dir) not in sys.path:
    sys.path.insert(0, str(split_lib_dir))

# 尝试相对导入，如果失败则使用绝对导入
try:
    from .number_extractor import extract_number_from_match
except ImportError:
    # 如果相对导入失败，使用绝对导入
    from number_extractor import extract_number_from_match

# 定义有序列表的正则表达式模式及其类型标识
# 匹配以下格式：
# 1. 数字 + 点 + 空格：1. , 2. , 10. 
# 2. 数字 + 右括号 + 空格：1) , 2) 
# 3. 中文括号 + 数字：（1）, （2）, (1), (2)
# 4. 中文括号 + 中文数字：（一）, （二）, （三）等
# 5. 中文数字序号：一、, 二、, 三、, 四、, 五、, 六、, 七、, 八、, 九、, 十、
# 6. 带圈数字：①, ②, ③ 等
# 7. 罗马数字：I., II., III. 等（简单匹配）
# 8. 第X章格式：第一章, 第二章, 第3章 等
# 9-12. 多级数字标题格式（互斥，按从最具体到最一般顺序）：
#     - 四级标题：1.1.1.1
#     - 三级标题：1.1.1
#     - 二级标题：3.1
#     - 一级标题：1.
ORDERED_LIST_PATTERNS: List[Tuple[str, str]] = [
    # 互斥的多级数字标题格式（必须放在前面，按从最具体到最一般顺序）
    (r'^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[^.\d]\S.*', 'number_level4'),  # 四级标题：1.1.1.1
    (r'^[0-9]+\.[0-9]+\.[0-9]+[^.\d]\S.*', 'number_level3'),          # 三级标题：1.1.1
    (r'^[0-9]+\.[0-9]+[^.\d]\S.*', 'number_level2'),                  # 二级标题：3.1
    (r'^[0-9]+\.[^.\d]\S.*', 'number_level1'),                        # 一级标题：1.
    
    # 其他格式
    (r'^\d+\.\s+', 'number_dot'),           # 1. , 2. , 10. (点号后可以有空格也可以没有) 
    (r'^\d+\)\s+', 'number_paren'),         # 1) , 2) 
    (r'^[（(]\d+[）)]\s*', 'paren_number'),   # （1）, （2）, (1), (2)
    (r'^[（(][一二三四五六七八九十]+[）)]\s*', 'paren_chinese'),  # （一）, （二）, （三）等
    (r'^[一二三四五六七八九十]+[、.]\s*', 'chinese_dot'),  # 一、, 二、, 三、
    (r'^[①②③④⑤⑥⑦⑧⑨⑩]+[、.]?\s*', 'circled_number'),  # ①, ②, ③
    (r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[、.]?\s*', 'roman_number'),  # 罗马数字
    (r'^第[一二三四五六七八九十百千万\d]+章', 'chapter'),  # 第一章, 第二章, 第3章 等
]

# 预编译正则表达式以提高性能
_COMPILED_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(pattern), pattern_type) 
    for pattern, pattern_type in ORDERED_LIST_PATTERNS
]


def is_ordered_list_item(line: str) -> bool:
    """
    检测一行是否符合有序列表项的格式（单行检测）
    
    Args:
        line: 要去除前导空格后的行内容
        
    Returns:
        如果符合有序列表项格式返回True，否则返回False
    """
    if not line or not line.strip():
        return False
    
    stripped = line.lstrip()
    
    # 使用预编译的正则表达式进行匹配
    for pattern, _ in _COMPILED_PATTERNS:
        if pattern.match(stripped):
            return True
    
    return False


def get_ordered_list_pattern_type(line: str) -> Optional[str]:
    """
    获取有序列表行的格式类型
    
    Args:
        line: 要去除前导空格后的行内容
        
    Returns:
        返回匹配的模式类型名称，如果不匹配则返回None
    """
    if not line or not line.strip():
        return None
    
    stripped = line.lstrip()
    
    # 使用预编译的正则表达式进行匹配
    for pattern, pattern_type in _COMPILED_PATTERNS:
        if pattern.match(stripped):
            return pattern_type
    
    return None


def _add_region_to_result(
    regions: Set[int], 
    start: int, 
    count: int, 
    min_consecutive: int
) -> None:
    """将满足条件的连续段添加到结果集合中"""
    if count >= min_consecutive:
        regions.update(range(start, start + count))


def _reset_segment_state() -> Tuple[None, int, None, None, Set[str], None]:
    """重置连续段状态"""
    return None, 0, None, None, set(), None


def _start_new_segment(
    line_num: int, 
    pattern_type: Optional[str], 
    line_content: str
) -> Tuple[int, int, Optional[str], str, Set[str], Optional[int]]:
    """开始新的连续段"""
    # 提取序号
    number = extract_number_from_match(line_content)
    return line_num, 1, pattern_type, line_content, {line_content}, number


def detect_ordered_list_regions(
    lines: List[str], 
    min_consecutive: int = 2, 
    exclude_toc_regions: Optional[Set[int]] = None
) -> Set[int]:
    """
    检测文件中的有序列表区域（连续多行的有序列表）
    
    Args:
        lines: 文件的所有行
        min_consecutive: 最少连续行数，只有连续这么多行都是有序列表才认为是列表区域
        exclude_toc_regions: 已检测到的目录区域行号集合，这些行将被排除
        
    Returns:
        返回一个集合，包含所有有序列表区域的行号（从0开始）
    """
    exclude_toc_regions = exclude_toc_regions or set()
    ordered_list_lines: Set[int] = set()
    
    # 第一遍扫描：标记所有符合有序列表格式的行（排除目录行）
    for i, line in enumerate(lines):
        if i not in exclude_toc_regions:
            stripped_line = line.lstrip()
            if is_ordered_list_item(stripped_line):
                ordered_list_lines.add(i)
    
    # 如果有序列表行数不足，直接返回
    if len(ordered_list_lines) < min_consecutive:
        return set()
    
    ordered_list_regions: Set[int] = set()
    sorted_lines = sorted(ordered_list_lines)
    
    # 找出连续且相同格式的行段
    current_start: Optional[int] = None
    current_count: int = 0
    current_pattern_type: Optional[str] = None
    previous_line_content: Optional[str] = None
    seen_lines_in_current_segment: Set[str] = set()
    previous_number: Optional[int] = None  # 上一行的序号
    
    for i, line_num in enumerate(sorted_lines):
        stripped_line = lines[line_num].lstrip()
        pattern_type = get_ordered_list_pattern_type(stripped_line)
        current_line_number = extract_number_from_match(stripped_line)  # 提取当前行的序号
        
        if current_start is None:
            # 开始新的连续段
            current_start, current_count, current_pattern_type, previous_line_content, seen_lines_in_current_segment, previous_number = \
                _start_new_segment(line_num, pattern_type, stripped_line)
        else:
            is_consecutive = line_num == sorted_lines[i - 1] + 1
            
            if is_consecutive:
                # 连续的行
                if stripped_line == previous_line_content:
                    # 前后两行完全相同，不属于有序列表，中断当前段
                    _add_region_to_result(ordered_list_regions, current_start, current_count, min_consecutive)
                    current_start, current_count, current_pattern_type, previous_line_content, seen_lines_in_current_segment, previous_number = \
                        _reset_segment_state()
                elif stripped_line in seen_lines_in_current_segment:
                    # 新的一行已存在于列表中，代表列表已完毕，中断当前段
                    _add_region_to_result(ordered_list_regions, current_start, current_count, min_consecutive)
                    current_start, current_count, current_pattern_type, previous_line_content, seen_lines_in_current_segment, previous_number = \
                        _start_new_segment(line_num, pattern_type, stripped_line)
                elif pattern_type == current_pattern_type:
                    # 格式相同且内容不同，且不在已见过的行中
                    # 检查序号是否连续（如果都能提取到序号）
                    if previous_number is not None and current_line_number is not None:
                        expected_number = previous_number + 1
                        if current_line_number != expected_number:
                            # 序号不连续，中断当前段
                            _add_region_to_result(ordered_list_regions, current_start, current_count, min_consecutive)
                            current_start, current_count, current_pattern_type, previous_line_content, seen_lines_in_current_segment, previous_number = \
                                _start_new_segment(line_num, pattern_type, stripped_line)
                        else:
                            # 序号连续，继续累积
                            current_count += 1
                            previous_line_content = stripped_line
                            seen_lines_in_current_segment.add(stripped_line)
                            previous_number = current_line_number
                    else:
                        # 无法提取序号，按原逻辑继续累积
                        current_count += 1
                        previous_line_content = stripped_line
                        seen_lines_in_current_segment.add(stripped_line)
                        if current_line_number is not None:
                            previous_number = current_line_number
                else:
                    # 格式不同，检查之前的段是否满足条件
                    _add_region_to_result(ordered_list_regions, current_start, current_count, min_consecutive)
                    current_start, current_count, current_pattern_type, previous_line_content, seen_lines_in_current_segment, previous_number = \
                        _start_new_segment(line_num, pattern_type, stripped_line)
            else:
                # 不连续，检查之前的段是否满足条件
                _add_region_to_result(ordered_list_regions, current_start, current_count, min_consecutive)
                current_start, current_count, current_pattern_type, previous_line_content, seen_lines_in_current_segment, previous_number = \
                    _start_new_segment(line_num, pattern_type, stripped_line)
    
    # 处理最后一段
    if current_start is not None:
        _add_region_to_result(ordered_list_regions, current_start, current_count, min_consecutive)
    
    return ordered_list_regions

