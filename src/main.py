#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一文档转换入口
自动根据文件类型（PDF或DOCX）调用对应的转换模块
"""

import argparse
import asyncio
import multiprocessing
import sys
from pathlib import Path
from typing import Optional

# 导入包内模块
try:
    from .utils.logger import get_logger
    from .pdf2txt.main import convert_pdf as convert_pdf_func
    from .docx2txt.main import docx_to_txt_simple
    from .utils.toc_extractor import extract_toc_regions_to_file
except ImportError:
    # 兼容直接运行的情况
    import sys
    from pathlib import Path
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from utils.logger import get_logger
    from pdf2txt.main import convert_pdf as convert_pdf_func
    from docx2txt.main import docx_to_txt_simple
    from utils.toc_extractor import extract_toc_regions_to_file
    from utils.toc_extractor import extract_toc_regions_to_file

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


def _convert_document_sync(
    file_path: str,
    output: Optional[str] = None,
    debug: bool = False,
    result_queue: Optional[multiprocessing.Queue] = None,
    # PDF特有参数
    extract_images: bool = False,
    extract_tables: bool = False,
    table_images: bool = False,
    export_metadata: bool = False,
    num_workers: int = 0,
):
    """
    同步转换文档的内部实现（在独立进程中运行）
    
    此函数在独立进程中执行，结果直接写入硬盘。
    如果提供了 result_queue，会将结果或异常信息放入队列。
    
    Args:
        file_path: 输入文件路径（PDF或DOCX）
        output: 输出目录路径（可选）
        debug: 是否启用调试模式
        result_queue: 结果队列，用于传递转换结果（可选）
        extract_images: 是否提取图片（仅PDF）
        extract_tables: 是否提取表格（仅PDF）
        table_images: 是否保存表格截图（仅PDF）
        export_metadata: 是否导出元数据（仅PDF）
        num_workers: 并行处理的工作进程数（仅PDF，0=自动）
    
    Raises:
        FileNotFoundError: 当文件不存在时
        ValueError: 当文件类型不支持时
        Exception: 当转换过程中发生错误时
    """
    # 检查文件是否存在
    path = Path(file_path)
    if not path.exists():
        error_msg = f"文件不存在: {file_path}"
        logger.error(error_msg)
        error = FileNotFoundError(error_msg)
        if result_queue:
            result_queue.put({'success': False, 'error': error, 'error_type': 'FileNotFoundError'})
        raise error
    
    # 检测文件类型
    file_type = detect_file_type(file_path)
    
    if file_type == 'unknown':
        error_msg = f"不支持的文件类型: {path.suffix}。仅支持 PDF (.pdf) 和 DOCX (.docx) 文件"
        logger.error(error_msg)
        error = ValueError(error_msg)
        if result_queue:
            result_queue.put({'success': False, 'error': error, 'error_type': 'ValueError'})
        raise error
    
    logger.info(f"检测到文件类型: {file_type.upper()}")
    logger.info(f"输入文件: {file_path}")
    
    try:
        if file_type == 'pdf':
            # 确定输出目录
            if output:
                output_dir = Path(output)
            else:
                # 默认输出到以源文件名命名的文件夹
                input_dir = path.parent
                input_stem = path.stem
                output_dir = input_dir / input_stem
            
            # 调用PDF转换函数
            convert_pdf_func(
                file_path=str(path),
                output_dir=output_dir,
                extract_images=extract_images,
                extract_tables=extract_tables,
                table_images=table_images,
                export_metadata=export_metadata,
                num_workers=num_workers,
                debug=debug
            )
            
            # 提取目录区域（PDF转换后，文本文件是 text.txt）
            text_file_path = output_dir / 'text.txt'
            extract_toc_regions_to_file(text_file_path, output_dir)
            
        elif file_type == 'docx':
            # 调用DOCX转换函数
            docx_to_txt_simple(
                docx_path=str(path),
                output_path=output,
                debug=debug
            )
            
            # 提取目录区域（DOCX转换后，确定文本文件路径）
            # 根据docx_to_txt_simple的逻辑，输出路径的确定方式如下：
            if output:
                output_path_docx = Path(output)
                if output_path_docx.is_dir() or not output_path_docx.suffix:
                    output_dir_docx = output_path_docx if output_path_docx.is_dir() else output_path_docx
                    text_file_path = output_dir_docx / (path.stem + '.txt')
                else:
                    output_dir_docx = output_path_docx.parent / output_path_docx.stem
                    text_file_path = output_dir_docx / output_path_docx.name
            else:
                output_dir_docx = path.parent / path.stem
                text_file_path = output_dir_docx / (path.stem + '.txt')
            
            # 提取目录区域
            extract_toc_regions_to_file(text_file_path, output_dir_docx)
        
        # 转换成功，将结果放入队列
        if result_queue:
            result_queue.put({
                'success': True,
                'file_path': file_path,
                'output': output or str(path.parent / path.stem)
            })
            
    except Exception as e:
        logger.error(f"转换失败: {e}", exc_info=debug)
        # 将异常信息放入队列
        if result_queue:
            result_queue.put({
                'success': False,
                'error': e,
                'error_type': type(e).__name__,
                'file_path': file_path
            })
        raise  # 重新抛出异常，让调用者处理


def convert_document(
    file_path: str,
    output: Optional[str] = None,
    debug: bool = False,
    # PDF特有参数
    extract_images: bool = False,
    extract_tables: bool = False,
    table_images: bool = False,
    export_metadata: bool = False,
    num_workers: int = 0,
):
    """
    同步转换文档（阻塞直到完成）
    
    使用进程隔离执行转换，结果直接写入硬盘。
    对于计算密集型任务，使用进程隔离可以避免GIL限制，真正并行执行。
    
    Args:
        file_path: 输入文件路径（PDF或DOCX）
        output: 输出目录路径（可选）
        debug: 是否启用调试模式
        extract_images: 是否提取图片（仅PDF）
        extract_tables: 是否提取表格（仅PDF）
        table_images: 是否保存表格截图（仅PDF）
        export_metadata: 是否导出元数据（仅PDF）
        num_workers: 并行处理的工作进程数（仅PDF，0=自动）
    
    Raises:
        FileNotFoundError: 当文件不存在时
        ValueError: 当文件类型不支持时
        Exception: 当转换过程中发生错误时
    
    Example:
        # 同步转换（阻塞直到完成）
        try:
            all2txt.convert_document("document.pdf", output="./output")
            print("转换完成！")
        except Exception as e:
            print(f"转换失败: {e}")
    """
    # 检查文件是否存在（在主进程中检查，避免子进程启动后才发现问题）
    path = Path(file_path)
    if not path.exists():
        error_msg = f"文件不存在: {file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # 检测文件类型（在主进程中检查）
    file_type = detect_file_type(file_path)
    if file_type == 'unknown':
        error_msg = f"不支持的文件类型: {path.suffix}。仅支持 PDF (.pdf) 和 DOCX (.docx) 文件"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 创建结果队列用于获取异常信息
    result_queue = multiprocessing.Queue()
    
    # 准备参数（需要可序列化）
    kwargs = {
        'file_path': file_path,
        'output': output,
        'debug': debug,
        'extract_images': extract_images,
        'extract_tables': extract_tables,
        'table_images': table_images,
        'export_metadata': export_metadata,
        'num_workers': num_workers,
        'result_queue': result_queue,
    }
    
    # 创建进程并启动
    process = multiprocessing.Process(
        target=_convert_document_sync,
        kwargs=kwargs,
        name=f"all2txt-{path.stem}"
    )
    process.start()
    
    # 等待进程完成
    process.join()
    
    # 检查退出码并获取结果
    if process.exitcode != 0:
        # 尝试从队列获取异常信息
        try:
            result = result_queue.get(timeout=0.1)
            if not result['success']:
                raise result['error']
        except Exception:
            # 如果队列为空，抛出通用异常
            raise RuntimeError(
                f"转换进程异常退出（退出码: {process.exitcode}）。"
                f"请检查日志获取详细错误信息。"
            )


async def aconvert_document(
    file_path: str,
    output: Optional[str] = None,
    debug: bool = False,
    # PDF特有参数
    extract_images: bool = False,
    extract_tables: bool = False,
    table_images: bool = False,
    export_metadata: bool = False,
    num_workers: int = 0,
) -> dict:
    """
    异步转换文档（支持 await，不阻塞事件循环）
    
    使用进程隔离执行转换，结果直接写入硬盘。
    在异步环境中使用 await 等待转换完成，不会阻塞事件循环。
    
    Args:
        file_path: 输入文件路径（PDF或DOCX）
        output: 输出目录路径（可选）
        debug: 是否启用调试模式
        extract_images: 是否提取图片（仅PDF）
        extract_tables: 是否提取表格（仅PDF）
        table_images: 是否保存表格截图（仅PDF）
        export_metadata: 是否导出元数据（仅PDF）
        num_workers: 并行处理的工作进程数（仅PDF，0=自动）
    
    Returns:
        结果字典，包含：
        - success: bool - 是否成功
        - file_path: str - 输入文件路径
        - output: str - 输出目录路径（成功时）
        - error: Optional[Exception] - 异常对象（失败时）
    
    Raises:
        FileNotFoundError: 当文件不存在时（在启动进程前检查）
        ValueError: 当文件类型不支持时（在启动进程前检查）
    
    Example:
        import asyncio
        import all2txt
        
        async def main():
            # 使用 await 等待转换完成
            result = await all2txt.aconvert_document("document.pdf")
            if result['success']:
                print(f"转换成功: {result['output']}")
            else:
                print(f"转换失败: {result['error']}")
            
            # 并发处理多个文件
            tasks = [
                all2txt.aconvert_document("doc1.pdf"),
                all2txt.aconvert_document("doc2.pdf"),
            ]
            results = await asyncio.gather(*tasks)
            for result in results:
                print(f"{result['file_path']}: {'成功' if result['success'] else '失败'}")
        
        asyncio.run(main())
    """
    # 检查文件是否存在
    path = Path(file_path)
    if not path.exists():
        error_msg = f"文件不存在: {file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # 检测文件类型
    file_type = detect_file_type(file_path)
    if file_type == 'unknown':
        error_msg = f"不支持的文件类型: {path.suffix}。仅支持 PDF (.pdf) 和 DOCX (.docx) 文件"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 创建结果队列
    result_queue = multiprocessing.Queue()
    
    # 准备参数
    kwargs = {
        'file_path': file_path,
        'output': output,
        'debug': debug,
        'extract_images': extract_images,
        'extract_tables': extract_tables,
        'table_images': table_images,
        'export_metadata': export_metadata,
        'num_workers': num_workers,
        'result_queue': result_queue,
    }
    
    # 创建进程并启动
    process = multiprocessing.Process(
        target=_convert_document_sync,
        kwargs=kwargs,
        name=f"all2txt-{path.stem}"
    )
    process.start()
    
    # 在事件循环中异步等待进程完成
    loop = asyncio.get_event_loop()
    
    # 使用 run_in_executor 异步等待进程（不阻塞事件循环）
    def _wait_process():
        """在线程池中等待进程完成"""
        process.join()
        return process.exitcode
    
    exitcode = await loop.run_in_executor(None, _wait_process)
    
    # 从队列获取结果
    try:
        result = result_queue.get(timeout=0.1)
        if result['success']:
            return {
                'success': True,
                'file_path': result['file_path'],
                'output': result['output'],
                'error': None
            }
        else:
            # 失败时返回结果字典，包含异常
            return {
                'success': False,
                'file_path': result.get('file_path', file_path),
                'output': None,
                'error': result['error']
            }
    except Exception:
        # 如果队列为空，检查退出码
        if exitcode != 0:
            error = RuntimeError(
                f"转换进程异常退出（退出码: {exitcode}）。"
                f"请检查日志获取详细错误信息。"
            )
            return {
                'success': False,
                'file_path': file_path,
                'output': None,
                'error': error
            }
        # 正常情况下应该不会到这里
        raise RuntimeError("无法获取转换结果")


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
    
    # 调用转换函数（同步等待完成）
    try:
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
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"转换失败: {e}", exc_info=args.debug)
        sys.exit(1)


if __name__ == '__main__':
    # Windows 平台需要保护多进程入口
    # 设置启动方法（Windows 默认使用 spawn）
    if sys.platform == 'win32':
        multiprocessing.freeze_support()
        # 确保使用 spawn 方式（Windows 默认）
        try:
            multiprocessing.set_start_method('spawn', force=False)
        except RuntimeError:
            # 如果已经设置过，忽略错误
            pass
    main()

