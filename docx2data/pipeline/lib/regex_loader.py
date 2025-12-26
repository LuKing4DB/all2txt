"""
正则表达式加载器模块
用于从配置文件加载正则表达式选项
只支持 Python 配置文件（.py），使用原始字符串，无需转义，所见即所得
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)


def load_regex_patterns(config_file: Optional[str] = None) -> Dict[str, str]:
    """
    加载正则表达式选项映射
    
    Args:
        config_file: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        正则表达式映射字典，格式: {"1": "pattern1", "2": "pattern2", ...}
        键为序号（从1开始），值为正则表达式模式
    """
    if config_file is None:
        # 使用默认路径：只使用 Python 格式（无转义，所见即所得）
        script_dir = Path(__file__).parent.parent
        config_file = str(script_dir / "config" / "regex_patterns.py")
    
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"正则表达式配置文件不存在: {config_file}")
    
    try:
        # 只支持 Python 配置文件（无转义，所见即所得）
        if config_path.suffix.lower() != '.py':
            raise ValueError(f"只支持 Python 配置文件（.py），不支持 {config_path.suffix} 格式")
        
        # Python 配置文件：直接导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("regex_patterns", config_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = {"patterns": module.PATTERNS}
        
        if not config or 'patterns' not in config:
            raise ValueError("配置文件格式错误：缺少 'patterns' 字段")
        
        # 构建映射字典，使用列表索引+1作为序号（从1开始）
        regex_map = {}
        for index, pattern_item in enumerate(config['patterns'], start=1):
            pattern = pattern_item.get('pattern')
            if pattern:
                # 使用序号作为键（字符串格式）
                regex_map[str(index)] = pattern
        
        logger.debug(f"已加载 {len(regex_map)} 个正则表达式选项")
        return regex_map
        
    except Exception as e:
        raise RuntimeError(f"加载正则表达式配置失败: {e}")


def load_regex_patterns_with_descriptions(config_file: Optional[str] = None) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    加载正则表达式选项映射和描述信息
    
    Args:
        config_file: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        (regex_map, descriptions_map) 元组
        - regex_map: 正则表达式映射字典，格式: {"1": "pattern1", "2": "pattern2", ...}
        - descriptions_map: 描述映射字典，格式: {"1": "描述1", "2": "描述2", ...}
    """
    if config_file is None:
        # 使用默认路径：只使用 Python 格式（无转义，所见即所得）
        script_dir = Path(__file__).parent.parent
        config_file = str(script_dir / "config" / "regex_patterns.py")
    
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"正则表达式配置文件不存在: {config_file}")
    
    try:
        # 只支持 Python 配置文件（无转义，所见即所得）
        if config_path.suffix.lower() != '.py':
            raise ValueError(f"只支持 Python 配置文件（.py），不支持 {config_path.suffix} 格式")
        
        # Python 配置文件：直接导入模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("regex_patterns", config_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = {"patterns": module.PATTERNS}
        
        if not config or 'patterns' not in config:
            raise ValueError("配置文件格式错误：缺少 'patterns' 字段")
        
        # 构建映射字典，使用列表索引+1作为序号（从1开始）
        regex_map = {}
        descriptions_map = {}
        for index, pattern_item in enumerate(config['patterns'], start=1):
            pattern = pattern_item.get('pattern')
            description = pattern_item.get('description', '')
            if pattern:
                # 使用序号作为键（字符串格式）
                regex_map[str(index)] = pattern
                descriptions_map[str(index)] = description
        
        logger.debug(f"已加载 {len(regex_map)} 个正则表达式选项")
        return regex_map, descriptions_map
        
    except Exception as e:
        raise RuntimeError(f"加载正则表达式配置失败: {e}")


def get_regex_options_text(regex_map: Dict[str, str], descriptions_map: Optional[Dict[str, str]] = None, exclude_options: Optional[list] = None) -> str:
    """
    将正则表达式映射转换为提示词中的有序列表格式
    只显示序号和描述，不显示正则表达式模式本身，避免转义问题
    
    Args:
        regex_map: 正则表达式映射字典，键为序号（字符串），值为正则表达式模式
        descriptions_map: 描述映射字典，键为序号（字符串），值为描述文本。如果为None，则只显示序号
        exclude_options: 要排除的选项编号列表（字符串列表），如果为None则不排除任何选项
        
    Returns:
        格式化的有序列表文本（带编号）
    """
    if exclude_options is None:
        exclude_options = []
    
    options = []
    # 按照序号排序（转换为整数排序）
    for pattern_id in sorted(regex_map.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        # 如果该选项在排除列表中，跳过
        if pattern_id in exclude_options:
            continue
            
        if descriptions_map and pattern_id in descriptions_map:
            # 只显示序号和描述，不显示模式
            description = descriptions_map[pattern_id]
            options.append(f"{pattern_id}. {description}")
        else:
            # 如果没有描述，只显示序号
            options.append(f"{pattern_id}.")
    
    return "\n".join(options)


def convert_option_to_regex(option: str, regex_map: Dict[str, str]) -> str:
    """
    将选项编号转换为对应的正则表达式
    
    Args:
        option: 选项编号（字符串形式的数字）
        regex_map: 正则表达式映射字典
        
    Returns:
        对应的正则表达式，如果不在映射中则返回原值
    """
    if option in regex_map:
        return regex_map[option]
    return option
