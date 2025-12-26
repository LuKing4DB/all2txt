"""
递归分割处理器模块
根据规则循环递归调用split进行文件分割
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# 使用相对导入，因为现在在 docx2data 包内
from .prompt_loader import read_prompt_template
from .openai_client import call_openai_api
from .local_pattern_matcher import match_pattern_locally
from ...split.lib.regex_splitter import RegexSplitter
from ...utils.logger import get_logger

logger = get_logger(__name__)


def process_recursive_split(
    txt_file_path: Path,
    base_url: str,
    api_key: str,
    model: str,
    prompt_file: str,
    sample_chars: int = 500,
    sample_chars_max: int = 8000,
    timeout: int = 120,
    max_depth: int = 1,
    current_depth: int = 0,
    project_root: Path = None,
    split_rules: Optional[List[Dict[str, Any]]] = None,
    max_file_length: int = 0,
    regex_config_file: str = None,
    used_patterns: Optional[List[str]] = None
) -> Path:
    """
    根据规则循环递归调用split进行文件分割
    
    Args:
        txt_file_path: TXT文件路径
        base_url: OpenAI API的base URL
        api_key: API密钥
        model: 模型名称
        prompt_file: 提示词文件路径
        sample_chars: 样本字符数，默认500
        timeout: API调用超时时间（秒）
        max_depth: 最大递归深度，默认1
        current_depth: 当前递归深度，默认0
        project_root: 项目根目录路径，用于调用其他模块
        split_rules: 分割规则列表，如果为None则自动生成
        max_file_length: 最大子文件长度（字符数），默认0表示不限制。如果文件长度小于等于此值，则跳过分割
        regex_config_file: 正则表达式配置文件路径，如果为None则使用默认路径
        
    Returns:
        分割结果目录路径
    """
    if project_root is None:
        # 假设当前文件在 src/pipeline/lib/ 下，项目根目录是 src/pipeline/ 的父目录的父目录
        project_root = Path(__file__).parent.parent.parent.parent

    # 初始化已用正则列表
    if used_patterns is None:
        used_patterns = []
    
    # 步骤1: 先检查递归深度，达到则跳过
    if current_depth >= max_depth:
        logger.info(f"达到最大递归深度 {max_depth}，跳过文件: {txt_file_path.name}")
        return txt_file_path.parent / (txt_file_path.stem + '_split')
    
    # 步骤2: 检查文件长度，没达到则跳过
    try:
        file_length = txt_file_path.stat().st_size
        # 读取文件内容以获取实际字符数（考虑编码）
        with open(txt_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            file_char_count = len(content)
    except Exception as e:
        logger.error(f"无法读取文件: {e}")
        raise
    
    if max_file_length > 0 and file_char_count <= max_file_length:
        logger.info(f"文件 {txt_file_path.name} 长度 {file_char_count} 字符 <= 最大文件长度 {max_file_length} 字符，跳过分割")
        return txt_file_path.parent / (txt_file_path.stem + '_split')
    
    # 步骤3: 达到条件，进行请求大模型并且切割
    logger.info(f"{'='*60}")
    logger.info(f"递归分割 - 深度 {current_depth + 1}/{max_depth}")
    logger.info(f"{'='*60}")
    logger.info(f"处理文件: {txt_file_path}")
    logger.info(f"文件大小: {file_length} 字节, {file_char_count} 字符")
    if max_file_length > 0:
        logger.info(f"文件长度 {file_char_count} 字符 > 最大文件长度 {max_file_length} 字符，继续分割")
    
    # 如果提供了分割规则，使用规则；否则自动生成
    if split_rules is None or current_depth >= len(split_rules):
        # 自动生成分割规则
        regex_pattern = _generate_split_pattern(
            txt_file_path,
            base_url,
            api_key,
            model,
            prompt_file,
            sample_chars,
            sample_chars_max,
            timeout,
            regex_config_file,
            current_depth,
            used_patterns
        )
    else:
        # 使用提供的规则
        rule = split_rules[current_depth]
        regex_pattern = rule.get('pattern')
        if regex_pattern is None:
            # 如果规则中没有pattern，自动生成
            regex_pattern = _generate_split_pattern(
                txt_file_path,
                base_url,
                api_key,
                model,
                prompt_file,
                sample_chars,
                sample_chars_max,
                timeout,
                regex_config_file,
                current_depth,
                used_patterns
            )
    
    # 检查是否返回None（表示跳过分割）
    if regex_pattern is None:
        logger.info(f"模型认为所有选项都不匹配，跳过分割，保留原文件: {txt_file_path}")
        return None  # 返回None表示跳过分割
    
    # 执行分割
    split_output_dir = _execute_split(
        txt_file_path,
        regex_pattern,
        project_root,
        current_depth
    )
    
    logger.info(f"分割完成: {split_output_dir}")
    
    # 对分割后的文件进行递归处理（递归深度和文件长度检查在函数内部进行）
    split_files = sorted(split_output_dir.glob('*.txt'))
    
    if split_files:
        logger.info(f"找到 {len(split_files)} 个分割文件，开始递归处理...")
        
        processed_count = 0
        skipped_count = 0
        
        for split_file in split_files:
            # 跳过0.txt和toc.txt文件，不进行递归切割
            if split_file.stem in {"0", "toc"}:
                logger.info(f"跳过{split_file.name}，不进行递归切割")
                skipped_count += 1
                continue
            
            # 递归处理（函数内部会先检查递归深度，再检查文件长度）
            try:
                result = process_recursive_split(
                    split_file,
                    base_url,
                    api_key,
                    model,
                    prompt_file,
                    sample_chars,
                    sample_chars_max,
                    timeout,
                    max_depth,
                    current_depth + 1,
                    project_root,
                    split_rules,
                    max_file_length,
                    regex_config_file,
                    used_patterns + [regex_pattern]
                )
                # 如果返回了结果，说明处理了（可能是分割，也可能是跳过）
                processed_count += 1
            except Exception as e:
                logger.warning(f"处理文件 {split_file.name} 时出错: {e}，跳过")
                skipped_count += 1
                continue
        
        logger.info(f"递归处理完成: 处理 {processed_count} 个文件，跳过 {skipped_count} 个文件")
    else:
        logger.info("未找到分割文件，停止递归")
    
    return split_output_dir


def _generate_split_pattern(
    txt_file_path: Path,
    base_url: str,
    api_key: str,
    model: str,
    prompt_file: str,
    sample_chars: int,
    sample_chars_max: int = 8000,
    timeout: int = 120,
    regex_config_file: str = None,
    current_depth: int = 0,
    used_patterns: Optional[List[str]] = None
) -> Optional[str]:
    """
    生成分割模式（正则表达式）
    
    Args:
        txt_file_path: TXT文件路径
        base_url: OpenAI API的base URL
        api_key: API密钥
        model: 模型名称
        prompt_file: 提示词文件路径
        sample_chars: 样本字符数（默认500）
        sample_chars_max: 最大样本字符数（默认8000），如果500字样本返回-1，使用此值重试
        timeout: API调用超时时间
        regex_config_file: 正则表达式配置文件路径
        current_depth: 当前递归深度，用于决定是否检测标题区域
        
    Returns:
        正则表达式模式
    """
    # 步骤1: 创建RegexSplitter实例用于提取样本（使用临时模式，不影响目录区域检测）
    # 使用一个不会匹配任何内容的模式，因为目录区域检测是基于关键字的，不依赖正则表达式
    # 在最外层递归（current_depth == 0）时，不检测标题区域
    detect_title_region = current_depth > 0
    try:
        temp_splitter = RegexSplitter(
            file_path=str(txt_file_path),
            pattern=r'^$',  # 临时模式：只匹配空行，不会影响目录区域检测
            output_dir=None,
            validate_sequence=False,  # 不需要序号校验
            create_output_dir=False,  # 不创建输出目录，因为只是用于提取样本
            detect_title_region=detect_title_region
        )
    except Exception as e:
        logger.error(f"创建RegexSplitter实例失败: {e}")
        raise
    
    # 提取8000字符样本
    sample, sample_line_numbers = temp_splitter.get_sample_text_with_line_numbers(sample_chars_max)
    logger.info(f"样本文件（{len(sample)} 字符，前10行）:")
    sample_lines = sample.split('\n')
    if sample_lines:
        for idx, line in enumerate(sample_lines[:10]):
            # 使用真实行号（原始文件中的行号）
            real_line_num = sample_line_numbers[idx] if idx < len(sample_line_numbers) else 0
            logger.info(f"  {real_line_num:2d}: {line}")
        if len(sample_lines) < 10:
            logger.info(f"  (共 {len(sample_lines)} 行)")
    
    # 使用本地验证方式生成正则表达式
    logger.info("使用本地验证方式匹配正则表达式...")
    local_match_result = match_pattern_locally(sample, regex_config_file)
    
    if local_match_result:
        option_id, regex_pattern, matched_line = local_match_result
        logger.info(f"✓ 本地验证成功：使用选项 {option_id}，匹配行 {matched_line}")
        # 如果该模式在上层已使用，返回None以跳过重复
        if used_patterns and regex_pattern in used_patterns:
            logger.warning(f"模式已在上层使用，跳过重复: {regex_pattern}")
            return None
        return regex_pattern
    else:
        logger.info("本地验证未找到匹配，跳过分割")
        return None


def _execute_split(
    txt_file_path: Path,
    regex_pattern: str,
    project_root: Path,
    current_depth: int = 0
) -> Path:
    """
    执行文件分割（使用面向对象方式）
    
    Args:
        txt_file_path: TXT文件路径
        regex_pattern: 正则表达式模式
        project_root: 项目根目录路径（保留参数以保持接口兼容性）
        current_depth: 当前递归深度，用于决定是否检测标题区域
        
    Returns:
        分割结果目录路径
    """
    logger.info("执行文件分割...")
    
    try:
        # 使用面向对象方式调用RegexSplitter
        # 在最外层递归（current_depth == 0）时，不检测标题区域
        detect_title_region = current_depth > 0
        splitter = RegexSplitter(
            file_path=str(txt_file_path),
            pattern=regex_pattern,
            output_dir=None,  # 使用默认输出目录（文件名_split）
            validate_sequence=True,  # 启用序号校验
            detect_title_region=detect_title_region
        )
        splitter.split()
        
        # 分割结果目录（默认输出到同级目录下的 文件名_split 文件夹）
        split_output_dir = txt_file_path.parent / (txt_file_path.stem + '_split')
        return split_output_dir
        
    except SystemExit as e:
        # RegexSplitter在错误时会调用sys.exit(1)，这里捕获并转换为异常
        logger.error(f"文件分割失败: {e}")
        raise RuntimeError(f"文件分割失败: {e}")
    except Exception as e:
        logger.error(f"文件分割失败: {e}")
        raise RuntimeError(f"文件分割失败: {e}")


def generate_outline(split_dir: Path, output_file: Path = None, split_dir_name: str = None, indent: str = "  ") -> None:
    """
    生成切分文件的大纲（outline）
    
    Args:
        split_dir: 切分结果目录（最外层split目录）
        output_file: 输出文件路径，如果为None则使用split_dir目录下的outline.txt
        split_dir_name: split目录的名称（用于在路径中包含根文件夹名），如果为None则从split_dir提取
        indent: 缩进字符串，默认两个空格
    """
    if output_file is None:
        output_file = split_dir / "outline.txt"
    
    if not split_dir.exists():
        logger.warning(f"目录不存在: {split_dir}")
        return
    
    # 获取split目录名（用于在路径中包含根文件夹名）
    if split_dir_name is None:
        split_dir_name = split_dir.name
    
    # 收集所有outline项，传递最外层目录和split目录名作为基准
    outline_lines = []
    _collect_outline_recursive(split_dir, split_dir, split_dir_name, outline_lines, indent, 0)
    
    # 写入outline文件
    if outline_lines:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(outline_lines))
            f.write('\n')
        logger.info(f"已生成大纲文件: {output_file}，共 {len(outline_lines)} 项")
    else:
        logger.warning(f"未找到任何切分文件，跳过生成大纲")


def _collect_outline_recursive(split_dir: Path, base_dir: Path, split_dir_name: str, outline_lines: list, indent: str, level: int) -> None:
    """
    递归收集outline项（只输出文件，不输出文件夹）
    使用父-子-父-子-孙的顺序：对于每个文件，先输出它本身，然后立即输出它的所有子文件（如果存在对应的split目录）
    
    Args:
        split_dir: 当前切分结果目录
        base_dir: 最外层split目录（用于计算相对路径）
        split_dir_name: split目录的名称（用于在路径中包含根文件夹名）
        outline_lines: 收集到的outline行列表
        indent: 缩进字符串
        level: 当前层级
    """
    # 获取当前目录的所有.txt文件，按文件名排序（数字优先）
    txt_files = sorted(split_dir.glob("*.txt"), key=lambda x: int(x.stem) if x.stem.isdigit() else float('inf'))
    
    for txt_file in txt_files:
        # 忽略0.txt、toc.txt、outline相关文件
        if (
            txt_file.stem == "0"
            or txt_file.name == "toc.txt"
            or txt_file.name == "outline.txt"
            or txt_file.name.endswith("_outline.txt")
        ):
            continue
        
        # 先输出文件本身
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line:
                    level_indent = indent * level
                    # 构建相对路径（相对于最外层split目录）
                    relative_path = txt_file.relative_to(base_dir)
                    # 在路径前加上split目录名（根文件夹名）
                    relative_path_str = f"{split_dir_name}/{relative_path}".replace('\\', '/')
                    outline_lines.append(f"{level_indent}{first_line}|{relative_path_str}")
        except Exception as e:
            logger.warning(f"无法读取文件 {txt_file}: {e}")
            continue
        
        # 检查是否有对应的split子目录（如1.txt对应1_split）
        file_num = txt_file.stem
        # 只有当文件名是纯数字时才检查对应的split目录
        if file_num.isdigit():
            subdir = split_dir / f"{file_num}_split"
            if subdir.exists() and subdir.is_dir():
                # 递归处理子目录，层级+1
                _collect_outline_recursive(subdir, base_dir, split_dir_name, outline_lines, indent, level + 1)

