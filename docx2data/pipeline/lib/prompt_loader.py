"""
提示词加载器模块
用于读取和加载提示词模板文件，并动态插入正则表达式选项
"""

from pathlib import Path
import sys

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# 添加lib目录到路径，以便导入其他lib模块
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from regex_loader import load_regex_patterns, load_regex_patterns_with_descriptions, get_regex_options_text
from utils.logger import get_logger

logger = get_logger(__name__)


def read_prompt_template(prompt_file: str, regex_config_file: str = None, exclude_options: list = None) -> str:
    """
    读取提示词模板文件，并动态插入正则表达式选项
    
    Args:
        prompt_file: 提示词文件路径（可以是相对路径或绝对路径）
        regex_config_file: 正则表达式配置文件路径，如果为None则使用默认路径
        
    Returns:
        处理后的提示词模板内容（字符串），已插入正则表达式选项
        
    Raises:
        FileNotFoundError: 如果提示词文件不存在
    """
    prompt_path = Path(prompt_file)
    
    # 如果文件不存在，尝试相对于脚本目录查找
    if not prompt_path.exists():
        # 尝试相对于当前模块的父目录查找
        script_dir = Path(__file__).parent.parent
        prompt_path = script_dir / prompt_file
        
        # 如果还是不存在，尝试向后兼容的路径（旧版本在根目录）
        if not prompt_path.exists():
            # 如果传入的是 prompt_select（旧格式），尝试在 prompt/ 目录下查找
            if prompt_file == "prompt_select":
                prompt_path = script_dir / "prompt" / "prompt_select"
            # 如果传入的是相对路径但不包含 prompt/，也尝试添加
            elif not "prompt" in str(prompt_file) and not Path(prompt_file).is_absolute():
                prompt_path = script_dir / "prompt" / prompt_file
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {prompt_file}")
    
    # 读取提示词模板
    with open(prompt_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # 检查模板中是否有正则表达式选项占位符
    placeholder = "{{regex_options}}"
    if placeholder in template:
        # 加载正则表达式配置（包含描述信息）
        try:
            regex_map, descriptions_map = load_regex_patterns_with_descriptions(regex_config_file)
            # 只显示序号和描述，不显示正则表达式模式，避免转义问题
            # 如果指定了要排除的选项，则排除它们
            regex_options_text = get_regex_options_text(regex_map, descriptions_map, exclude_options=exclude_options)
            
            # 替换占位符
            template = template.replace(placeholder, regex_options_text)
            if exclude_options:
                logger.debug(f"已动态插入正则表达式选项到提示词模板（排除选项: {exclude_options}）")
            else:
                logger.debug("已动态插入正则表达式选项到提示词模板（仅显示序号和描述）")
        except Exception as e:
            logger.warning(f"加载正则表达式配置失败，使用模板中的原始内容: {e}")
    
    return template

