"""PDF 预检和修复工具（独立单文件脚本）

可以单独运行来预检和修复 PDF 文件，解决 xref 嵌套过深等问题。
所有功能都集成在这个文件中，无需依赖其他模块。
"""
from __future__ import annotations

import argparse
import signal
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional, Tuple

# 尝试导入依赖
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None
    PdfWriter = None

# 简单的日志功能（不依赖外部模块）
class SimpleLogger:
    """简单的日志类，不依赖外部模块"""
    def __init__(self, name: str = None, debug: bool = False):
        self.name = name or __name__
        self.debug_mode = debug
    
    def debug(self, msg: str):
        if self.debug_mode:
            print(f"[DEBUG] {msg}")
    
    def info(self, msg: str):
        print(f"[INFO] {msg}")
    
    def warning(self, msg: str):
        print(f"[WARNING] {msg}")
    
    def error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr)

# 全局日志对象（会在 main 中初始化）
logger = SimpleLogger()


class TimeoutError(Exception):
    """超时异常"""
    pass


def check_pdf_with_timeout(pdf_path: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
    """检查 PDF 文件是否可以用 pdfplumber 正常打开（带超时）。
    
    Args:
        pdf_path: PDF 文件路径
        timeout: 超时时间（秒），默认 10 秒
        
    Returns:
        (is_ok, error_message)
        - is_ok: True 表示可以正常打开，False 表示有问题
        - error_message: 错误信息（如果有）
    """
    if pdfplumber is None:
        logger.warning("pdfplumber 未安装，跳过预检")
        return True, None  # 如果没有 pdfplumber，跳过检查
    
    result = {'success': False, 'error': None}
    
    def _check_pdf():
        """在单独线程中检查 PDF"""
        try:
            # 尝试打开 PDF
            with pdfplumber.open(pdf_path) as pdf:
                # 尝试访问页数（这会触发 xref 表的解析）
                page_count = len(pdf.pages)
                if page_count == 0:
                    result['error'] = "PDF 没有页面"
                    return
                
                # 尝试访问第一页（进一步验证）
                if page_count > 0:
                    _ = pdf.pages[0]
            
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
    
    # 在单独线程中运行检查
    thread = threading.Thread(target=_check_pdf, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        # 线程仍在运行，说明超时了
        return False, f"PDF 打开超时（>{timeout}秒），可能存在 xref 嵌套过深问题"
    
    # 确保文件句柄释放（Windows 需要）
    import gc
    import time
    gc.collect()
    time.sleep(0.2)  # 短暂等待，确保文件句柄释放
    
    if result['success']:
        return True, None
    else:
        error_msg = result['error'] or "未知错误"
        return False, f"PDF 打开失败: {error_msg}"


def fix_pdf_xref(input_path: str, output_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """修复 PDF 的 xref 表问题。
    
    通过重新读取和写入 PDF，生成新的 xref 表，解决 pdfplumber 卡死问题。
    修复后的文件会保存为带 _fixed 后缀的新文件。
    
    Args:
        input_path: 输入 PDF 文件路径
        output_path: 输出 PDF 文件路径，如果为 None 则自动生成（原文件名_fixed.pdf）
        
    Returns:
        (success, fixed_path)
        - success: True 表示修复成功，False 表示失败
        - fixed_path: 修复后的文件路径（如果成功）
    """
    if PdfReader is None or PdfWriter is None:
        logger.error("pypdf 未安装，无法修复 PDF")
        logger.error("安装命令: pip install pypdf")
        return False, None
    
    input_path = Path(input_path)
    if not input_path.exists():
        logger.error(f"文件不存在: {input_path}")
        return False, None
    
    if output_path is None:
        # 生成新文件（在原文件同目录下，带 _fixed 后缀）
        output_path = input_path.parent / f"{input_path.stem}_fixed{input_path.suffix}"
        # 如果已存在，添加数字后缀
        counter = 1
        while output_path.exists():
            output_path = input_path.parent / f"{input_path.stem}_fixed_{counter}{input_path.suffix}"
            counter += 1
    else:
        output_path = Path(output_path)
    
    try:
        logger.info(f"开始修复 PDF: {input_path.name}")
        input_size = input_path.stat().st_size / 1024 / 1024
        logger.debug(f"输入文件大小: {input_size:.2f} MB")
        
        # 读取 PDF
        logger.info("读取 PDF 文件...")
        reader = PdfReader(input_path)
        page_count = len(reader.pages)
        
        if page_count == 0:
            logger.error("PDF 没有页面")
            reader = None  # 释放引用
            return False, None
        
        logger.info(f"总页数: {page_count}")
        
        # 创建新的 PDF
        logger.info("创建新的 PDF 文件...")
        writer = PdfWriter()
        
        # 复制所有页面
        logger.info("复制页面...")
        pages = []  # 先收集所有页面
        for i, page in enumerate(reader.pages):
            pages.append(page)
            if (i + 1) % 100 == 0:
                logger.info(f"已处理 {i + 1}/{page_count} 页")
        
        # 立即释放 reader 和文件句柄
        reader = None
        import gc
        gc.collect()  # 强制垃圾回收，释放文件句柄
        
        # 添加页面到 writer
        for page in pages:
            writer.add_page(page)
        
        # 写入修复后的 PDF
        logger.info("写入修复后的 PDF 文件...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        # 释放 writer
        writer = None
        gc.collect()  # 再次确保释放
        
        output_size = output_path.stat().st_size / 1024 / 1024
        logger.info(f"PDF 修复成功: {output_path.name} ({output_size:.2f} MB)")
        
        return True, str(output_path)
        
    except Exception as e:
        logger.error(f"修复 PDF 失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def precheck_and_fix_pdf(pdf_path: str, auto_fix: bool = True, timeout: int = 10, debug: bool = False) -> Tuple[str, bool]:
    """预检 PDF 文件，如果需要则自动修复。
    
    Args:
        pdf_path: PDF 文件路径
        auto_fix: 是否自动修复（默认 True）
        timeout: 预检超时时间（秒），默认 10 秒
        debug: 是否输出调试信息
        
    Returns:
        (actual_pdf_path, was_fixed)
        - actual_pdf_path: 实际使用的 PDF 文件路径（修复后的文件路径，带 _fixed 后缀）
        - was_fixed: 是否进行了修复
    """
    pdf_path = Path(pdf_path)
    
    if debug:
        logger.debug(f"预检 PDF 文件: {pdf_path}")
    
    # 检查 PDF 是否可以正常打开
    is_ok, error_msg = check_pdf_with_timeout(str(pdf_path), timeout=timeout)
    
    if is_ok:
        if debug:
            logger.debug("PDF 预检通过，无需修复")
        return str(pdf_path), False
    
    # PDF 有问题，需要修复
    logger.warning(f"PDF 预检发现问题: {error_msg}")
    
    if not auto_fix:
        logger.warning("自动修复已禁用，将尝试使用原始文件")
        return str(pdf_path), False
    
    # 在修复前，确保预检阶段的文件句柄完全释放
    import gc
    import time
    gc.collect()  # 强制垃圾回收
    time.sleep(0.5)  # 等待文件句柄释放（Windows 需要）
    gc.collect()  # 再次垃圾回收
    
    # 尝试修复
    if debug:
        logger.info("开始自动修复 PDF...")
    
    success, fixed_path = fix_pdf_xref(str(pdf_path))
    
    if success and fixed_path:
        if debug:
            logger.info(f"PDF 修复成功，将使用修复后的文件: {fixed_path}")
        return fixed_path, True
    else:
        logger.warning("PDF 修复失败，将尝试使用原始文件")
        return str(pdf_path), False


def main():
    """命令行入口函数"""
    global logger
    
    parser = argparse.ArgumentParser(
        description="PDF 预检和修复工具：检测并修复 PDF 文件的 xref 嵌套过深等问题",
        epilog="""
示例：
  # 预检 PDF 文件（仅检查，不修复）
  %(prog)s document.pdf --check-only
  
  # 预检并自动修复（如果发现问题）
  %(prog)s document.pdf
  
  # 预检并修复，指定输出文件
  %(prog)s document.pdf --output fixed.pdf
  
  # 强制修复（即使预检通过也修复）
  %(prog)s document.pdf --force-fix
  
  # 设置预检超时时间
  %(prog)s document.pdf --timeout 5
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="PDF 文件路径")
    parser.add_argument("--output", "-o", help="修复后的输出文件路径（可选，不指定则自动生成原文件名_fixed.pdf）")
    parser.add_argument("--check-only", action="store_true", 
                        help="仅检查，不修复（默认：检查到问题会自动修复）")
    parser.add_argument("--force-fix", action="store_true",
                        help="强制修复，即使预检通过也进行修复")
    parser.add_argument("--timeout", type=int, default=10,
                        help="预检超时时间（秒），默认 10 秒")
    parser.add_argument("--debug", action="store_true", help="打印调试信息")
    
    args = parser.parse_args()
    
    # 初始化日志
    logger = SimpleLogger(debug=args.debug)
    
    file_path = Path(args.file)
    
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return 1
    
    if file_path.suffix.lower() != '.pdf':
        logger.error(f"不是 PDF 文件: {file_path}")
        return 1
    
    # 检查依赖
    if pdfplumber is None:
        logger.warning("pdfplumber 未安装，预检功能不可用")
        logger.warning("安装命令: pip install pdfplumber")
        if not args.force_fix:
            logger.warning("提示: 可以使用 --force-fix 直接修复（不进行预检）")
            if PdfReader is None:
                logger.error("pypdf 也未安装，无法修复")
                return 1
    
    if PdfReader is None and args.force_fix:
        logger.error("pypdf 未安装，无法修复 PDF")
        logger.error("安装命令: pip install pypdf")
        return 1
    
    # 如果指定了输出文件，检查输出路径
    if args.output:
        output_path = Path(args.output)
        if output_path.exists() and not args.force_fix:
            logger.error(f"输出文件已存在: {output_path}")
            logger.error("使用 --force-fix 可以覆盖现有文件")
            return 1
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # 如果强制修复，直接修复
        if args.force_fix:
            logger.info("强制修复模式：直接修复 PDF 文件...")
            success, fixed_path = fix_pdf_xref(
                str(file_path),
                str(args.output) if args.output else None
            )
            if success:
                logger.info("=" * 80)
                logger.info("修复完成！")
                logger.info(f"修复后的文件: {fixed_path}")
                logger.info("=" * 80)
                return 0
            else:
                logger.error("修复失败")
                return 1
        
        # 如果仅检查，只进行预检
        if args.check_only:
            logger.info("预检模式：仅检查 PDF 文件...")
            is_ok, error_msg = check_pdf_with_timeout(str(file_path), timeout=args.timeout)
            if is_ok:
                logger.info("=" * 80)
                logger.info("✓ PDF 预检通过，文件正常")
                logger.info("=" * 80)
                return 0
            else:
                logger.warning("=" * 80)
                logger.warning("✗ PDF 预检发现问题")
                logger.warning(f"问题: {error_msg}")
                logger.warning("=" * 80)
                logger.warning("提示: 运行时不加 --check-only 参数可以自动修复")
                return 1
        
        # 默认：预检并自动修复
        logger.info("预检并自动修复模式...")
        actual_pdf_path, was_fixed = precheck_and_fix_pdf(
            str(file_path),
            auto_fix=not args.check_only,
            timeout=args.timeout,
            debug=args.debug
        )
        
        if was_fixed:
            logger.info("=" * 80)
            logger.info("✓ PDF 修复完成！")
            logger.info(f"修复后的文件: {actual_pdf_path}")
            logger.info("=" * 80)
            return 0
        else:
            logger.info("=" * 80)
            logger.info("✓ PDF 预检通过，无需修复")
            logger.info("=" * 80)
            return 0
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断操作")
        return 1
    except Exception as e:
        logger.error(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
