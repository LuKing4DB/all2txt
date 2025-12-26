"""
OpenAI客户端模块
用于调用OpenAI API生成正则表达式
"""

import sys
import time
import re
from pathlib import Path
from typing import Tuple, Optional

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# 添加lib目录到路径，以便导入其他lib模块
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from regex_loader import load_regex_patterns, convert_option_to_regex

logger = get_logger(__name__)


def build_prompt(sample: str, prompt_template: str) -> str:
    """
    构建完整的提示词，将样本插入到模板中
    
    Args:
        sample: 文本样本
        prompt_template: 提示词模板
        
    Returns:
        完整的提示词
    """
    start_tag = "<开头样本>"
    end_tag = "</开头样本>"
    
    if start_tag in prompt_template and end_tag in prompt_template:
        # 找到开始和结束标签的位置
        start_idx = prompt_template.find(start_tag)
        end_idx = prompt_template.find(end_tag)
        if start_idx < end_idx:
            # 保留开始标签，替换中间内容，保留结束标签
            full_prompt = (
                prompt_template[:start_idx + len(start_tag)] + 
                "\n" + sample + "\n" + 
                prompt_template[end_idx:]
            )
        else:
            # 如果标签顺序不对，使用简单替换
            full_prompt = prompt_template.replace(start_tag + "\n", start_tag + "\n" + sample + "\n").replace(end_tag, end_tag)
    else:
        # 如果没有找到标签，尝试简单替换
        full_prompt = prompt_template.replace(start_tag, start_tag + "\n" + sample + "\n").replace(end_tag, end_tag)
    
    # 在提示词结尾添加 /nothink 指令
    full_prompt = full_prompt.rstrip() + "\n/nothink"
    
    return full_prompt


def clean_regex_response(response_text: str) -> Tuple[str, int]:
    """
    清理AI返回的正则表达式响应
    
    Args:
        response_text: AI返回的原始文本
        
    Returns:
        (清理后的选项编号或"-1", 置信度) 元组，置信度固定为-1（已废弃，保留以保持接口兼容）
        如果选项编号是-1，表示所有选项都不匹配，应该跳过分割
    """
    regex_pattern = response_text.strip()
    confidence = -1  # 置信度已废弃，固定为-1
    
    # 清理响应，移除可能的代码块标记
    regex_pattern = regex_pattern.replace("```", "").strip()
    regex_pattern = regex_pattern.replace("regex", "").strip()
    regex_pattern = regex_pattern.replace("python", "").strip()
    
    # 如果包含冒号，可能是旧格式（选项编号:置信度），只取第一部分
    if ':' in regex_pattern:
        parts = regex_pattern.split(':', 1)
        if len(parts) == 2:
            regex_pattern = parts[0].strip()
    
    # 检查是否是-1（表示都不匹配）
    if regex_pattern == "-1":
        return "-1", confidence
    
    return regex_pattern, confidence


def get_regex_map(regex_config_file: str = None) -> dict:
    """
    获取正则表达式映射字典
    
    Args:
        regex_config_file: 正则表达式配置文件路径，如果为None则使用默认路径
        
    Returns:
        正则表达式映射字典
    """
    try:
        return load_regex_patterns(regex_config_file)
    except Exception as e:
        logger.warning(f"加载正则表达式配置失败，使用默认配置: {e}")
        # 返回默认配置作为后备
        return {
            "1": r"^(第[一二三四五六七八九十百千]+章).*",
            "2": r"^(第[一二三四五六七八九十百千]+卷).*",
            "3": r"^[一二三四五六七八九十百千]+、\S.*",
            "4": r"^[0-9]+[^.\d\s]\S.*",
            "5": r"^[0-9]+\.[^.\d\s]\S.*",
            "6": r"^[0-9]+\.[0-9]+\.[^.\d\s]\S.*",
            "7": r"^[0-9]+\.[0-9]+\.[0-9]+\.[^.\d\s]\S.*",
            "8": r"^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\.[^.\d\s]\S.*",
        }


def validate_regex_against_sample(regex_pattern: str, sample: str) -> Tuple[bool, int, list]:
    """
    验证正则表达式是否能匹配样本中的第一层级标题
    
    Args:
        regex_pattern: 正则表达式模式
        sample: 样本文本
        
    Returns:
        (是否匹配, 匹配的行数, 匹配的行列表) 元组
    """
    import re
    try:
        regex = re.compile(regex_pattern)
        lines = sample.split('\n')
        matches = []
        
        # 检查所有行（包括第一行），因为第一行可能就是标题
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped:
                match = regex.search(stripped)
                if match and match.start() == 0:
                    matches.append((i+1, stripped[:50]))
        
        return len(matches) > 0, len(matches), matches
    except Exception as e:
        logger.warning(f"验证正则表达式时出错: {e}")
        return False, 0, []


def find_best_matching_option(sample: str, regex_config_file: str = None) -> Tuple[str, int, list, str]:
    """
    自动查找最匹配的正则表达式选项
    
    Args:
        sample: 样本文本
        regex_config_file: 正则表达式配置文件路径
        
    Returns:
        (最佳匹配的正则表达式, 匹配的行数, 匹配的行列表, 选项编号) 元组
    """
    import re
    regex_map = get_regex_map(regex_config_file)
    lines = sample.split('\n')
    
    best_pattern = None
    best_match_count = 0
    best_matches = []
    best_option_id = None
    
    # 测试所有选项
    for option_id, pattern in sorted(regex_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        try:
            regex = re.compile(pattern)
            matches = []
            
            for i, line in enumerate(lines):
                if i == 0:  # 跳过第一行
                    continue
                stripped = line.lstrip()
                if stripped:
                    match = regex.search(stripped)
                    if match and match.start() == 0:
                        matches.append((i+1, stripped[:50]))
            
            match_count = len(matches)
            # 选择匹配行数最多的选项（但至少匹配1行）
            if match_count > best_match_count:
                best_match_count = match_count
                best_pattern = pattern
                best_matches = matches
                best_option_id = option_id
        except Exception as e:
            logger.debug(f"测试选项 {option_id} 时出错: {e}")
            continue
    
    return best_pattern, best_match_count, best_matches, best_option_id


def call_openai_api(sample: str, prompt_template: str, base_url: str, api_key: str, model: str, timeout: int = 120, regex_config_file: str = None, exclude_options: list = None, retry_count: int = 0, max_retries: int = 1, prompt_file: str = None) -> Optional[str]:
    """
    调用OpenAI接口生成正则表达式
    
    Args:
        sample: 文本样本
        prompt_template: 提示词模板（如果exclude_options不为None，需要重新加载）
        base_url: OpenAI API的base URL
        api_key: API密钥
        model: 模型名称
        timeout: 超时时间（秒），默认120秒
        regex_config_file: 正则表达式配置文件路径
        exclude_options: 要排除的选项编号列表
        retry_count: 当前重试次数
        max_retries: 最大重试次数
        prompt_file: 提示词文件路径（用于重新加载时排除选项）
        
    Returns:
        生成的正则表达式
        
    Raises:
        SystemExit: 如果未安装openai库或API调用失败
    """
    try:
        from openai import OpenAI
        import httpx
    except ImportError:
        logger.error("未安装openai库，请运行: pip install openai")
        sys.exit(1)
    
    # 如果指定了要排除的选项，重新加载提示词模板（排除错误选项）
    if exclude_options and prompt_file:
        from prompt_loader import read_prompt_template as reload_prompt_template
        logger.info(f"🔧 重新加载提示词，排除错误选项: {exclude_options}")
        prompt_template = reload_prompt_template(prompt_file, regex_config_file, exclude_options=exclude_options)
    
    # 构建完整的提示词
    full_prompt = build_prompt(sample, prompt_template)
    
    # 创建OpenAI客户端，设置超时
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=httpx.Timeout(timeout, connect=10.0)  # 总超时120秒，连接超时10秒
    )
    
    logger.info(f"调用OpenAI API (模型: {model}, 样本: {len(sample)} 字符, 超时: {timeout}秒)...")
    start_time = time.time()
    
    try:
        logger.debug("发送请求中...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            temperature=0.1,  # 使用较低的温度以获得更稳定的结果
            max_tokens=100  # 限制最大token数，避免过长响应
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"✓ API调用成功 (耗时: {elapsed_time:.2f} 秒)")
        
        # 检查响应是否有效
        if not response or not response.choices:
            logger.error("✗ 错误: API返回空响应")
            sys.exit(1)
        
        message = response.choices[0].message
        if not message:
            logger.error("✗ 错误: API返回的消息为空")
            sys.exit(1)
        
        # 尝试从多个可能的字段获取响应内容
        regex_pattern = None
        if message.content:
            regex_pattern = message.content.strip()
        elif hasattr(message, 'reasoning_content') and message.reasoning_content:
            regex_pattern = message.reasoning_content.strip()
        elif hasattr(message, 'reasoning') and message.reasoning:
            regex_pattern = message.reasoning.strip()
        
        if not regex_pattern:
            logger.error("✗ 错误: API返回的响应内容为空")
            logger.error(f"  完成原因: {response.choices[0].finish_reason}")
            sys.exit(1)
        
        # 清理响应
        regex_pattern, _ = clean_regex_response(regex_pattern)
        
        # 检查是否是-1（表示所有选项都不匹配）
        if regex_pattern == "-1":
            logger.info(f"模型返回-1：认为所有选项都不匹配样本中的第一层级标题")
            logger.info(f"跳过分割，保留原文件")
            return None  # 返回None表示跳过分割
        
        # 如果返回的是选项编号，转换为对应的正则表达式
        original_pattern = regex_pattern
        regex_map = get_regex_map(regex_config_file)
        regex_pattern = convert_option_to_regex(regex_pattern, regex_map)
        
        if regex_pattern != original_pattern:
            logger.info(f"生成的正则表达式: {regex_pattern} (从选项 {original_pattern} 转换)")
        else:
            logger.info(f"生成的正则表达式: {regex_pattern}")
        
        # 后验证：实际测试正则表达式是否能匹配样本中的标题
        can_match, match_count, matched_lines = validate_regex_against_sample(regex_pattern, sample)
        if not can_match:
            logger.error(f"✗ 警告：生成的正则表达式无法匹配样本中的任何标题行！")
            logger.error(f"  这表明模型的选择可能是错误的")
            logger.info(f"跳过分割，保留原文件")
            return None  # 返回None表示跳过分割
            
            # 暂时取消重试逻辑
            # # 自动修复：排除错误选项，让模型重新选择
            # if retry_count < max_retries:
            #     # 获取错误选项的编号
            #     wrong_option_id = original_pattern if original_pattern in regex_map else None
            #     if wrong_option_id:
            #         logger.info(f"🔧 自动修复：排除错误选项 {wrong_option_id}，让模型重新选择...")
            #         exclude_options = [wrong_option_id]
            #         # 递归调用，但排除错误选项
            #         return call_openai_api(
            #             sample, prompt_template, base_url, api_key, model, timeout, 
            #             regex_config_file, exclude_options=exclude_options, 
            #             retry_count=retry_count + 1, max_retries=max_retries,
            #             prompt_file=prompt_file
            #         )
            #     else:
            #         logger.warning(f"  无法确定错误选项编号，尝试查找最匹配的选项...")
            #         # 如果无法确定错误选项，回退到查找最匹配选项的方式
            #         best_pattern, best_match_count, best_matches, best_option_id = find_best_matching_option(sample, regex_config_file)
            #         if best_pattern and best_match_count > 0:
            #             logger.info(f"✓ 找到更匹配的选项：选项 {best_option_id}，能匹配 {best_match_count} 行")
            #             logger.info(f"  自动使用选项 {best_option_id} 替换原选择")
            #             regex_pattern = best_pattern
            #         else:
            #             logger.error(f"  ✗ 无法找到匹配的选项，请手动检查样本内容和正则表达式配置")
            # else:
            #     logger.error(f"  ✗ 已达到最大重试次数（{max_retries}），无法自动修复")
            #     # 最后尝试：查找最匹配的选项
            #     best_pattern, best_match_count, best_matches, best_option_id = find_best_matching_option(sample, regex_config_file)
            #     if best_pattern and best_match_count > 0:
            #         logger.info(f"✓ 找到更匹配的选项：选项 {best_option_id}，能匹配 {best_match_count} 行")
            #         logger.info(f"  自动使用选项 {best_option_id} 替换原选择")
            #         regex_pattern = best_pattern
            #     else:
            #         logger.error(f"  ✗ 无法找到匹配的选项，请手动检查样本内容和正则表达式配置")
        elif match_count > 0:
            logger.info(f"✓ 验证通过：正则表达式能匹配样本中的 {match_count} 行")
        
        return regex_pattern
        
    except TimeoutError as e:
        elapsed_time = time.time() - start_time
        logger.error(f"\n✗ 错误: API调用超时 (已等待 {elapsed_time:.2f} 秒)")
        logger.error("建议:")
        logger.error("  - 检查网络连接")
        logger.error("  - 检查API服务是否正常")
        logger.error("  - 尝试增加超时时间")
        sys.exit(1)
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"\n✗ 错误: 调用OpenAI API失败 (耗时: {elapsed_time:.2f} 秒)")
        logger.error(f"错误类型: {type(e).__name__}")
        logger.error(f"错误信息: {e}")
        
        # 提供常见错误的解决建议
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            logger.error("\n建议:")
            logger.error("  - 检查API密钥是否正确")
            logger.error("  - 确认API密钥是否有效且未过期")
        elif "404" in error_str or "not found" in error_str:
            logger.error("\n建议:")
            logger.error("  - 检查base_url是否正确")
            logger.error("  - 检查模型名称是否正确")
        elif "connection" in error_str or "timeout" in error_str or "timed out" in error_str:
            logger.error("\n建议:")
            logger.error("  - 检查网络连接")
            logger.error("  - 检查base_url是否可访问")
            logger.error("  - 如果是本地模型，确认服务是否已启动")
            logger.error("  - 尝试增加超时时间")
        elif "rate limit" in error_str:
            logger.error("\n建议:")
            logger.error("  - 等待一段时间后重试")
            logger.error("  - 检查API配额是否已用完")
        
        import traceback
        logger.error("\n详细错误信息:")
        traceback.print_exc()
        sys.exit(1)

