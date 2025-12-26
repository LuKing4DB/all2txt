"""
测试配置文件中的大模型连通性
用于验证OpenAI API配置是否正确
"""

import argparse
import sys
from pathlib import Path

# 添加src目录到路径
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

# 添加当前目录到路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from lib.config_loader import load_config, get_config_value
from utils.logger import get_logger

logger = get_logger(__name__)


def test_connection(config_file: str = None, verbose: bool = False):
    """
    测试OpenAI API连接
    
    Args:
        config_file: 配置文件路径，如果为None则使用默认路径
        verbose: 是否显示详细信息
    """
    logger.info("=" * 60)
    logger.info("测试大模型连通性")
    logger.info("=" * 60)
    logger.info("")
    
    # 加载配置文件
    try:
        config = load_config(config_file)
        if config_file:
            logger.info(f"✓ 已加载配置文件: {config_file}")
        else:
            logger.info("✓ 已加载默认配置文件")
    except FileNotFoundError as e:
        logger.error(f"✗ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ 错误: 加载配置文件失败: {e}")
        sys.exit(1)
    
    # 读取配置参数
    base_url = get_config_value(config, 'openai.base_url')
    api_key = get_config_value(config, 'openai.api_key')
    model = get_config_value(config, 'openai.model')
    
    if verbose:
        logger.info(f"\n配置信息:")
        logger.info(f"  Base URL: {base_url}")
        logger.info(f"  API Key: {api_key[:10]}..." if api_key and len(api_key) > 10 else f"  API Key: {api_key}")
        logger.info(f"  Model: {model}")
        logger.info("")
    
    # 验证必需参数
    if not base_url:
        logger.error("✗ 错误: 配置文件中缺少 openai.base_url")
        sys.exit(1)
    
    if not api_key:
        logger.error("✗ 错误: 配置文件中缺少 openai.api_key")
        sys.exit(1)
    
    if not model:
        logger.error("✗ 错误: 配置文件中缺少 openai.model")
        sys.exit(1)
    
    logger.info(f"正在测试连接...")
    logger.info(f"  Base URL: {base_url}")
    logger.info(f"  Model: {model}")
    logger.info("")
    
    # 尝试导入openai库
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("✗ 错误: 未安装openai库")
        logger.error("  请运行: pip install openai")
        sys.exit(1)
    
    # 创建客户端
    try:
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        logger.info("✓ OpenAI客户端创建成功")
    except Exception as e:
        logger.error(f"✗ 错误: 创建OpenAI客户端失败: {e}")
        sys.exit(1)
    
    # 发送测试请求
    logger.info("正在发送测试请求...")
    test_messages = [
        {
            "role": "user",
            "content": "请回复'连接成功'，仅回复这四个字，不要包含其他内容。"
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=test_messages,
            temperature=0.1,
            max_tokens=10
        )
        
        # 检查响应是否有效
        if not response or not response.choices:
            logger.error("✗ 错误: API返回空响应")
            sys.exit(1)
        
        message = response.choices[0].message
        if not message:
            logger.error("✗ 错误: API返回的消息为空")
            sys.exit(1)
        
        # 尝试从多个可能的字段获取响应内容
        response_text = None
        if message.content:
            response_text = message.content.strip()
        elif hasattr(message, 'reasoning_content') and message.reasoning_content:
            response_text = message.reasoning_content.strip()
        elif hasattr(message, 'reasoning') and message.reasoning:
            response_text = message.reasoning.strip()
        
        if not response_text:
            logger.warning("⚠ 警告: API返回的响应内容为空，但API调用成功")
            if verbose:
                logger.debug(f"  响应对象: {response}")
                logger.debug(f"  完成原因: {response.choices[0].finish_reason}")
            # 即使内容为空，如果API调用成功，也认为连接正常
            logger.info("=" * 60)
            logger.info("✓ 连通性测试通过（响应内容为空，但API调用成功）")
            logger.info("=" * 60)
            return True
        
        logger.info("✓ API调用成功!")
        logger.info("")
        logger.info("响应内容:")
        logger.info(f"  {response_text}")
        logger.info("")
        
        # 显示详细信息
        if verbose:
            logger.info("详细信息:")
            logger.info(f"  模型: {response.model}")
            logger.info(f"  完成原因: {response.choices[0].finish_reason}")
            if hasattr(response, 'usage'):
                logger.info(f"  使用token数: {response.usage.total_tokens}")
            logger.info("")
        
        # 验证响应
        if "连接成功" in response_text or "成功" in response_text:
            logger.info("=" * 60)
            logger.info("✓ 连通性测试通过！")
            logger.info("=" * 60)
            return True
        else:
            logger.warning("⚠ 警告: 响应内容不符合预期，但API调用成功")
            logger.info("=" * 60)
            logger.info("✓ 连通性测试通过（响应异常）")
            logger.info("=" * 60)
            return True
            
    except Exception as e:
        logger.error("✗ 错误: API调用失败")
        logger.error("")
        logger.error("错误详情:")
        logger.error(f"  {type(e).__name__}: {e}")
        logger.error("")
        
        # 提供常见错误的解决建议
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            logger.error("建议:")
            logger.error("  - 检查API密钥是否正确")
            logger.error("  - 确认API密钥是否有效且未过期")
        elif "404" in error_str or "not found" in error_str:
            logger.error("建议:")
            logger.error("  - 检查base_url是否正确")
            logger.error("  - 检查模型名称是否正确")
        elif "connection" in error_str or "timeout" in error_str:
            logger.error("建议:")
            logger.error("  - 检查网络连接")
            logger.error("  - 检查base_url是否可访问")
            logger.error("  - 如果是本地模型，确认服务是否已启动")
        elif "rate limit" in error_str:
            logger.error("建议:")
            logger.error("  - 等待一段时间后重试")
            logger.error("  - 检查API配额是否已用完")
        
        logger.error("")
        logger.error("=" * 60)
        logger.error("✗ 连通性测试失败")
        logger.error("=" * 60)
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='测试配置文件中的大模型连通性',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置文件
  python src/pipeline/test/test_connection.py
  
  # 指定配置文件
  python src/pipeline/test/test_connection.py --config config/config.yaml
  
  # 显示详细信息
  python src/pipeline/test/test_connection.py -v
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='配置文件路径（默认: 查找当前目录或脚本目录下的config/config.yaml）'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细信息'
    )
    
    args = parser.parse_args()
    
    success = test_connection(args.config, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

