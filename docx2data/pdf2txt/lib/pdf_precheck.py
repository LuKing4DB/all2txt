"""PDF 预检和自动修复模块

检测 PDF 文件是否有 xref 嵌套过深等问题，并在需要时自动修复。
"""
from __future__ import annotations

import signal
import tempfile
import threading
from pathlib import Path
from typing import Optional, Tuple

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None
    PdfWriter = None

from utils.logger import get_logger

logger = get_logger(__name__)


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
        logger.warning("pypdf 未安装，无法修复 PDF")
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
        if logger:
            logger.info(f"开始修复 PDF: {input_path.name}")
            logger.debug(f"输入文件大小: {input_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # 读取 PDF
        reader = PdfReader(input_path)
        page_count = len(reader.pages)
        
        if page_count == 0:
            logger.error("PDF 没有页面")
            return False, None
        
        if logger:
            logger.debug(f"总页数: {page_count}")
        
        # 创建新的 PDF
        writer = PdfWriter()
        
        # 复制所有页面
        for i, page in enumerate(reader.pages):
            writer.add_page(page)
            if logger and (i + 1) % 100 == 0:
                logger.debug(f"已处理 {i + 1}/{page_count} 页")
        
        # 写入修复后的 PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        if logger:
            output_size = output_path.stat().st_size / 1024 / 1024
            logger.info(f"PDF 修复成功: {output_path.name} ({output_size:.2f} MB)")
        
        return True, str(output_path)
        
    except Exception as e:
        if logger:
            logger.error(f"修复 PDF 失败: {e}", exc_info=True)
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
        - actual_pdf_path: 实际使用的 PDF 文件路径（可能是修复后的文件）
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
    if debug or True:  # 总是输出警告
        logger.warning(f"PDF 预检发现问题: {error_msg}")
    
    if not auto_fix:
        logger.warning("自动修复已禁用，将尝试使用原始文件")
        return str(pdf_path), False
    
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

