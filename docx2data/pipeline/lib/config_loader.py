"""
配置加载器模块
用于读取和加载YAML配置文件
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_file: 配置文件路径，如果为None则尝试查找默认配置文件
        
    Returns:
        配置字典
        
    Raises:
        FileNotFoundError: 如果配置文件不存在
        yaml.YAMLError: 如果配置文件格式错误
    """
    if config_file is None:
        # 尝试查找默认配置文件
        # 1. 当前目录下的 config.yaml
        # 2. 脚本目录下的 config/config.yaml
        script_dir = Path(__file__).parent.parent
        possible_paths = [
            Path("config.yaml"),  # 当前工作目录
            script_dir / "config" / "config.yaml",  # 脚本目录下的config文件夹
            script_dir / "config.yaml",  # 脚本目录（向后兼容）
        ]
        
        config_path = None
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        
        if config_path is None:
            raise FileNotFoundError(
                "未找到配置文件。请创建 config/config.yaml 文件，或使用 --config 参数指定配置文件路径。"
            )
    else:
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            config = {}
        
        return config
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"配置文件格式错误: {e}")


def merge_config_with_args(config: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并配置文件和命令行参数
    命令行参数优先级高于配置文件
    
    Args:
        config: 配置文件中的参数
        args: 命令行参数（字典形式）
        
    Returns:
        合并后的参数字典
    """
    merged = config.copy()
    
    # 命令行参数覆盖配置文件参数
    for key, value in args.items():
        if value is not None:
            merged[key] = value
    
    return merged


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    从配置中获取值，支持嵌套键（使用点号分隔）
    
    Args:
        config: 配置字典
        key: 配置键，支持嵌套（如 "openai.base_url"）
        default: 默认值
        
    Returns:
        配置值
    """
    keys = key.split('.')
    value = config
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    return value if value is not None else default

