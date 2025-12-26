"""
本地模式匹配器模块
使用本地验证的方式，从样本文件从上至下逐行验证，返回第一个被命中的正则表达式
"""

import re
import sys
from pathlib import Path
from typing import Optional, Tuple

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# 添加lib目录到路径
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from regex_loader import load_regex_patterns_with_descriptions
from utils.logger import get_logger

logger = get_logger(__name__)


def match_pattern_locally(sample: str, regex_config_file: str = None) -> Optional[Tuple[str, str, int]]:
    """
    使用本地验证的方式，从样本文件从上至下逐行验证，返回第一个被命中的正则表达式
    
    Args:
        sample: 样本文本
        regex_config_file: 正则表达式配置文件路径
        
    Returns:
        如果找到匹配，返回 (选项编号, 正则表达式模式, 匹配的行号) 元组
        如果没有找到匹配，返回 None
    """
    if not sample:
        return None
    
    # 加载正则表达式配置
    try:
        regex_map, descriptions_map = load_regex_patterns_with_descriptions(regex_config_file)
    except Exception as e:
        logger.warning(f"加载正则表达式配置失败: {e}")
        return None
    
    if not regex_map:
        logger.warning("正则表达式配置为空")
        return None
    
    # 将样本按行分割
    lines = sample.split('\n')
    
    # 从上到下逐行验证
    for line_idx, line in enumerate(lines):
        stripped_line = line.lstrip()
        if not stripped_line:
            continue
        
        # 按选项编号顺序测试每个正则表达式
        for option_id in sorted(regex_map.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            pattern = regex_map[option_id]
            try:
                regex = re.compile(pattern, re.MULTILINE)
                match = regex.search(stripped_line)
                if match and match.start() == 0:
                    # 找到第一个匹配的正则表达式
                    description = descriptions_map.get(option_id, "无描述")
                    logger.info(f"本地验证匹配成功：行 {line_idx + 1} 匹配选项 {option_id} ({description})")
                    logger.info(f"  匹配的行: {stripped_line[:50]}")
                    logger.info(f"  正则表达式: {pattern}")
                    return (option_id, pattern, line_idx + 1)
            except re.error as e:
                logger.debug(f"选项 {option_id} 的正则表达式编译失败: {e}")
                continue
            except Exception as e:
                logger.debug(f"测试选项 {option_id} 时出错: {e}")
                continue
    
    # 没有找到匹配
    logger.info("本地验证：没有找到匹配的正则表达式")
    return None

