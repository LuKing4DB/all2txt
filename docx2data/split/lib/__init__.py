"""
正则表达式分割器库
提供文件分割相关的功能模块
"""

from .regex_splitter import split_by_regex, RegexSplitter
from .number_extractor import extract_number_from_match

__all__ = ['split_by_regex', 'RegexSplitter', 'extract_number_from_match']

