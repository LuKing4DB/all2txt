"""
路由决策器
判断用户查询是否需要检索外部知识
"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import RouterDecision

logger = get_logger(__name__)


class Router:
    """路由决策器"""
    
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 120):
        """
        初始化路由决策器
        
        Args:
            base_url: LLM API基础URL（已废弃，保留以兼容接口）
            api_key: API密钥（已废弃，保留以兼容接口）
            model: 模型名称（已废弃，保留以兼容接口）
            timeout: 超时时间（秒，已废弃，保留以兼容接口）
        """
        # 参数保留以兼容现有接口，但不再使用
        pass
    
    def decide(self, query: str) -> RouterDecision:
        """
        提取查询关键词（直接返回查询本身作为关键词）
        
        Args:
            query: 用户查询
            
        Returns:
            路由决策结果（始终返回需要检索，使用查询本身作为关键词）
        """
        logger.info("=" * 80)
        logger.info("关键词提取: 使用查询本身作为关键词")
        logger.info(f"  查询: {query}")
        
        # 直接使用查询本身作为关键词
        return RouterDecision(
            needs_retrieval=True,
            confidence=1.0,
            reasoning="使用查询本身作为关键词",
            keywords=[query]
        )

