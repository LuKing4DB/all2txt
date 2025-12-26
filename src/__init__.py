"""
all2txt - 文档转换工具包

支持将PDF和DOCX文件转换为TXT格式的Python包。

主要功能：
- PDF文件转换为TXT格式
- DOCX文件转换为TXT格式
- 支持提取图片和表格（PDF）
- 支持导出元数据（PDF）
"""

__version__ = "0.1.0"

# 导出主要功能函数
from .pdf2txt.main import convert_pdf
from .docx2txt.main import docx_to_txt_simple

__all__ = [
    "__version__",
    "convert_pdf",
    "docx_to_txt_simple",
]

