"""
验证器
验证检索结果的相关性和准确性
"""

import sys
import json
import re
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import Evidence
from retriever.prompts.verifier import format_verifier_batch, format_verifier_single

logger = get_logger(__name__)


class Verifier:
    """验证器"""
    TITLE_WEIGHT = 0.2
    CONTENT_WEIGHT = 0.8
    
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 120, 
                 max_concurrent: int = 20, use_concurrent: bool = True, max_tokens: int = 8000,
                 batch_size: int = 10):
        """
        初始化验证器
        
        Args:
            base_url: LLM API基础URL
            api_key: API密钥
            model: 模型名称
            timeout: 超时时间（秒）
            max_concurrent: 最大并发批次数（默认20）
            use_concurrent: 是否使用并发验证（默认True，已废弃）
            max_tokens: LLM生成的最大token数（默认8000）
            batch_size: 批量验证的批次大小（默认5）
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.use_concurrent = use_concurrent
        self.max_tokens = max_tokens
        self.batch_size = batch_size
    
    def verify(self, query: str, evidences: List[Evidence]) -> Dict[str, float]:
        """
        验证检索结果的相关性
        
        Args:
            query: 原始查询
            evidences: 证据列表
            
        Returns:
            验证分数字典 {evidence_index: score}
        """
        if not evidences:
            return {}
        
        try:
            # 使用批量验证模式，分批处理证据（便于模型横向比较）
            total_batches = (len(evidences) + self.batch_size - 1) // self.batch_size
            logger.info(f"验证 {len(evidences)} 个证据（批次: {total_batches}，每批: {self.batch_size}）")
            verification_scores = self._verify_in_batches(query, evidences)
            
            if logger.isEnabledFor(logging.DEBUG):
                for idx, score in verification_scores.items():
                    logger.debug(f"证据 {idx}: {score:.2f}")
            
            return verification_scores
        except Exception as e:
            logger.warning(f"  验证失败: {e}")
            logger.debug("使用默认验证分数（基于相关性分数）")
            # 使用相关性分数作为默认验证分数
            return {str(i): ev.relevance_score for i, ev in enumerate(evidences)}

    async def verify_async(self, query: str, evidences: List[Evidence]) -> Dict[str, float]:
        """
        异步验证检索结果的相关性（适用于已有事件循环，如FastAPI）
        """
        if not evidences:
            return {}
        try:
            total_batches = (len(evidences) + self.batch_size - 1) // self.batch_size
            logger.info(f"[async] 验证 {len(evidences)} 个证据（批次: {total_batches}，每批: {self.batch_size}）")
            verification_scores = await self._verify_in_batches_async(query, evidences)

            if logger.isEnabledFor(logging.DEBUG):
                for idx, score in verification_scores.items():
                    logger.debug(f"[async] 证据 {idx}: {score:.2f}")

            return verification_scores
        except Exception as e:
            logger.warning(f"  [async] 验证失败: {e}")
            logger.debug("使用默认验证分数（基于相关性分数）")
            return {str(i): ev.relevance_score for i, ev in enumerate(evidences)}
    
    def _extract_relevant_context(self, content: str, query: str, before_lines: int = 3, after_lines: int = 4, max_length: int = 600) -> str:
        """
        从完整内容中提取包含查询关键词的目标区域及其上下文
        
        Args:
            content: 完整内容
            query: 查询字符串
            before_lines: 匹配行之前包含的行数（默认3行）
            after_lines: 匹配行之后包含的行数（默认4行）
            max_length: 最大返回长度（字符数，默认600）
            
        Returns:
            提取的相关片段
        """
        if not content or not query:
            return content[:max_length] if len(content) > max_length else content
        
        # 简单关键词获取（不依赖本地分词）
        import re
        tokens = [t for t in re.split(r"[\\s,，。.!？?;；:：]+", query) if len(t) >= 2]
        keywords = tokens if tokens else [query]
        
        # 添加原文作为关键词
        if query not in keywords:
            keywords.insert(0, query)
        
        # 按行分割内容
        lines = content.split('\n')
        
        # 找到包含关键词的行索引
        relevant_indices = set()
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword in line:
                    relevant_indices.add(i)
                    break
        
        if not relevant_indices:
            # 如果没有找到匹配的行，返回前max_length个字符
            truncated = content[:max_length]
            if len(content) > max_length:
                last_newline = truncated.rfind('\n')
                if last_newline > max_length * 0.7:
                    return truncated[:last_newline] + "\n..."
                return truncated + "..."
            return content
        
        # 收集相关行（包含上下文：前3行后4行）
        snippet_indices = set()
        for idx in relevant_indices:
            start = max(0, idx - before_lines)
            end = min(len(lines), idx + after_lines + 1)
            snippet_indices.update(range(start, end))
        
        # 按顺序提取行
        snippet_lines = [lines[i] for i in sorted(snippet_indices)]
        snippet_text = '\n'.join(snippet_lines)
        
        # 如果片段太长，在行边界处截断
        if len(snippet_text) > max_length:
            truncated = snippet_text[:max_length]
            last_newline = truncated.rfind('\n')
            if last_newline > max_length * 0.7:
                snippet_text = truncated[:last_newline] + "\n..."
            else:
                snippet_text = truncated + "..."
        
        return snippet_text
    
    def _verify_in_batches(self, query: str, evidences: List[Evidence]) -> Dict[str, float]:
        """
        分批验证证据，每批batch_size个，便于模型横向比较
        
        Args:
            query: 原始查询
            evidences: 证据列表
            
        Returns:
            验证分数字典 {evidence_index: score}
        """
        all_scores = {}
        total_batches = (len(evidences) + self.batch_size - 1) // self.batch_size
        max_workers = total_batches if not self.max_concurrent or self.max_concurrent <= 0 else min(self.max_concurrent, total_batches)
        
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch_idx in range(0, len(evidences), self.batch_size):
                batch_evidences = evidences[batch_idx:batch_idx + self.batch_size]
                batch_num = batch_idx // self.batch_size + 1
                
                logger.debug(f"提交批次 {batch_num}/{total_batches}（{len(batch_evidences)} 个证据）")
                
                futures.append(
                    executor.submit(
                        self._call_verifier_llm,
                        query,
                        batch_evidences,
                        batch_start_idx=batch_idx
                    )
                )
            
            for future in as_completed(futures):
                try:
                    batch_scores = future.result()
                except Exception as e:
                    logger.warning(f"并发验证批次失败: {e}")
                    continue
                
                all_scores.update(batch_scores)
        
        return all_scores

    async def _verify_in_batches_async(self, query: str, evidences: List[Evidence]) -> Dict[str, float]:
        """
        异步分批验证证据，使用事件循环并发发送批次请求
        """
        all_scores: Dict[str, float] = {}
        total_batches = (len(evidences) + self.batch_size - 1) // self.batch_size
        max_concurrent_batches = total_batches if not self.max_concurrent or self.max_concurrent <= 0 else min(self.max_concurrent, total_batches)
        semaphore = asyncio.Semaphore(max_concurrent_batches)

        async def run_batch(batch_idx: int, batch_evidences: List[Evidence]) -> Dict[str, float]:
            batch_num = batch_idx // self.batch_size + 1
            logger.debug(f"[async] 提交批次 {batch_num}/{total_batches}（{len(batch_evidences)} 个证据）")
            async with semaphore:
                try:
                    return await self._call_verifier_llm_batch_async(query, batch_evidences, batch_start_idx=batch_idx)
                except Exception as e:
                    logger.warning(f"[async] 并发验证批次失败: {e}")
                    return {}

        tasks = [
            run_batch(batch_idx, evidences[batch_idx:batch_idx + self.batch_size])
            for batch_idx in range(0, len(evidences), self.batch_size)
        ]

        results = await asyncio.gather(*tasks)
        for batch_scores in results:
            all_scores.update(batch_scores)

        return all_scores
    
    def _format_evidence_unified(self, evidence: Evidence, index: int, query: str) -> str:
        """
        统一格式化证据展示（用于验证器）
        
        Args:
            evidence: 证据对象
            index: 证据索引（批次内索引）
            query: 查询字符串（用于提取相关上下文）
            
        Returns:
            格式化后的证据文本
        """
        # 提取包含查询关键词的相关片段（前3行后4行，减小片段大小以支持更大批次）
        content_snippet = self._extract_relevant_context(evidence.content, query, before_lines=3, after_lines=4, max_length=600)
        
        # 构建统一的展示格式
        parts = [f"证据 {index}:"]
        
        # 文档信息
        doc_info_parts = []
        if evidence.doc_id:
            doc_info_parts.append(f"文档: {evidence.doc_id}")
        if evidence.file_path:
            doc_info_parts.append(f"文件: {evidence.file_path}")
        if doc_info_parts:
            parts.append(" | ".join(doc_info_parts))
        
        # 章节信息（提示模型提高章节权重）
        if evidence.section:
            parts.append(f"章节(优先参考): {evidence.section}")
        
        # 行号信息
        if evidence.start_line is not None and evidence.end_line is not None:
            if evidence.start_line == evidence.end_line:
                parts.append(f"行号: {evidence.start_line}")
            else:
                parts.append(f"行号: {evidence.start_line}-{evidence.end_line}")
        
        # 检索分数（如果可用）
        if evidence.retrieval_score > 0:
            parts.append(f"检索分数: {evidence.retrieval_score:.3f}")
        
        # 内容
        parts.append(f"内容: {content_snippet}")
        
        return "\n".join(parts) + "\n"

    @staticmethod
    def _combine_title_content_score(query: str, evidence: Evidence, content_score: float) -> float:
        """
        将标题(章节)与内容打分按固定权重合成
        """
        section = (evidence.section or "").lower()
        q = query.lower()

        # 简单标题匹配：完整包含 > 关键词包含 > 否
        if not section:
            title_score = 0.0
        elif q and q in section:
            title_score = 1.0
        else:
            # 关键词切分（按空白+常见分隔）
            import re
            tokens = [t for t in re.split(r"[\\s,，。.!？?;；:：]+", q) if len(t) >= 2]
            title_score = 1.0 if any(t in section for t in tokens) else 0.0

        final_score = (
            Verifier.CONTENT_WEIGHT * content_score
            + Verifier.TITLE_WEIGHT * title_score
        )
        # 保证在0-1区间
        return max(0.0, min(1.0, final_score))
    
    def _call_verifier_llm(self, query: str, evidences: List[Evidence], batch_start_idx: int = 0) -> Dict[str, float]:
        """
        调用LLM进行验证
        
        Args:
            query: 原始查询
            evidences: 证据列表
            
        Returns:
            验证分数字典
        """
        # 构建证据列表文本（使用统一的展示格式）
        evidence_texts = []
        for i, ev in enumerate(evidences):
            # 使用批次内的索引（0, 1, 2...）以便模型横向比较
            evidence_texts.append(self._format_evidence_unified(ev, i, query))
        
        evidence_list = "\n".join(evidence_texts)
        
        prompt = format_verifier_batch(query, evidence_list)
        
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
                temperature=0.1,
                max_tokens=self.max_tokens
            )
            
            if not response or not response.choices:
                raise ValueError("API返回空响应")
            
            message = response.choices[0].message
            if not message or not message.content:
                raise ValueError("API返回的消息为空")
            
            response_text = message.content.strip()
            logger.debug(f"  LLM响应: {response_text[:200]}...")
            
            # 解析JSON响应
            scores_dict = self._parse_json_response(response_text)
            
            # 转换为字符串键的字典，并调整索引（加上批次起始索引）
            verification_scores = {}
            for key, value in scores_dict.items():
                # 批次内的索引（0, 1, 2...）转换为全局索引
                batch_idx = int(key)
                global_idx = batch_start_idx + batch_idx
                content_score = float(value)
                ev = evidences[batch_idx] if batch_idx < len(evidences) else None
                if ev:
                    verification_scores[str(global_idx)] = self._combine_title_content_score(query, ev, content_score)
                else:
                    verification_scores[str(global_idx)] = content_score
            
            return verification_scores
            
        except Exception as e:
            logger.error(f"调用验证LLM失败: {e}")
            raise

    async def _call_verifier_llm_batch_async(self, query: str, evidences: List[Evidence], batch_start_idx: int = 0) -> Dict[str, float]:
        """
        异步调用LLM进行批量验证
        """
        evidence_texts = []
        for i, ev in enumerate(evidences):
            evidence_texts.append(self._format_evidence_unified(ev, i, query))

        evidence_list = "\n".join(evidence_texts)
        prompt = format_verifier_batch(query, evidence_list)

        try:
            from openai import AsyncOpenAI
            import httpx
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai")
            raise

        client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(self.timeout, connect=10.0)
        )

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens
            )

            if not response or not response.choices:
                raise ValueError("API返回空响应")

            message = response.choices[0].message
            if not message or not message.content:
                raise ValueError("API返回的消息为空")

            response_text = message.content.strip()
            logger.debug(f"  [async] LLM响应: {response_text[:200]}...")

            scores_dict = self._parse_json_response(response_text)

            verification_scores = {}
            for key, value in scores_dict.items():
                batch_idx = int(key)
                global_idx = batch_start_idx + batch_idx
                content_score = float(value)
                ev = evidences[batch_idx] if batch_idx < len(evidences) else None
                if ev:
                    verification_scores[str(global_idx)] = self._combine_title_content_score(query, ev, content_score)
                else:
                    verification_scores[str(global_idx)] = content_score

            return verification_scores

        except Exception as e:
            logger.error(f"[async] 调用验证LLM失败: {e}")
            raise
        finally:
            await client.close()
    
    async def _call_verifier_llm_async(self, query: str, evidences: List[Evidence]) -> Dict[str, float]:
        """
        使用协程并发调用LLM验证每个证据
        
        Args:
            query: 原始查询
            evidences: 证据列表
            
        Returns:
            验证分数字典
        """
        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def verify_single_evidence_with_semaphore(idx: int, evidence: Evidence) -> tuple:
            """使用信号量限制并发的单个证据验证"""
            async with semaphore:
                try:
                    score = await self._verify_single_evidence_llm_async(query, evidence)
                    return (idx, score)
                except Exception as e:
                    logger.warning(f"  证据 {idx} 验证失败: {e}，使用相关性分数作为默认值")
                    return (idx, evidence.relevance_score)
        
        # 创建所有任务
        tasks = [
            verify_single_evidence_with_semaphore(i, ev)
            for i, ev in enumerate(evidences)
        ]
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks)
        
        # 收集结果
        verification_scores = {}
        for idx, score in results:
            verification_scores[str(idx)] = score
        
        return verification_scores
    
    async def _verify_single_evidence_llm_async(self, query: str, evidence: Evidence) -> float:
        """
        调用LLM验证单个证据
        
        Args:
            query: 原始查询
            evidence: 单个证据
            
        Returns:
            验证分数（0-1）
        """
        # 提取包含查询关键词的相关片段（而不是整个文件）
        content_snippet = self._extract_relevant_context(evidence.content, query, before_lines=3, after_lines=4, max_length=600)
        
        # 极简 prompt
        prompt = format_verifier_single(query, content_snippet)
        
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai")
            raise
        
        client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout
        )
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens
            )
            
            if not response or not response.choices:
                logger.error(f"  API返回格式异常")
                raise ValueError("API返回空响应")
            
            choice = response.choices[0]
            finish_reason = choice.finish_reason
            message = choice.message
            
            # 详细日志
            logger.debug(f"  finish_reason: {finish_reason}")
            logger.debug(f"  message: {message}")
            
            if not message:
                logger.error("  message对象为None")
                raise ValueError("API返回的消息对象为空")
            
            # 检查 message.content
            content = getattr(message, 'content', None)
            logger.debug(f"  content type: {type(content)}, value: {repr(content)}")
            
            if content is None or (isinstance(content, str) and not content.strip()):
                # 如果是因为长度限制
                if finish_reason == "length":
                    logger.warning(f"  token长度限制，prompt可能过长，使用默认分数0.5")
                    return 0.5
                
                # 其他原因导致的空内容
                logger.warning(f"  响应内容为空(finish_reason={finish_reason})，使用默认分数0.5")
                return 0.5
            
            response_text = str(content).strip()
            logger.debug(f"  响应文本: '{response_text}'")
            
            # 提取数字（支持各种格式）
            score_match = re.search(r'(\d*\.?\d+)', response_text)
            if score_match:
                score = float(score_match.group(1))
                # 确保分数在0-1范围内
                score = max(0.0, min(1.0, score))
                return score
            else:
                logger.warning(f"  无法提取数字: '{response_text[:100]}'，使用默认值0.5")
                return 0.5
            
        except Exception as e:
            logger.error(f"调用验证LLM失败: {e}")
            raise
        finally:
            await client.close()
    
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

