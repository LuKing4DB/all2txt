"""
意图识别器
负责将用户简短/不完整的提问转化为可用于验证的完整意图描述
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.prompts.intent import format_intent_analysis

logger = get_logger(__name__)


class IntentAnalyzer:
    """意图识别器"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60, max_tokens: int = 400):
        """
        初始化意图识别器

        Args:
            base_url: LLM API基础URL
            api_key: API密钥
            model: 模型名称
            timeout: 超时时间（秒）
            max_tokens: 生成的最大token数
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def analyze(self, query: str) -> Dict[str, str]:
        """
        分析用户真实意图，返回补全后的验证查询与推理
        """
        if not query:
            return {"intent": "", "reasoning": ""}

        prompt = format_intent_analysis(query)

        try:
            from openai import OpenAI
            import httpx
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai")
            return {"intent": query, "reasoning": ""}

        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=self.max_tokens,
            )

            if not response or not response.choices:
                raise ValueError("API返回空响应")

            message = response.choices[0].message
            if not message or not message.content:
                raise ValueError("API返回的消息为空")

            response_text = str(message.content).strip()
            logger.debug(f"  意图识别响应: {response_text[:200]}...")

            parsed = self._parse_json_response(response_text)
            intent = (parsed.get("intent") or query).strip()
            reasoning = str(parsed.get("reasoning", "")).strip()

            if not intent:
                intent = query

            return {"intent": intent, "reasoning": reasoning}

        except Exception as e:
            logger.warning(f"意图识别失败: {e}，使用原始查询")
            return {"intent": query, "reasoning": ""}

    @staticmethod
    def _parse_json_response(response_text: str) -> dict:
        """解析返回的JSON文本，兼容代码块和非严格格式"""
        text = response_text.strip()

        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline > 0:
                text = text[first_newline:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"intent": text}

