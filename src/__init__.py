"""
all2txt - 文档转换工具包

支持将PDF和DOCX文件转换为TXT格式的Python包。

主要功能：
- PDF文件转换为TXT格式
- DOCX文件转换为TXT格式
- 支持提取图片和表格（PDF）
- 支持导出元数据（PDF）

使用示例：
    import all2txt
    
    # 转换文档（自动检测文件类型）
    try:
        all2txt.convert_document("document.pdf")
        all2txt.convert_document("document.docx", output="./output")
        
        # PDF特有选项
        all2txt.convert_document(
            "document.pdf",
            output="./output",
            extract_images=True,
            extract_tables=True,
            num_workers=4
        )
    except FileNotFoundError as e:
        print(f"文件不存在: {e}")
    except ValueError as e:
        print(f"不支持的文件类型: {e}")
    except Exception as e:
        print(f"转换失败: {e}")
    
    # 检测文件类型
    file_type = all2txt.detect_file_type("document.pdf")  # 返回 'pdf'
"""

__version__ = "0.1.0"

# 导出统一接口
from .main import convert_document, detect_file_type

__all__ = [
    "__version__",
    "convert_document",  # 统一转换入口
    "detect_file_type",  # 文件类型检测
]

