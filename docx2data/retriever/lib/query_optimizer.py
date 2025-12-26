"""
查询优化器
根据Anti-RAG范式优化查询，提高召回准确率
"""

import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import RouterDecision
from retriever.prompts.keywords import format_keyword_expansion

logger = get_logger(__name__)


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 120):
        """
        初始化查询优化器
        
        Args:
            base_url: LLM API基础URL
            api_key: API密钥
            model: 模型名称
            timeout: 超时时间（秒）
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
    
    def expand_keywords(self, query: str, original_keywords: List[str], 
                       context: Optional[str] = None) -> List[str]:
        """
        扩展关键词：生成同义词、相关词、变体词
        
        Args:
            query: 原始查询
            original_keywords: 原始关键词列表
            context: 上下文信息（可选，如检索失败的原因）
            
        Returns:
            扩展后的关键词列表
        """
        logger.info("  查询优化: 扩展关键词")
        
        try:
            expanded_keywords = self._call_keyword_expansion_llm(
                query, original_keywords, context
            )
            
            # 合并原始关键词和扩展关键词（去重）
            all_keywords = list(set(original_keywords + expanded_keywords))
            logger.info(f"  关键词扩展: {len(original_keywords)} -> {len(all_keywords)} 个")
            logger.debug(f"  扩展的关键词: {expanded_keywords}")
            
            return all_keywords
        except Exception as e:
            logger.warning(f"  关键词扩展失败: {e}，使用原始关键词")
            return original_keywords
    
    def _call_keyword_expansion_llm(self, query: str, keywords: List[str],
                                   context: Optional[str] = None) -> List[str]:
        """
        调用LLM扩展关键词
        
        Args:
            query: 原始查询
            keywords: 原始关键词列表
            context: 上下文信息
            
        Returns:
            扩展后的关键词列表
        """
        context_text = f"\n上下文: {context}" if context else ""
        keywords_str = ', '.join(keywords)
        prompt = format_keyword_expansion(query, keywords_str, context_text)
        
        try:
            from openai import OpenAI
            import httpx
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai")
            raise
        
        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(self.timeout, connect=10.0)
        )
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            if not response or not response.choices:
                raise ValueError("API返回空响应")
            
            message = response.choices[0].message
            if not message or not message.content:
                raise ValueError("API返回的消息为空")
            
            response_text = message.content.strip()
            logger.debug(f"  LLM响应: {response_text[:200]}...")
            
            # 解析JSON响应
            result_dict = self._parse_json_response(response_text)
            expanded = result_dict.get("expanded_keywords", [])
            
            # 过滤和验证关键词
            expanded = [kw for kw in expanded if isinstance(kw, str) and 2 <= len(kw) <= 20]
            
            return expanded
            
        except Exception as e:
            logger.error(f"调用关键词扩展LLM失败: {e}")
            raise
    
    def _parse_json_response(self, response_text: str) -> dict:
        """
        解析JSON响应
        
        Args:
            response_text: 响应文本
            
        Returns:
            解析后的字典
        """
        text = response_text.strip()
        
        # 移除可能的代码块标记
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline > 0:
                text = text[first_newline:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        
        # 尝试解析JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"无法解析JSON响应: {text[:200]}")

