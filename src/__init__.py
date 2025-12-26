"""
all2txt - 文档转换工具包

支持将PDF和DOCX文件转换为TXT格式的Python包。

主要功能：
- PDF文件转换为TXT格式
- DOCX文件转换为TXT格式
- 支持提取图片和表格（PDF）
- 支持导出元数据（PDF）
- 默认使用进程隔离异步执行，适合计算密集型任务

使用示例：
    import all2txt
    
    # 方式1：同步转换（阻塞直到完成）
    try:
        all2txt.convert_document(
            "document.pdf",
            output="./output",
            extract_images=True,
            extract_tables=True
        )
        print("转换完成！")
    except FileNotFoundError as e:
        print(f"文件不存在: {e}")
    except ValueError as e:
        print(f"不支持的文件类型: {e}")
    except Exception as e:
        print(f"转换失败: {e}")
    
    # 方式2：异步转换（支持 await，不阻塞事件循环）
    import asyncio
    
    async def main():
        # 单个文件转换
        result = await all2txt.aconvert_document("document.pdf", output="./output")
        if result['success']:
            print(f"转换成功: {result['output']}")
        else:
            print(f"转换失败: {result['error']}")
        
        # 并发处理多个文件
        tasks = [
            all2txt.aconvert_document("doc1.pdf", extract_images=True),
            all2txt.aconvert_document("doc2.pdf", extract_images=True),
            all2txt.aconvert_document("doc3.docx"),
        ]
        results = await asyncio.gather(*tasks)
        for result in results:
            if result['success']:
                print(f"✓ {result['file_path']} 转换完成")
            else:
                print(f"✗ {result['file_path']} 转换失败: {result['error']}")
    
    asyncio.run(main())
    
    # 检测文件类型
    file_type = all2txt.detect_file_type("document.pdf")  # 返回 'pdf'
"""

__version__ = "0.1.0"

# 导出统一接口
from .main import convert_document, aconvert_document, detect_file_type

__all__ = [
    "__version__",
    "convert_document",  # 同步转换入口（阻塞等待）
    "aconvert_document",  # 异步转换入口（支持 await）
    "detect_file_type",  # 文件类型检测
]

