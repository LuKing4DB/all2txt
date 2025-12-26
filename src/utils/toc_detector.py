"""
目录区域检测模块
用于检测文件中的目录区域，包括基于末尾数字的目录行和基于关键字的目录区域
"""

import re
import sys
import importlib.util
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# 添加split/lib目录到路径，以便支持直接导入
split_lib_dir = Path(__file__).parent
if str(split_lib_dir) not in sys.path:
    sys.path.insert(0, str(split_lib_dir))

from utils.logger import get_logger

# 尝试相对导入，如果失败则使用绝对导入
try:
    from .number_extractor import extract_number_from_match
except ImportError:
    # 如果相对导入失败，使用绝对导入
    from number_extractor import extract_number_from_match

logger = get_logger(__name__)

# 目录分隔符正则表达式（支持各种点号、横线、竖线、中文标点等）
# 匹配1个或多个分隔符字符（适配去重后的情况，原本至少3个，去重后可能只有1个）
TOC_SEPARATOR_PATTERN = r'([.…·•▪▫○●□■◆◇▲△★☆・\-—–_=~|│┃┄┅┈┉─━。，]{1,})'
# 全角空格分隔符（至少1个连续全角空格，适配去重后的情况）
FULL_WIDTH_SPACE_PATTERN = r'([　]{1,})'


def _extract_title_from_toc_line(line: str) -> str:
    """
    从目录行中提取标题部分（去除分隔符和页码）
    
    适配去重后的情况：分隔符可能只有1个，分隔符和页码可能直接相连。
    
    Args:
        line: 目录行内容
        
    Returns:
        提取的标题文本（去除分隔符和末尾页码后）
    """
    if not line:
        return ""
    
    stripped_line = line.lstrip()
    if not stripped_line:
        return ""
    
    # 先尝试匹配常规分隔符（适配去重后可能只有1个）
    separator_match = re.search(TOC_SEPARATOR_PATTERN, stripped_line)
    # 如果没找到，尝试匹配全角空格
    if not separator_match:
        separator_match = re.search(FULL_WIDTH_SPACE_PATTERN, stripped_line)
    
    # 如果有分隔符，只取分隔符之前的部分
    if separator_match:
        title = stripped_line[:separator_match.start()].strip()
    else:
        # 如果没有找到分隔符，尝试直接匹配"标题+分隔符+数字"的模式
        # 适配去重后的情况：分隔符和页码可能直接相连，如"标题.2"
        # 匹配模式：标题 + 分隔符 + 可选的空格 + 数字
        match = re.search(r'^(.+?)[.…·•▪▫○●□■◆◇▲△★☆・\-—–_=~|│┃┄┅┈┉─━。，]\s*\d+$', stripped_line)
        if match:
            title = match.group(1).strip()
        else:
            title = stripped_line
    
    # 去除末尾的数字（可能是页码，适配去重后分隔符和数字直接相连的情况）
    # 匹配：分隔符 + 可选的空格 + 数字
    title = re.sub(r'[.…·•▪▫○●□■◆◇▲△★☆・\-—–_=~|│┃┄┅┈┉─━。，]\s*\d+$', '', title).strip()
    # 如果还有末尾数字，也去除（兜底处理）
    title = re.sub(r'\d+$', '', title).strip()
    
    return title


def _load_common_patterns():
    """
    加载常见的目录形式 pattern（从 regex_patterns.py）
    
    Returns:
        常见 pattern 列表
    """
    common_patterns = []
    
    # 尝试加载 regex_patterns.py
    try:
        # 查找 regex_patterns.py 文件
        # 可能在 pipeline/config/regex_patterns.py 或 split/config/regex_patterns.py
        possible_paths = [
            Path(__file__).parent.parent.parent / 'pipeline' / 'config' / 'regex_patterns.py',
            Path(__file__).parent.parent.parent / 'split' / 'config' / 'regex_patterns.py',
        ]
        
        config_path = None
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        
        if config_path:
            spec = importlib.util.spec_from_file_location("regex_patterns", config_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 提取所有 pattern
            if hasattr(module, 'PATTERNS'):
                for item in module.PATTERNS:
                    if 'pattern' in item:
                        common_patterns.append(item['pattern'])
    except Exception as e:
        logger.debug(f"加载常见 pattern 失败: {e}")
    
    # 如果没有加载到，使用默认的常见 pattern
    if not common_patterns:
        common_patterns = [
            r"^(第[一二三四五六七八九十百千]+章).*",
            r"^(第[一二三四五六七八九十百千]+卷).*",
            r"^(第[一二三四五六七八九十百千]+节).*",
            r"^(第[一二三四五六七八九十百千]+册).*",
            r"^(第[一二三四五六七八九十百千]+部分).*",
            r"^[一二三四五六七八九十百千]+、\S.*",
            r"^[0-9]+、\S.*",
            r"^[0-9]+[^.\d）)]\S.*",
            r"^[0-9]+\.[^.\d]\S.*",
            r"^（[一二三四五六七八九十百千]+）\S.*",
        ]
    
    return common_patterns


def is_toc_item(line: str) -> bool:
    """
    检测一行是否是目录项（单行检测）
    目录行的特征是末尾是数字（通常是页码）
    
    Args:
        line: 要去除前导空格后的行内容
        
    Returns:
        如果符合目录项格式返回True，否则返回False
    """
    if not line or not line.strip():
        return False
    
    # 去除前后空格
    stripped = line.strip()
    
    # 检测末尾是否是数字（可能是页码）
    # 匹配模式：行末尾是数字，可能前面有空格、点、或其他分隔符，也可能直接是数字
    # 例如：
    # "第一章 标题 1"
    # "第一章招标公告（代投标邀请）1"  # 末尾直接是数字
    # "1.1 标题 10"
    # "标题... 5"
    # "标题 123"
    
    # 确保不是纯数字行（避免误判）
    if re.match(r'^\s*\d+\s*$', stripped):
        return False
    
    # 匹配末尾的数字（至少1位），可能前面有空格、点、省略号等，也可能直接是数字
    # 适配去重后的情况：分隔符可能只有1个
    toc_patterns = [
        r'\s+\d+$',           # 末尾是空格+数字
        r'[.…·•▪▫○●□■◆◇▲△★☆・\-—–_=~|│┃┄┅┈┉─━。，]\s*\d+$',  # 末尾是分隔符+数字（适配去重后可能只有1个分隔符）
        r'[.…·•▪▫○●□■◆◇▲△★☆・\-—–_=~|│┃┄┅┈┉─━。，]{1,}\s*\d+$',  # 末尾是1个或多个分隔符+数字
        r'[^\d]\d+$',         # 末尾直接是数字（前面至少有一个非数字字符）
    ]
    
    for pattern in toc_patterns:
        if re.search(pattern, stripped):
            return True
    
    return False


def detect_toc_regions(lines: list, min_consecutive: int = 2) -> set:
    """
    检测文件中的目录区域（连续多行的目录）
    
    Args:
        lines: 文件的所有行
        min_consecutive: 最少连续行数，只有连续这么多行都是目录行才认为是目录区域
        
    Returns:
        返回一个集合，包含所有目录区域的行号（从0开始）
    """
    toc_lines = set()
    
    # 第一遍扫描：标记所有符合目录格式的行
    for i, line in enumerate(lines):
        stripped_line = line.lstrip()
        if is_toc_item(stripped_line):
            toc_lines.add(i)
    
    # 第二遍扫描：找出连续的目录区域
    # 只有连续至少 min_consecutive 行的目录行才被认为是目录区域
    toc_regions = set()
    
    if len(toc_lines) < min_consecutive:
        return toc_regions
    
    # 按行号排序
    sorted_lines = sorted(toc_lines)
    
    # 找出连续的行段
    current_start = None
    current_count = 0
    
    for i, line_num in enumerate(sorted_lines):
        if current_start is None:
            # 开始新的连续段
            current_start = line_num
            current_count = 1
        else:
            if line_num == sorted_lines[i-1] + 1:
                # 连续的行
                current_count += 1
            else:
                # 不连续，检查之前的段是否满足条件
                if current_count >= min_consecutive:
                    # 将整个连续段加入区域
                    for j in range(current_start, current_start + current_count):
                        toc_regions.add(j)
                # 开始新的连续段
                current_start = line_num
                current_count = 1
    
    # 处理最后一段
    if current_start is not None and current_count >= min_consecutive:
        for j in range(current_start, current_start + current_count):
            toc_regions.add(j)
    
    return toc_regions


def detect_toc_region_by_keyword(lines: list, pattern: str) -> set:
    """
    检测文件中的目录区域（基于"目录"关键字和标题匹配）
    
    逻辑：
    1. 从上到下检测到"目录"两个字则激活
    2. 锁定目录下第一个part名字（匹配标题格式的行）
    3. 然后逐行检测到标题再次出现，将这中间的全部区域标记为目录区域
    
    Args:
        lines: 文件的所有行
        pattern: 正则表达式模式，用于匹配标题（分割点）
        
    Returns:
        返回一个集合，包含所有目录区域的行号（从0开始）
    """
    toc_region_lines = set()
    
    # 编译正则表达式用于匹配标题
    patterns_to_try = []
    
    try:
        if pattern:
            # 如果pattern是临时pattern（只匹配空行），使用常见的目录形式 pattern
            if pattern == r'^$':
                # 加载常见的目录形式 pattern
                common_patterns = _load_common_patterns()
                if common_patterns:
                    patterns_to_try = [re.compile(p, re.MULTILINE) for p in common_patterns]
                else:
                    # 如果没有加载到，使用默认 pattern
                    patterns_to_try = [re.compile(r'^第[一二三四五六七八九十百千万\d]+[章节]', re.MULTILINE)]
            else:
                patterns_to_try = [re.compile(pattern, re.MULTILINE)]
        else:
            return toc_region_lines
    except re.error as e:
        logger.warning(f"无效的正则表达式模式，跳过基于关键字的目录区域检测: {pattern}, 错误: {e}")
        return toc_region_lines
    
    if not patterns_to_try:
        return toc_region_lines
    
    # 从上至下查找第一个"目录"关键字，只激活一次
    # 查找范围：前100行或前20%的行数，取较大值
    max_search_lines = max(100, int(len(lines) * 0.2))
    search_end_line = min(max_search_lines, len(lines))
    
    for i in range(search_end_line):
        line = lines[i].strip()
        
        # 检测到包含"目录"的行则激活（包括"目录"两个字、"xxxx目录"、"目录xxxx"等）
        # 但排除明显不是目录标题的行（如包含"目录"但后面有很多内容的行）
        if "目录" in line:
            # 如果行中包含"目录"且行长度较短（可能是目录标题），或者以"目录"结尾
            # 排除包含"目录"但明显是正文内容的长行
            if line.endswith("目录") or (len(line) <= 50 and "目录" in line):
                toc_start = i  # 记录目录行的位置
                
                # 从下一行开始查找第一个匹配标题格式的行（part名字）
                first_part_line = None
                matched_regex = None  # 记录匹配到的 regex
                first_part_number = None  # 记录首条目录序号
                j = i + 1
                while j < len(lines):
                    stripped_line = lines[j].lstrip()
                    if stripped_line:
                        # 从目录行中提取标题部分
                        line_for_match = _extract_title_from_toc_line(stripped_line)
                        
                        # 尝试使用所有 pattern 来匹配（使用处理后的行）
                        for regex in patterns_to_try:
                            match = regex.search(line_for_match)
                            if match and match.start() == 0:
                                # 找到匹配的行，提取序号（允许不是1）
                                first_part_name_raw = line_for_match.strip()
                                first_part_number = extract_number_from_match(first_part_name_raw)
                                # 记录这一行和匹配到的 regex
                                first_part_line = j
                                matched_regex = regex
                                break
                        
                        # 如果找到了匹配的行，跳出外层循环
                        if first_part_line is not None:
                            break
                    j += 1
                
                # 如果没有找到匹配的part名字，结束目录检测（只激活一次，直接返回）
                if first_part_line is None or matched_regex is None:
                    return toc_region_lines
                
                # 如果找到了第一个part名字（序号为1），继续处理
                # 从目录行中提取标题部分用于后续匹配
                first_part_name_raw = lines[first_part_line].strip()
                first_part_name = _extract_title_from_toc_line(first_part_name_raw)
                
                # 根据首条序号决定闭合搜索范围：
                # - 序号为1：搜索前50%行
                # - 序号非1：搜索前30%行
                # - 无法提取序号：全篇搜索
                closure_search_end = len(lines)
                if first_part_number is not None:
                    ratio = 0.5 if first_part_number == 1 else 0.3
                    closure_search_end = min(len(lines), max(first_part_line + 1, int(len(lines) * ratio)))
                
                # 从第一个part名字的下一行开始查找，搜索到文件末尾
                # 目录区域可能很长，不应该限制搜索范围（除非首条序号不是1）
                for k in range(first_part_line + 1, closure_search_end):
                    stripped_line = lines[k].lstrip()
                    if stripped_line:
                        # 从目录行中提取标题部分
                        line_for_match = _extract_title_from_toc_line(stripped_line)
                        
                        # 检查是否再次出现与第一个part名字相同的标题
                        # 使用匹配到的 regex 来检查是否匹配标题格式
                        match = matched_regex.search(line_for_match)
                        if match and match.start() == 0:
                            # 检查是否与第一个part名字相同（去除前后空格后比较）
                            current_line_stripped = line_for_match.strip()
                            if current_line_stripped == first_part_name:
                                # 找到了第一个part名字再次出现，将中间区域标记为目录区域
                                # 包括从"目录"行到该标题行之前的所有行
                                for line_num in range(toc_start, k):
                                    toc_region_lines.add(line_num)
                                break
                
                # 无论是否找到闭合行，都直接返回（只激活一次）
                return toc_region_lines
    
    return toc_region_lines

