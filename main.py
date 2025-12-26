#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一文档转换入口
自动根据文件类型（PDF或DOCX）调用对应的转换模块
"""

import argparse
import sys
from pathlib import Path

# 添加src目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# 直接导入utils.logger模块，避免导入src/__init__.py（它依赖pipeline模块）
import importlib
utils_logger = importlib.import_module('utils.logger')
get_logger = utils_logger.get_logger

logger = get_logger(__name__)


def detect_file_type(file_path: str) -> str:
    """
    检测文件类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件类型: 'pdf', 'docx', 或 'unknown'
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == '.pdf':
        return 'pdf'
    elif suffix == '.docx':
        return 'docx'
    else:
        return 'unknown'


def convert_document(
    file_path: str,
    output: str = None,
    debug: bool = False,
    # PDF特有参数
    extract_images: bool = False,
    extract_tables: bool = False,
    table_images: bool = False,
    export_metadata: bool = False,
    num_workers: int = 0,
):
    """
    转换文档（自动根据文件类型选择处理模块）
    
    Args:
        file_path: 输入文件路径（PDF或DOCX）
        output: 输出目录路径（可选）
        debug: 是否启用调试模式
        extract_images: 是否提取图片（仅PDF）
        extract_tables: 是否提取表格（仅PDF）
        table_images: 是否保存表格截图（仅PDF）
        export_metadata: 是否导出元数据（仅PDF）
        num_workers: 并行处理的工作进程数（仅PDF，0=自动）
    """
    # 检查文件是否存在
    path = Path(file_path)
    if not path.exists():
        logger.error(f"文件不存在: {file_path}")
        sys.exit(1)
    
    # 检测文件类型
    file_type = detect_file_type(file_path)
    
    if file_type == 'unknown':
        logger.error(f"不支持的文件类型: {path.suffix}。仅支持 PDF (.pdf) 和 DOCX (.docx) 文件")
        sys.exit(1)
    
    logger.info(f"检测到文件类型: {file_type.upper()}")
    logger.info(f"输入文件: {file_path}")
    
    try:
        if file_type == 'pdf':
            # 导入PDF转换模块
            from pdf2txt.main import convert_pdf
            
            # 确定输出目录
            if output:
                output_dir = Path(output)
            else:
                # 默认输出到以源文件名命名的文件夹
                input_dir = path.parent
                input_stem = path.stem
                output_dir = input_dir / input_stem
            
            # 调用PDF转换函数
            convert_pdf(
                file_path=str(path),
                output_dir=output_dir,
                extract_images=extract_images,
                extract_tables=extract_tables,
                table_images=table_images,
                export_metadata=export_metadata,
                num_workers=num_workers,
                debug=debug
            )
            
        elif file_type == 'docx':
            # 导入DOCX转换模块
            from docx2txt.main import docx_to_txt_simple
            
            # 调用DOCX转换函数
            docx_to_txt_simple(
                docx_path=str(path),
                output_path=output,
                debug=debug
            )
            
    except Exception as e:
        logger.error(f"转换失败: {e}", exc_info=debug)
        sys.exit(1)


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(
        description='统一文档转换工具：自动根据文件类型（PDF/DOCX）调用对应的转换模块',
        epilog="""
示例：
  # 转换PDF文档
  %(prog)s document.pdf
  
  # 转换DOCX文档
  %(prog)s document.docx
  
  # 指定输出目录
  %(prog)s document.pdf --output ./output
  
  # PDF特有选项：提取图片和表格
  %(prog)s document.pdf --images --tables
  
  # 启用调试模式
  %(prog)s document.pdf --debug
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 通用参数
    parser.add_argument(
        'file',
        help='输入文件路径（支持 .pdf 或 .docx 文件）'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出目录路径（可选，默认在输入文件同目录下创建同名文件夹）'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式，输出详细信息'
    )
    
    # PDF特有参数
    pdf_group = parser.add_argument_group(
        'PDF选项',
        '以下选项仅对PDF文件有效'
    )
    pdf_group.add_argument(
        '--images',
        action='store_true',
        help='提取图片（仅PDF，默认：不提取）'
    )
    pdf_group.add_argument(
        '--tables',
        action='store_true',
        help='提取表格（仅PDF，默认：不提取）'
    )
    pdf_group.add_argument(
        '--table-images',
        action='store_true',
        help='保存表格截图PNG（仅PDF，默认：否）'
    )
    pdf_group.add_argument(
        '--metadata',
        action='store_true',
        help='导出元数据到NDJSON（仅PDF，默认：不导出）'
    )
    pdf_group.add_argument(
        '--workers',
        type=int,
        default=0,
        help='并行处理的工作进程数（仅PDF，0=自动，1=串行，默认：0）'
    )
    
    args = parser.parse_args()
    
    # 检查文件类型，如果使用了PDF特有参数但文件不是PDF，给出警告
    file_type = detect_file_type(args.file)
    if file_type != 'pdf':
        pdf_only_args = []
        if args.images:
            pdf_only_args.append('--images')
        if args.tables:
            pdf_only_args.append('--tables')
        if args.table_images:
            pdf_only_args.append('--table-images')
        if args.metadata:
            pdf_only_args.append('--metadata')
        if args.workers != 0:
            pdf_only_args.append('--workers')
        
        if pdf_only_args:
            logger.warning(
                f"警告：以下选项仅对PDF文件有效，当前文件类型为 {file_type.upper()}，"
                f"这些选项将被忽略: {', '.join(pdf_only_args)}"
            )
    
    # 调用转换函数
    convert_document(
        file_path=args.file,
        output=args.output,
        debug=args.debug,
        extract_images=args.images,
        extract_tables=args.tables,
        table_images=args.table_images,
        export_metadata=args.metadata,
        num_workers=args.workers,
    )


if __name__ == '__main__':
    main()

