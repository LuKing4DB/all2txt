"""
通用库模块
提供图片检测、印章识别等功能
"""

from .image_detector import (
    has_image,
    get_image_data_from_paragraph,
    get_image_size_from_paragraph,
    is_square_image,
    is_red_image,
    has_stamp_features
)

__all__ = [
    'has_image',
    'get_image_data_from_paragraph',
    'get_image_size_from_paragraph',
    'is_square_image',
    'is_red_image',
    'has_stamp_features',
]

