"""PDF修复工具：使用Python修复PDF的xref表问题"""
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("错误: 需要安装 pypdf")
    print("安装命令: pip install pypdf")
    sys.exit(1)

from utils.logger import get_logger

logger = get_logger(__name__)


def fix_pdf_xref(input_path: str, output_path: str = None):
    """修复PDF的xref表问题
    
    通过重新读取和写入PDF，生成新的xref表，解决pdfplumber卡死问题。
    
    Args:
        input_path: 输入PDF文件路径
        output_path: 输出PDF文件路径，如果为None则自动生成
    """
    input_path = Path(input_path)
    if not input_path.exists():
        logger.error(f"文件不存在: {input_path}")
        return False
    
    if output_path is None:
        output_path = input_path.with_suffix('.fixed.pdf')
    else:
        output_path = Path(output_path)
    
    logger.info(f"输入文件: {input_path}")
    logger.info(f"文件大小: {input_path.stat().st_size / 1024 / 1024:.2f} MB")
    logger.info(f"输出文件: {output_path}")
    
    try:
        logger.info("读取PDF文件...")
        reader = PdfReader(input_path)
        page_count = len(reader.pages)
        logger.info(f"总页数: {page_count}")
        
        if page_count == 0:
            logger.error("PDF没有页面")
            return False
        
        logger.info("创建新的PDF文件...")
        writer = PdfWriter()
        
        # 复制所有页面
        logger.info("复制页面...")
        for i, page in enumerate(reader.pages):
            writer.add_page(page)
            if (i + 1) % 100 == 0:
                logger.info(f"已处理 {i + 1}/{page_count} 页")
        
        logger.info("写入修复后的PDF文件...")
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        output_size = output_path.stat().st_size / 1024 / 1024
        logger.info(f"成功生成修复后的PDF")
        logger.info(f"输出文件大小: {output_size:.2f} MB")
        logger.info(f"文件路径: {output_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.error("用法: python pdf_fix_tool.py <input_pdf> [output_pdf]")
        logger.error("\n示例:")
        logger.error("  python pdf_fix_tool.py data/tb3.pdf")
        logger.error("  python pdf_fix_tool.py data/tb3.pdf data/tb3_fixed.pdf")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = fix_pdf_xref(input_pdf, output_pdf)
    
    if success:
        logger.info("=" * 80)
        logger.info("修复完成！")
        logger.info("=" * 80)
        logger.info("现在可以使用pdfplumber打开修复后的文件:")
        if output_pdf:
            logger.info(f"  python -c \"import pdfplumber; pdf = pdfplumber.open('{output_pdf}'); print(len(pdf.pages))\"")
        else:
            fixed_path = Path(input_pdf).with_suffix('.fixed.pdf')
            logger.info(f"  python -c \"import pdfplumber; pdf = pdfplumber.open('{fixed_path}'); print(len(pdf.pages))\"")
    else:
        logger.error("修复失败，请检查错误信息")
        sys.exit(1)

