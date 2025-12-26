"""
文档转换器模块
将 DOCX 或 PDF 文件转换为 TXT 格式
"""

import subprocess
import sys
from pathlib import Path

from ...utils.logger import get_logger

logger = get_logger(__name__)


def convert_document_to_txt(
    file_path: str,
    output_dir: str = None,
    project_root: Path = None
) -> Path:
    """
    将文档（DOCX 或 PDF）转换为 TXT 文件
    
    Args:
        file_path: 输入文档文件路径（支持 .docx 或 .pdf）
        output_dir: 输出目录，如果为None则使用默认目录（文件同目录下的同名文件夹）
        project_root: 项目根目录路径，用于调用其他模块
        
    Returns:
        生成的TXT文件路径
        
    Raises:
        FileNotFoundError: 如果输入文件不存在
        ValueError: 如果文件格式不支持
        RuntimeError: 如果转换失败
    """
    input_file = Path(file_path)
    
    if not input_file.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    file_suffix = input_file.suffix.lower()
    if file_suffix not in ['.docx', '.pdf']:
        raise ValueError(f"不支持的文件格式: {file_suffix}。支持格式: .docx, .pdf")
    
    # 确定输出目录
    if output_dir is None:
        txt_output_dir = input_file.parent / input_file.stem
    else:
        txt_output_dir = Path(output_dir)
    
    # 如果没有提供项目根目录，尝试自动检测
    if project_root is None:
        # 假设当前文件在 docx2data/pipeline/lib/ 下，项目根目录是 docx2data/pipeline/lib/ 的父目录的父目录的父目录
        project_root = Path(__file__).parent.parent.parent.parent.parent
    
    doc_type = "DOCX" if file_suffix == '.docx' else "PDF"
    logger.info(f"将{doc_type}转换为TXT...")
    
    if file_suffix == '.docx':
        # 处理 DOCX 文件
        txt_output_path = txt_output_dir / (input_file.stem + '.txt')
        
        # 使用命令行调用 docx2txt/main.py（现在在 docx2data 包内）
        # 尝试多个可能的路径
        current_file = Path(__file__)
        possible_paths = [
            current_file.parent.parent.parent / 'docx2txt' / 'main.py',  # 安装后
            current_file.parent.parent.parent.parent / 'docx2data' / 'docx2txt' / 'main.py',  # 开发模式
        ]
        docx2txt_script = None
        for path in possible_paths:
            if path.exists():
                docx2txt_script = path
                break
        
        if docx2txt_script is None:
            # 如果都找不到，使用相对路径
            docx2txt_script = current_file.parent.parent.parent / 'docx2txt' / 'main.py'
        cmd = [
            sys.executable,
            str(docx2txt_script),
            str(input_file),
            '-o',
            str(txt_output_dir)
        ]
        
        logger.debug(f"执行命令: {' '.join(cmd)}")
        # result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', cwd=str(project_root))
        result = subprocess.run(cmd, capture_output=True, text=True, encoding=sys.getdefaultencoding(), errors='replace', cwd=str(project_root))
        
        if result.returncode != 0:
            logger.error(f"DOCX转换失败")
            if result.stderr:
                logger.error(f"错误信息: {result.stderr}")
            if result.stdout:
                logger.error(f"输出信息: {result.stdout}")
            raise RuntimeError(f"DOCX转换失败: {result.stderr}")
        
        # 重新获取实际生成的txt文件路径（因为docx_to_txt_simple可能会调整路径）
        actual_txt_dir = txt_output_dir / input_file.stem
        actual_txt_path = actual_txt_dir / (input_file.stem + '.txt')
        
        # 如果实际路径不存在，尝试使用原始路径
        if not actual_txt_path.exists():
            if txt_output_path.exists():
                actual_txt_path = txt_output_path
            else:
                raise RuntimeError(f"DOCX转换失败：未找到生成的TXT文件")
        
        txt_output_path = actual_txt_path
    else:
        # 处理 PDF 文件
        txt_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用命令行调用 pdf2txt/main.py（现在在 docx2data 包内）
        # 尝试多个可能的路径
        current_file = Path(__file__)
        possible_paths = [
            current_file.parent.parent.parent / 'pdf2txt' / 'main.py',  # 安装后
            current_file.parent.parent.parent.parent / 'docx2data' / 'pdf2txt' / 'main.py',  # 开发模式
        ]
        pdf2txt_script = None
        for path in possible_paths:
            if path.exists():
                pdf2txt_script = path
                break
        
        if pdf2txt_script is None:
            # 如果都找不到，使用相对路径
            pdf2txt_script = current_file.parent.parent.parent / 'pdf2txt' / 'main.py'
        cmd = [
            sys.executable,
            str(pdf2txt_script),
            str(input_file),
            '--out',
            str(txt_output_dir)
        ]
        
        logger.debug(f"执行命令: {' '.join(cmd)}")
        # result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', cwd=str(project_root))
        result = subprocess.run(cmd, capture_output=True, text=True, encoding=sys.getdefaultencoding(), errors='replace', cwd=str(project_root))
        
        if result.returncode != 0:
            logger.error(f"PDF转换失败")
            if result.stderr:
                logger.error(f"错误信息: {result.stderr}")
            if result.stdout:
                logger.error(f"输出信息: {result.stdout}")
            raise RuntimeError(f"PDF转换失败: {result.stderr}")
        
        # PDF 转换后，文件名为 text.txt，需要重命名为原文件名.txt
        text_file = txt_output_dir / 'text.txt'
        txt_output_path = txt_output_dir / (input_file.stem + '.txt')
        
        if text_file.exists():
            if txt_output_path.exists():
                txt_output_path.unlink()
            text_file.rename(txt_output_path)
        else:
            raise RuntimeError("PDF 转换失败：未生成 text.txt 文件")
    
    logger.info(f"转换完成: {txt_output_path}")
    return txt_output_path

