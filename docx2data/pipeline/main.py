"""
文档处理脚本（使用AI生成正则表达式）
支持 DOCX 和 PDF 格式
流程：
1. 将文档转换为txt（使用document_converter模块）
2. 根据规则循环递归调用split进行分割（使用recursive_splitter模块）
"""

import argparse
import sys
from pathlib import Path

# 使用相对导入，因为现在在 docx2data 包内
from .lib.document_converter import convert_document_to_txt
from .lib.recursive_splitter import process_recursive_split, generate_outline
from .lib.config_loader import load_config, get_config_value
from ..utils.logger import get_logger

# 获取项目根目录（用于某些路径计算）
current_dir = Path(__file__).parent           # .../docx2data/pipeline
project_root = current_dir.parent.parent      # 项目根目录（从 docx2data/pipeline 向上两级）

logger = get_logger(__name__)


def run_pipeline(
    file_path: str,
    base_url: str,
    api_key: str,
    model: str,
    prompt_file: str = None,
    sample_chars: int = 500,
    sample_chars_max: int = 8000,
    output_dir: str = None,
    timeout: int = 120,
    max_depth: int = 1,
    max_file_length: int = 0,
    regex_config_file: str = None
):
    """
    处理文档的完整流程（支持 DOCX 和 PDF）
    
    Args:
        file_path: 文档文件路径（支持 .docx 或 .pdf）
        base_url: OpenAI API的base URL
        api_key: API密钥
        model: 模型名称
        prompt_file: 提示词文件路径，如果为None则使用默认路径（脚本目录下的prompt/prompt_select）
        sample_chars: 样本字符数，默认500
        output_dir: 输出目录，如果为None则使用默认目录
        timeout: API调用超时时间（秒）
        max_depth: 最大递归深度，默认1
        max_file_length: 最大子文件长度（字符数），默认0表示不限制。如果文件长度小于等于此值，则跳过分割
        regex_config_file: 正则表达式配置文件路径，如果为None则使用默认路径（config/regex_patterns.yaml）
    """
    input_file = Path(file_path)
    
    if not input_file.exists():
        logger.error(f"文件不存在: {file_path}")
        sys.exit(1)
    
    file_suffix = input_file.suffix.lower()
    if file_suffix not in ['.docx', '.pdf']:
        logger.error(f"不支持的文件格式: {file_suffix}。支持格式: .docx, .pdf")
        sys.exit(1)
    
    # 如果未指定提示词文件，使用脚本目录下的默认文件
    if prompt_file is None:
        script_dir = Path(__file__).parent
        prompt_file = str(script_dir / "prompt" / "prompt_select")
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent.parent
    
    doc_type = "DOCX" if file_suffix == '.docx' else "PDF"
    logger.info(f"{'='*60}")
    logger.info(f"开始处理{doc_type}文档")
    logger.info(f"{'='*60}")
    logger.info(f"输入文件: {file_path}")
    logger.info(f"提示词文件: {prompt_file}")
    logger.info(f"样本字符数: {sample_chars}")
    logger.info(f"最大递归深度: {max_depth}")
    logger.info(f"最大子文件长度: {max_file_length if max_file_length > 0 else '不限制'}")
    logger.info("")
    
    # 步骤1: 将文档转换为txt
    logger.info(f"步骤1: 将{doc_type}转换为TXT...")
    try:
        txt_output_path = convert_document_to_txt(
            file_path,
            output_dir,
            project_root
        )
    except Exception as e:
        logger.error(f"文档转换失败: {e}")
        sys.exit(1)
    
    logger.info("")
    
    # 步骤2: 根据规则循环递归调用split进行分割
    logger.info("步骤2: 根据规则循环递归调用split进行分割...")
    try:
        split_output_dir = process_recursive_split(
            txt_output_path,
            base_url,
            api_key,
            model,
            prompt_file,
            sample_chars,
            sample_chars_max,
            timeout,
            max_depth,
            current_depth=0,
            project_root=project_root,
            max_file_length=max_file_length,
            regex_config_file=regex_config_file
        )
    except Exception as e:
        logger.error(f"文件分割失败: {e}")
        sys.exit(1)
    
    logger.info("")
    
    # 步骤3: 生成outline
    logger.info("步骤3: 生成文件大纲...")
    try:
        # outline文件保存在输入文件的同级目录下，命名为 文件名_outline.txt
        if split_output_dir and split_output_dir.exists():
            outline_file = txt_output_path.parent / f"{txt_output_path.stem}_outline.txt"
            # split_dir_name是split目录的名称（如1_split），用于在路径中包含根文件夹名
            split_dir_name = split_output_dir.name
            generate_outline(split_output_dir, outline_file, split_dir_name)
            logger.info(f"大纲文件已生成: {outline_file}")
        else:
            logger.warning(f"分割结果目录不存在，跳过生成大纲: {split_output_dir}")
    except Exception as e:
        logger.warning(f"生成大纲失败: {e}")
    
    logger.info("")
    logger.info(f"{'='*60}")
    logger.info(f"处理完成!")
    logger.info(f"{'='*60}")
    logger.info(f"TXT文件: {txt_output_path}")
    logger.info(f"分割结果: {split_output_dir}")
    outline_file = txt_output_path.parent / f"{txt_output_path.stem}_outline.txt"
    if outline_file.exists():
        logger.info(f"大纲文件: {outline_file}")
    logger.info("")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='处理文档：转换为TXT，使用AI生成正则表达式，然后分割文件（支持 DOCX 和 PDF）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用配置文件处理 DOCX（推荐）
  python src/pipeline/main.py data/docx/1.docx
  
  # 使用配置文件处理 PDF
  python src/pipeline/main.py data/pdf/1.pdf
  
  # 使用命令行参数（覆盖配置文件）
  python src/pipeline/main.py data/docx/1.docx \\
    --base-url https://api.openai.com/v1 \\
    --api-key sk-xxx \\
    --model gpt-4
  
  # 指定配置文件
  python src/pipeline/main.py data/docx/1.docx \\
    --config custom_config.yaml
        """
    )
    
    parser.add_argument(
        'file_path',
        type=str,
        help='输入的文档文件路径（支持 .docx 或 .pdf）'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='配置文件路径（默认: 查找当前目录或脚本目录下的config/config.yaml）'
    )
    
    parser.add_argument(
        '--base-url',
        type=str,
        default=None,
        help='OpenAI API的base URL（覆盖配置文件中的设置）'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='API密钥（覆盖配置文件中的设置）'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='模型名称（覆盖配置文件中的设置）'
    )
    
    parser.add_argument(
        '--prompt-file',
        type=str,
        default=None,
        help='提示词文件路径（覆盖配置文件中的设置）'
    )
    
    parser.add_argument(
        '--sample-chars',
        type=int,
        default=None,
        help='样本字符数（覆盖配置文件中的设置）'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='API调用超时时间（秒，覆盖配置文件中的设置，默认: 120）'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出目录（可选，默认在输入文件同目录下创建同名文件夹）'
    )
    
    parser.add_argument(
        '--max-depth',
        type=int,
        default=None,
        help='最大递归深度（覆盖配置文件中的设置，默认: 1）'
    )
    
    parser.add_argument(
        '--max-file-length',
        type=int,
        default=None,
        help='最大子文件长度（字符数，覆盖配置文件中的设置，默认: 0表示不限制。小于等于此长度的文件将跳过分割）'
    )
    
    args = parser.parse_args()
    
    # 尝试加载配置文件
    config = {}
    try:
        config = load_config(args.config)
        logger.info(f"已加载配置文件")
    except FileNotFoundError as e:
        # 如果没有配置文件，检查是否所有必需参数都已提供
        if not args.base_url or not args.api_key or not args.model:
            logger.warning(f"{e}")
            logger.warning("请提供所有必需参数（--base-url, --api-key, --model）或创建配置文件。")
            logger.warning("可以复制 config/config.yaml.example 为 config/config.yaml 并修改配置。")
            sys.exit(1)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        sys.exit(1)
    
    # 从配置文件读取参数（如果命令行未提供）
    base_url = args.base_url or get_config_value(config, 'openai.base_url')
    api_key = args.api_key or get_config_value(config, 'openai.api_key')
    model = args.model or get_config_value(config, 'openai.model')
    prompt_file = args.prompt_file or get_config_value(config, 'processing.prompt_file')
    sample_chars = args.sample_chars or get_config_value(config, 'processing.sample_chars', 500)
    sample_chars_max = get_config_value(config, 'processing.sample_chars_max', 8000)
    timeout = args.timeout or get_config_value(config, 'processing.timeout', 120)
    output_dir = args.output or get_config_value(config, 'processing.output_dir')
    max_depth = args.max_depth or get_config_value(config, 'processing.max_depth', 1)
    max_file_length = args.max_file_length or get_config_value(config, 'processing.max_file_length', 0)
    
    # 设置正则表达式配置文件路径（使用默认路径）
    script_dir = Path(__file__).parent
    regex_config_file = str(script_dir / "config" / "regex_patterns.py")
    
    # 验证必需参数
    if not base_url or not api_key or not model:
        logger.error("缺少必需参数。请提供 --base-url, --api-key, --model 或在配置文件中设置。")
        sys.exit(1)
    
    run_pipeline(
        args.file_path,
        base_url,
        api_key,
        model,
        prompt_file,
        sample_chars,
        sample_chars_max,
        output_dir,
        timeout,
        max_depth,
        max_file_length,
        regex_config_file
    )


if __name__ == '__main__':
    main()

