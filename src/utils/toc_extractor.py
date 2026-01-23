"""
目录提取辅助函数
从文本文件中提取目录区域并保存到 <文件名>_toc_行号开始_行号结束.txt
"""

import sys
from pathlib import Path

# 优先使用相对导入（推荐，作为包安装时使用）
try:
    from .toc_detector import (
        detect_toc_regions,
        detect_toc_region_by_keyword
    )
    from .logger import get_logger
except ImportError:
    # 如果相对导入失败，尝试使用包绝对导入（作为第三方依赖安装时）
    try:
        from all2txt.utils.toc_detector import (
            detect_toc_regions,
            detect_toc_region_by_keyword
        )
        from all2txt.utils.logger import get_logger
    except ImportError:
        # 如果包导入也失败，使用路径导入（直接运行脚本时）
        # 添加src目录到路径
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from utils.toc_detector import (
            detect_toc_regions,
            detect_toc_region_by_keyword
        )
        from utils.logger import get_logger

logger = get_logger(__name__)


def extract_toc_regions_to_file(text_file_path: Path, output_dir: Path = None, pattern: str = None, source_filename: str = None):
    """
    从文本文件中提取目录区域并保存到 <文件名>_toc_行号开始_行号结束.txt
    
    Args:
        text_file_path: 输入文本文件路径
        output_dir: 输出目录，如果为None则使用文本文件所在目录
        pattern: 用于基于关键字的目录检测的正则表达式模式，如果为None则使用默认模式
        source_filename: 源文件名（不含扩展名），如果为None则从text_file_path提取
        
    Returns:
        bool: 如果成功提取并保存目录返回True，否则返回False
    """
    if not text_file_path.exists():
        logger.warning(f"文本文件不存在，跳过目录提取: {text_file_path}")
        return False
    
    # 读取文件内容
    try:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        logger.warning(f"读取文本文件失败，跳过目录提取: {e}")
        return False
    
    if not lines:
        logger.debug("文本文件为空，跳过目录提取")
        return False
    
    # 确定输出目录
    if output_dir is None:
        output_dir = text_file_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 确定源文件名（用于文件命名）
    if source_filename is None:
        source_filename = text_file_path.stem
    
    # 方法1: 基于关键字的目录检测（如果提供了pattern或使用默认模式）
    toc_region_lines = set()
    if pattern is not None:
        # 使用提供的pattern
        toc_region_lines = detect_toc_region_by_keyword(lines, pattern)
        if toc_region_lines:
            logger.debug(f"基于关键字检测到 {len(toc_region_lines)} 行目录区域（使用自定义pattern）")
    else:
        # 尝试使用默认模式（匹配空行，会使用常见目录形式pattern）
        toc_region_lines = detect_toc_region_by_keyword(lines, r'^$')
        if toc_region_lines:
            logger.debug(f"基于关键字检测到 {len(toc_region_lines)} 行目录区域（默认模式）")
    
    # 如果基于关键字的方法没有找到，尝试基于末尾数字的检测
    if not toc_region_lines:
        logger.debug("基于关键字的检测未找到目录，尝试基于末尾数字的检测...")
        toc_region_lines = detect_toc_regions(lines, min_consecutive=2)
        if toc_region_lines:
            logger.debug(f"基于末尾数字检测到 {len(toc_region_lines)} 行目录区域")
    
    if not toc_region_lines:
        logger.debug("未检测到目录区域，跳过目录文件生成")
        return False
    
    # 找出连续的区域范围
    sorted_toc_lines = sorted(toc_region_lines)
    
    # 找出所有连续的区域段
    regions = []
    if sorted_toc_lines:
        current_start = sorted_toc_lines[0]
        current_end = sorted_toc_lines[0]
        
        for i in range(1, len(sorted_toc_lines)):
            if sorted_toc_lines[i] == sorted_toc_lines[i-1] + 1:
                # 连续的行
                current_end = sorted_toc_lines[i]
            else:
                # 不连续，保存当前区域并开始新区域
                regions.append((current_start, current_end))
                current_start = sorted_toc_lines[i]
                current_end = sorted_toc_lines[i]
        
        # 添加最后一个区域
        regions.append((current_start, current_end))
    
    # 为每个连续区域生成文件
    files_generated = []
    for region_start, region_end in regions:
        # 提取该区域的目录行
        toc_contents = []
        for line_num in range(region_start, region_end + 1):
            if line_num < len(lines):
                line_content = lines[line_num].rstrip()  # 去除右侧空白但保留左侧缩进
                if line_content.strip():  # 跳过空行
                    toc_contents.append(line_content)
        
        if toc_contents:
            # 生成文件名：<文件名>_toc_行号开始_行号结束.txt（行号从1开始显示）
            # 注意：内部行号是从0开始的，但文件名中显示从1开始（更符合用户习惯）
            output_filename = f"{source_filename}_toc_{region_start + 1}_{region_end + 1}.txt"
            output_path = output_dir / output_filename
            
            # 写入文件
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    for line in toc_contents:
                        f.write(line + '\n')
                
                files_generated.append((output_filename, region_start + 1, region_end + 1, len(toc_contents)))
                logger.info(f"已生成目录文件: {output_filename} (行号 {region_start + 1}-{region_end + 1}, {len(toc_contents)} 行)")
            except Exception as e:
                logger.warning(f"写入目录文件失败 {output_filename}: {e}")
    
    if files_generated:
        return True
    else:
        logger.debug("提取的目录内容为空")
        return False

