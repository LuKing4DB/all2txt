"""
全局日志配置模块
统一管理所有脚本的日志输出
"""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = None,
    level: int = logging.INFO,
    format_string: str = None,
    enable_file_logging: bool = False,
    log_file: str = None
) -> logging.Logger:
    """
    设置并返回一个配置好的logger
    
    Args:
        name: logger名称，如果为None则使用调用模块的名称
        level: 日志级别，默认为INFO
        format_string: 日志格式字符串，如果为None则使用默认格式
        enable_file_logging: 是否启用文件日志，默认为False
        log_file: 日志文件路径，如果为None则使用默认路径
        
    Returns:
        配置好的logger实例
    """
    # 如果没有指定名称，尝试从调用栈获取模块名
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get('__name__', 'root')
        name = module_name
    
    logger = logging.getLogger(name)
    
    # 如果logger已经有handlers，直接返回（避免重复配置）
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(level)
    
    # 阻止日志向上传播到父logger，避免重复输出
    logger.propagate = False
    
    # 默认日志格式
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if enable_file_logging:
        if log_file is None:
            # 默认日志文件路径：项目根目录下的logs目录
            project_root = Path(__file__).parent.parent.parent
            log_dir = project_root / 'logs'
            log_dir.mkdir(exist_ok=True)
            log_file = str(log_dir / 'app.log')
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    获取一个配置好的logger（便捷函数）
    
    Args:
        name: logger名称，如果为None则使用调用模块的名称
        level: 日志级别，默认为INFO
        
    Returns:
        配置好的logger实例
    """
    return setup_logger(name=name, level=level)


# 创建默认的根logger（用于快速使用）
default_logger = get_logger('docx2data', logging.INFO)

