"""
Anti-RAG检索器主类
整合路由决策、检索、验证和引用功能
"""

import sys
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import RetrievalResult
from retriever.lib.router import Router
from retriever.lib.query_optimizer import QueryOptimizer
from retriever.lib.document_retriever import DocumentRetriever
from retriever.lib.verifier import Verifier
from retriever.lib.intent_analyzer import IntentAnalyzer
from retriever.prompts.keywords import format_keyword_segmentation_weight
from retriever.lib.retrieval_utils import (
    filter_deep_zero_txt,
    dedupe_merge_by_path_lines,
    verify_and_merge,
)

logger = get_logger(__name__)

class AntiRAGRetriever:
    """Anti-RAG检索器"""
    

    def __init__(self, data_dir: str = "data", config_path: Optional[str] = None):
        """
        初始化Anti-RAG检索器
        
        Args:
            data_dir: 数据目录路径
            config_path: 配置文件路径（可选）
        """
        # 加载配置
        if config_path is None:
            # 默认使用本模块的配置文件
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        
        self.config = self._load_config(config_path)
        
        # 初始化组件
        llm_config = self.config.get("openai", {})
        self.router = Router(
            base_url=llm_config.get("base_url", "http://localhost:8000/v1"),
            api_key=llm_config.get("api_key", ""),
            model=llm_config.get("model", "gpt-3.5-turbo"),
            timeout=self.config.get("processing", {}).get("timeout", 120)
        )
        
        # 设置索引缓存文件路径（默认在data目录下）
        index_cache_file = str(Path(data_dir) / ".index_cache" / "search_index.pkl")
        
        self.document_retriever = DocumentRetriever(
            data_dir=data_dir,
            index_cache_file=index_cache_file
        )
        
        # 检查并构建索引（如果启用）
        if self.document_retriever.searcher.use_index:
            stats = self.document_retriever.get_cache_stats()
            index_stats = stats.get('index', {})
            # 如果索引为空或关键词数为0，尝试构建索引
            if index_stats.get('keywords', 0) == 0:
                logger.info("检测到索引为空，开始构建内存索引（首次构建可能需要一些时间）...")
                try:
                    self.document_retriever.build_index()
                    stats_after = self.document_retriever.get_cache_stats()
                    index_stats_after = stats_after.get('index', {})
                    logger.info(f"索引构建完成: {index_stats_after.get('keywords', 0)} 个关键词，{index_stats_after.get('indexed_files', 0)} 个文件")
                except Exception as e:
                    logger.warning(f"索引构建失败: {e}，将继续使用全量搜索")
            else:
                logger.info(f"索引已加载: {index_stats.get('keywords', 0)} 个关键词，{index_stats.get('indexed_files', 0)} 个文件")
        
        processing_config = self.config.get("processing", {})
        intent_enabled = processing_config.get("enable_intent_analysis", True)
        intent_max_tokens = processing_config.get("intent_max_tokens", 400)

        self.intent_analyzer = (
            IntentAnalyzer(
                base_url=llm_config.get("base_url", "http://localhost:8000/v1"),
                api_key=llm_config.get("api_key", ""),
                model=llm_config.get("model", "gpt-3.5-turbo"),
                timeout=processing_config.get("timeout", 120),
                max_tokens=intent_max_tokens,
            )
            if intent_enabled
            else None
        )

        self.verifier = Verifier(
            base_url=llm_config.get("base_url", "http://localhost:8000/v1"),
            api_key=llm_config.get("api_key", ""),
            model=llm_config.get("model", "gpt-3.5-turbo"),
            timeout=processing_config.get("timeout", 120),
            max_concurrent=processing_config.get("max_concurrent", 20),
            use_concurrent=processing_config.get("use_concurrent", True),
            max_tokens=processing_config.get("max_tokens", 8000),
            batch_size=processing_config.get("verification_batch_size", 10)
        )
        
        # 查询优化器（用于阶段3的关键词扩展）
        self.query_optimizer = QueryOptimizer(
            base_url=llm_config.get("base_url", "http://localhost:8000/v1"),
            api_key=llm_config.get("api_key", ""),
            model=llm_config.get("model", "gpt-3.5-turbo"),
            timeout=processing_config.get("timeout", 120),
        )
        
        logger.info("Anti-RAG检索器初始化完成")
    
    def retrieve_batch(self, query: str, doc_ids: List[str], max_results: int = 200,
                       use_query_planning: bool = True, stage: int = 3) -> RetrievalResult:
        """
        批量检索多个文档（并发检索，统一意图识别和验证）
        
        Args:
            query: 用户查询（自然语言）
            doc_ids: 文档ID列表
            max_results: 最大返回结果数
            use_query_planning: 是否允许使用查询规划（默认True）
            stage: 检索阶段控制（1=仅原文，2=原文+分词，3=全流程，默认3）
            
        Returns:
            检索结果
        """
        if not doc_ids:
            return self.retrieve(query, max_results=max_results, stage=stage)
        
        # 规范化阶段参数
        stage = max(1, min(stage, 3))
        enable_segmentation = stage >= 2
        enable_expansion = stage >= 3
        
        logger.info("=" * 80)
        logger.info(f"批量检索开始 | 查询: {query} | 文档数: {len(doc_ids)} | 阶段: {stage}")
        
        # ========== 统一意图识别（只识别一次） ==========
        intent_query = query
        intent_reasoning = ""
        if self.intent_analyzer:
            intent_result = self.intent_analyzer.analyze(query)
            intent_query = (intent_result.get("intent") or query).strip() or query
            intent_reasoning = intent_result.get("reasoning", "")
            logger.info(f"意图识别: {intent_query}")
            if intent_reasoning:
                logger.debug(f"意图推理: {intent_reasoning}")
        verification_query = self._build_verification_query(query, intent_query)
        
        # ========== 阶段1：并发检索所有文档 ==========
        logger.info(f"阶段1: 并发检索 {len(doc_ids)} 个文档")
        all_evidences = []
        all_keywords = []
        original_keywords = [query]
        
        def retrieve_single_doc(doc_id: str):
            """检索单个文档（内部方法，不包含意图识别和验证）"""
            try:
                logger.debug(f"检索文档: {doc_id}")
                # 使用原文作为关键词进行检索
                evidences = self.document_retriever.retrieve(
                    keywords=original_keywords,
                    max_results=max_results,
                    doc_id=doc_id
                )
                return doc_id, evidences, original_keywords
            except Exception as e:
                logger.warning(f"检索文档 {doc_id} 失败: {e}")
                return doc_id, [], []
        
        # 并发检索所有文档
        max_workers = min(len(doc_ids), 20)  # 最多20个并发
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(retrieve_single_doc, doc_id): doc_id for doc_id in doc_ids}
            
            for future in as_completed(futures):
                doc_id, evidences, keywords = future.result()
                all_evidences.extend(evidences)
                if keywords:
                    all_keywords.extend(keywords)
        
        logger.info(f"并发检索完成 | 共找到 {len(all_evidences)} 个证据")
        
        # ========== 统一处理证据 ==========
        logger.info(f"步骤2: 处理 {len(all_evidences)} 个证据")
        
        # 保存原始检索分数
        for ev in all_evidences:
            ev.retrieval_score = ev.relevance_score
        
        # 过滤深层 0.txt
        all_evidences = filter_deep_zero_txt(all_evidences, "批量检索", logger)
        
        # 路径/行号去重合并
        all_evidences = dedupe_merge_by_path_lines(all_evidences, "批量检索", logger)
        
        # 按检索分数排序
        all_evidences.sort(key=lambda x: x.retrieval_score, reverse=True)
        
        # 限制验证数量
        if len(all_evidences) > max_results:
            logger.info(f"限制验证数量: {len(all_evidences)} -> {max_results} 个")
            all_evidences = all_evidences[:max_results]
        
        # ========== 统一验证（批量验证） ==========
        logger.info(f"步骤3: 统一验证 {len(all_evidences)} 个证据")
        
        verification_scores = self.verifier.verify(verification_query, all_evidences)
        
        # 根据验证分数过滤和排序
        quality_config = self.config.get("quality", {})
        min_score_threshold = quality_config.get("min_score_threshold", 0.5)
        # 使用与min_score_threshold相同的默认值，确保阈值一致性
        verification_score_threshold = quality_config.get("verification_score_threshold", min_score_threshold)
        
        if verification_scores and verification_score_threshold > 0:
            original_count = len(all_evidences)
            filtered_evidences = []
            filtered_scores = {}
            new_index = 0
            
            for i, ev in enumerate(all_evidences):
                score_key = str(i)
                if score_key in verification_scores:
                    ver_score = verification_scores[score_key]
                    if ver_score > verification_score_threshold:
                        filtered_evidences.append(ev)
                        ev.relevance_score = ver_score
                        filtered_scores[str(new_index)] = ver_score
                        new_index += 1
            
            filtered_count = original_count - len(filtered_evidences)
            all_evidences = filtered_evidences
            
            if filtered_count > 0:
                logger.info(f"验证分数过滤: {filtered_count} 个（阈值: {verification_score_threshold:.2f}）")
            
            # 按验证分数排序
            all_evidences.sort(key=lambda x: x.relevance_score, reverse=True)
        elif verification_scores:
            # 如果没有设置阈值，仍然用验证分数替换相关性分数并排序
            for i, ev in enumerate(all_evidences):
                score_key = str(i)
                if score_key in verification_scores:
                    ev.relevance_score = verification_scores[score_key]
            all_evidences.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # 计算最高分
        max_score = max([ev.relevance_score for ev in all_evidences], default=0.0)
        
        # 初始化结果对象
        result = RetrievalResult(
            query=query,
            intent_query=intent_query,
            intent_reasoning=intent_reasoning,
            needs_retrieval=True,
            reasoning=f"在 {len(doc_ids)} 个文档中并发检索",
            keywords=list(set(all_keywords)) if all_keywords else [query],
            evidences=all_evidences,
            citations=self.document_retriever.build_citations(all_evidences),
            verification_scores=verification_scores if verification_scores else {},
            total_results=len(all_evidences),
            evidence_sufficient=max_score >= min_score_threshold
        )
        
        # ========== 阶段2：分词加权检索（如果启用且结果不足） ==========
        needs_segmentation = (
            enable_segmentation and (not result.evidences or max_score < min_score_threshold)
        )
        
        if needs_segmentation:
            logger.info("")
            if not result.evidences:
                logger.info(f"阶段2: 分词加权检索（阶段1未召回证据，启用阶段2）")
            else:
                logger.info(f"阶段2: 分词加权检索（阶段1最高分 {max_score:.3f} < 阈值 {min_score_threshold:.3f}，启用阶段2）")
            
            # 使用大模型进行分词和权重分配
            weighted_keywords = self._get_weighted_keywords_from_llm(query, max_score if all_evidences else 0.0)
            
            if weighted_keywords:
                logger.info(f"  分词结果（带权重）: {weighted_keywords}")
                
                def retrieve_single_doc_segmentation(doc_id: str):
                    """阶段2：使用分词关键词检索单个文档"""
                    try:
                        logger.debug(f"阶段2检索文档: {doc_id}")
                        evidences = self.document_retriever.retrieve(
                            keywords=[kw["keyword"] for kw in weighted_keywords],
                            keyword_weights={kw["keyword"]: kw["weight"] for kw in weighted_keywords},
                            max_results=max_results * 2,
                            doc_id=doc_id
                        )
                        return doc_id, evidences
                    except Exception as e:
                        logger.warning(f"阶段2检索文档 {doc_id} 失败: {e}")
                        return doc_id, []
                
                # 并发检索所有文档
                expanded_evidences = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(retrieve_single_doc_segmentation, doc_id): doc_id for doc_id in doc_ids}
                    
                    for future in as_completed(futures):
                        doc_id, evidences = future.result()
                        expanded_evidences.extend(evidences)
                
                if expanded_evidences:
                    logger.info(f"  阶段2召回 {len(expanded_evidences)} 个证据")
                    
                    # 去重：过滤掉已有的证据
                    existing_paths = {(ev.doc_id, ev.file_path) for ev in result.evidences}
                    new_evidences = [
                        ev for ev in expanded_evidences
                        if (ev.doc_id, ev.file_path) not in existing_paths
                    ]
                    
                    if new_evidences:
                        logger.info(f"  新增 {len(new_evidences)} 个证据（已去重）")
                        logger.info("")
                        logger.info("步骤4: 验证阶段2检索结果（打分）")
                        
                        # 与原文检索一致：过滤0.txt + 合并 + 验证
                        new_max_score = verify_and_merge(
                            stage="阶段2批量检索",
                            query=query,
                            verification_query=verification_query,
                            new_evidences=new_evidences,
                            result=result,
                            verifier=self.verifier,
                            config=self.config,
                            logger=logger,
                            keywords=None,  # 不覆盖关键词，最后统一更新
                            reasoning=f"阶段2批量检索，原始查询: {query}, 分词关键词: {[kw['keyword'] for kw in weighted_keywords]}"
                        )
                        
                        max_score = max(max_score, new_max_score)
                        all_keywords.extend([kw["keyword"] for kw in weighted_keywords])
                    else:
                        logger.info("  阶段2未找到新证据（已去重）")
                else:
                    logger.info("  阶段2未召回结果")
        
        # ========== 阶段3：关键词扩展检索（如果启用且结果不足） ==========
        needs_expansion = (
            enable_expansion and (not result.evidences or max_score < min_score_threshold)
        )
        
        if needs_expansion:
            logger.info("")
            if not result.evidences:
                logger.info(f"阶段3: 关键词扩展 + 扩大搜索（前两轮未召回证据，启用阶段3）")
            else:
                logger.info(f"阶段3: 关键词扩展 + 扩大搜索（前两轮最高分 {max_score:.3f} < 阈值 {min_score_threshold:.3f}，启用阶段3）")
            
            # 提取扩展关键词（使用查询优化器的扩展提示词）
            expanded_keywords = []
            try:
                expanded_keywords = self.query_optimizer.expand_keywords(
                    query=query,
                    original_keywords=original_keywords,
                    context="前两轮召回不足"
                )
                # 确保至少包含原文
                if not expanded_keywords:
                    expanded_keywords = original_keywords
            except Exception as e:
                logger.warning(f"  关键词扩展失败，回退使用原始关键词: {e}")
                expanded_keywords = original_keywords
            
            logger.info(f"  扩展关键词: {expanded_keywords}")
            
            def retrieve_single_doc_expansion(doc_id: str):
                """阶段3：使用扩展关键词检索单个文档"""
                try:
                    logger.debug(f"阶段3检索文档: {doc_id}")
                    evidences = self.document_retriever.retrieve(
                        keywords=expanded_keywords,
                        max_results=max_results * 2,
                        doc_id=doc_id
                    )
                    return doc_id, evidences
                except Exception as e:
                    logger.warning(f"阶段3检索文档 {doc_id} 失败: {e}")
                    return doc_id, []
            
            # 并发检索所有文档
            expanded_evidences = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(retrieve_single_doc_expansion, doc_id): doc_id for doc_id in doc_ids}
                
                for future in as_completed(futures):
                    doc_id, evidences = future.result()
                    expanded_evidences.extend(evidences)
            
            if expanded_evidences:
                logger.info(f"  阶段3召回 {len(expanded_evidences)} 个证据")
                
                # 去重：过滤掉已有的证据
                existing_paths = {(ev.doc_id, ev.file_path) for ev in result.evidences}
                new_evidences = [
                    ev for ev in expanded_evidences
                    if (ev.doc_id, ev.file_path) not in existing_paths
                ]
                
                if new_evidences:
                    logger.info(f"  新增 {len(new_evidences)} 个证据（已去重）")
                    logger.info("")
                    logger.info("步骤5: 验证阶段3检索结果（打分）")
                    
                    # 与原文检索一致：过滤0.txt + 合并 + 验证
                    new_max_score = verify_and_merge(
                        stage="阶段3批量检索",
                        query=query,
                        verification_query=verification_query,
                        new_evidences=new_evidences,
                        result=result,
                        verifier=self.verifier,
                        config=self.config,
                        logger=logger,
                        keywords=None,  # 不覆盖关键词，最后统一更新
                        reasoning=f"阶段3批量检索，原始关键词: {original_keywords}, 扩展关键词: {expanded_keywords}"
                    )
                    
                    max_score = max(max_score, new_max_score)
                    all_keywords.extend(expanded_keywords)
                else:
                    logger.info("  阶段3未找到新证据（已去重）")
            else:
                logger.info("  阶段3未召回结果")
        
        # 更新结果：统一更新关键词和最终状态
        result.keywords = list(set(all_keywords)) if all_keywords else [query]
        result.evidence_sufficient = max_score >= min_score_threshold
        result.citations = self.document_retriever.build_citations(result.evidences)
        
        logger.info(f"批量检索完成 | 证据: {len(result.evidences)} 个 | 引用: {len(result.citations)} 个 | 最高分: {max_score:.3f}")
        logger.info("=" * 80)
        
        return result
    
    def retrieve(self, query: str, max_results: int = 200, 
                 doc_id: Optional[str] = None, use_query_planning: bool = True,
                 stage: int = 3) -> RetrievalResult:
        """
        执行Anti-RAG检索流程
        
        流程：
        1. 先用原文检索
        2. 如果无召回或验证分数低，启动查询规划模式
        3. 使用查询规划的策略重新检索
        
        Args:
            query: 用户查询（自然语言）
            max_results: 最大返回结果数
            doc_id: 文档ID（可选）
            use_query_planning: 是否允许使用查询规划（默认True）
            stage: 检索阶段控制（1=仅原文，2=原文+分词，3=全流程，默认3）
            
        Returns:
            检索结果
        """
        # 规范化阶段参数
        stage = max(1, min(stage, 3))
        enable_segmentation = stage >= 2
        enable_expansion = stage >= 3
        
        # 如果是单文档检索，输出完整日志；多文档检索时由调用方控制日志
        if doc_id:
            logger.info("=" * 80)
            logger.info(f"Anti-RAG检索流程开始 | 查询: {query} | 文档: {doc_id} | 阶段: {stage}")
        else:
            logger.info("=" * 80)
            logger.info(f"Anti-RAG检索流程开始 | 查询: {query} | 阶段: {stage}")

        # 先做意图识别，为验证打分提供完整语义
        intent_query = query
        intent_reasoning = ""
        if self.intent_analyzer:
            intent_result = self.intent_analyzer.analyze(query)
            intent_query = (intent_result.get("intent") or query).strip() or query
            intent_reasoning = intent_result.get("reasoning", "")
            logger.info(f"意图识别: {intent_query}")
            if intent_reasoning:
                logger.debug(f"意图推理: {intent_reasoning}")
        verification_query = self._build_verification_query(query, intent_query)

        # 初始化结果对象
        result = RetrievalResult(
            query=query,
            intent_query=intent_query,
            intent_reasoning=intent_reasoning,
            needs_retrieval=True,
            reasoning="执行原文检索流程",
            keywords=[query]  # 初始使用原文作为关键词
        )
        
        # 初始化变量，避免后续使用时报错
        quality_config = self.config.get("quality", {})
        max_score = 0.0
        min_score_threshold = quality_config.get("min_score_threshold", 0.5)
        
        # ========== 第一阶段：原文检索 ==========
        logger.info("阶段1: 原文检索")
        
        # 使用原文作为关键词进行检索（不带权重）
        original_keywords = [query]
        evidences = self.document_retriever.retrieve(
            keywords=original_keywords,
            max_results=max_results,
            doc_id=doc_id
        )
        
        result.keywords = original_keywords
        result.evidences = evidences
        result.total_results = len(evidences)
        
        # 初始化扩展检索标志
        needs_planning = False
        
        # 如果召回结果，进行打分
        if evidences:
            logger.info(f"  召回 {len(evidences)} 个证据")
            
            # 保存原始检索分数
            for ev in evidences:
                ev.retrieval_score = ev.relevance_score
            
            # 原文检索：过滤深层 0.txt（一级保留，二级及以上移除）
            evidences = filter_deep_zero_txt(evidences, "原文检索", logger)

            # 路径/行号去重合并，减少后续验证数量
            evidences = dedupe_merge_by_path_lines(evidences, "原文检索", logger)

            # 先按检索分数由高到低排序
            evidences.sort(key=lambda x: x.retrieval_score, reverse=True)
            
            # 限制验证数量最多100个
            if len(evidences) > max_results:
                logger.info(f"限制验证数量: {len(evidences)} -> {max_results} 个")
                evidences = evidences[:max_results]
            
            logger.info(f"步骤2: 验证 {len(evidences)} 个证据")
            
            verification_scores = self.verifier.verify(verification_query, evidences)
            result.verification_scores = verification_scores
            
            # 根据验证分数过滤和排序证据
            # 使用与min_score_threshold相同的默认值，确保阈值一致性
            verification_score_threshold = quality_config.get("verification_score_threshold", min_score_threshold)
            
            if verification_scores and verification_score_threshold > 0:
                original_count = len(evidences)
                # 过滤掉验证分数低于阈值的证据
                filtered_evidences = []
                filtered_scores = {}
                new_index = 0
                
                for i, ev in enumerate(evidences):
                    score_key = str(i)
                    if score_key in verification_scores:
                        ver_score = verification_scores[score_key]
                        # 使用 > 而不是 >= 来严格过滤阈值分数
                        if ver_score > verification_score_threshold:
                            # 保留该证据
                            filtered_evidences.append(ev)
                            # 用验证分数替换相关性分数（用于排序和显示）
                            ev.relevance_score = ver_score
                            # 更新验证分数索引
                            filtered_scores[str(new_index)] = ver_score
                            new_index += 1
                
                evidences = filtered_evidences
                result.verification_scores = filtered_scores
                filtered_count = original_count - len(evidences)
                
                if filtered_count > 0:
                    logger.info(f"验证分数过滤: {filtered_count} 个（阈值: {verification_score_threshold:.2f}）")
                
                # 按验证分数排序（降序）
                evidences.sort(key=lambda x: x.relevance_score, reverse=True)
            elif verification_scores:
                # 如果没有设置阈值，仍然用验证分数替换相关性分数并排序
                for i, ev in enumerate(evidences):
                    score_key = str(i)
                    if score_key in verification_scores:
                        ev.relevance_score = verification_scores[score_key]
                # 按验证分数排序（降序）
                evidences.sort(key=lambda x: x.relevance_score, reverse=True)
            else:
                # 如果没有验证分数，按检索分数排序（降序）
                evidences.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # 确保所有证据都保存了检索分数
            for ev in evidences:
                if ev.retrieval_score == 0.0 and ev.relevance_score > 0:
                    # 如果检索分数为0，说明可能没有保存，尝试从relevance_score恢复
                    # 但这种情况不应该发生，因为上面已经保存了
                    pass
            
            result.evidences = evidences
            result.total_results = len(evidences)
            
            # 检查是否需要启动查询规划
            max_score = max(verification_scores.values()) if verification_scores else 0.0
            # min_score_threshold 已在函数开始时初始化
            
            if max_score >= min_score_threshold and len(evidences) > 0:
                # 原文检索成功，不需要查询规划
                logger.info(f"原文检索成功: 最高分 {max_score:.2f} >= 阈值 {min_score_threshold:.2f}")
                result.reasoning = f"使用原文检索成功，最高分数: {max_score:.2f}"
                needs_planning = False
            else:
                # 原文检索结果不足，需要启动查询规划
                logger.info(f"原文检索结果不足: 最高分 {max_score:.2f} < 阈值 {min_score_threshold:.2f}，启动查询规划")
                needs_planning = use_query_planning
        else:
            # 没有召回结果
            logger.info("原文检索未召回结果，启动查询规划")
            # max_score 和 min_score_threshold 已在函数开始时初始化
            max_score = 0.0  # 明确设置为0，表示没有召回结果
            needs_planning = use_query_planning
        
        # ========== 迭代检索：大模型分词+权重分配（备用方案）==========
        # 第二轮：仅分词+权重；如果仍不足，再进入第三轮扩展
        needs_segmentation = (
            enable_segmentation and (not result.evidences or max_score < min_score_threshold)
        )
        
        iteration = 1
        max_iterations = 1  # 第二轮只做大模型分词+权重，失败再进入第三轮扩展
        
        if needs_segmentation:
            logger.info("")
            logger.info("阶段2: 分词加权检索（第二轮，对应分词+权重提示词）")
        while needs_segmentation and iteration <= max_iterations:
            logger.info(f"迭代检索 {iteration}: 使用大模型进行分词和权重分配")
            
            # 调用大模型进行分词和权重分配
            weighted_keywords = self._get_weighted_keywords_from_llm(query, max_score if evidences else 0.0)
            
            if not weighted_keywords:
                logger.warning("  大模型分词失败，使用默认策略")
                break
            
            logger.info(f"  分词结果（带权重）: {weighted_keywords}")
            
            # 使用带权重的关键词进行检索
            expanded_evidences = self.document_retriever.retrieve(
                keywords=[kw["keyword"] for kw in weighted_keywords],
                keyword_weights={kw["keyword"]: kw["weight"] for kw in weighted_keywords},
                max_results=max_results * (iteration + 1),  # 每次迭代扩大检索范围
                doc_id=doc_id
            )
            
            if expanded_evidences:
                logger.info(f"  迭代检索 {iteration} 召回 {len(expanded_evidences)} 个证据")
                
                # 去重：过滤掉已有的证据
                existing_paths = {(ev.doc_id, ev.file_path) for ev in evidences}
                new_evidences = [
                    ev for ev in expanded_evidences
                    if (ev.doc_id, ev.file_path) not in existing_paths
                ]
                
                if new_evidences:
                    logger.info(f"  新增 {len(new_evidences)} 个证据（已去重）")
                    logger.info("")
                    logger.info(f"步骤{2 + iteration}: 验证迭代检索结果（打分）")
                    
                    # 与原文检索一致：过滤0.txt + 合并 + 验证
                    new_max_score = verify_and_merge(
                        stage=f"迭代检索 {iteration}",
                        query=query,
                        verification_query=verification_query,
                        new_evidences=new_evidences,
                        result=result,
                        verifier=self.verifier,
                        config=self.config,
                        logger=logger,
                        keywords=[kw["keyword"] for kw in weighted_keywords],
                        reasoning=f"迭代检索 {iteration}，原始查询: {query}, 分词关键词: {[kw['keyword'] for kw in weighted_keywords]}"
                    )
                    min_score_threshold = quality_config.get("min_score_threshold", 0.5)
                    
                    if new_max_score >= min_score_threshold and len(evidences) > 0:
                        logger.info(f"  迭代检索 {iteration} 成功: 最高分数 {new_max_score:.2f} >= 阈值 {min_score_threshold:.2f}")
                        needs_segmentation = False
                        max_score = max(max_score, new_max_score)
                    else:
                        logger.info(f"  迭代检索 {iteration} 结果仍不足: 最高分数 {new_max_score:.2f} < 阈值 {min_score_threshold:.2f}")
                        max_score = max(max_score, new_max_score)
                        iteration += 1
                else:
                    logger.info("  迭代检索未找到新证据（已去重）")
                    break
            else:
                logger.info("  迭代检索未召回结果")
                break
        
        # ========== 第三阶段：关键词扩展 + 扩大搜索（保留作为后备） ==========
        needs_expansion = (
            enable_expansion and (not result.evidences or max_score < min_score_threshold)
        )
        if needs_expansion:
            logger.info("")
            logger.info("阶段3: 关键词扩展 + 扩大搜索（第三轮，对应扩展提示词）")
            
            # 提取扩展关键词（使用查询优化器的扩展提示词）
            expanded_keywords = []
            try:
                expanded_keywords = self.query_optimizer.expand_keywords(
                    query=query,
                    original_keywords=original_keywords,
                    context="前两轮召回不足"
                )
                # 确保至少包含原文
                if not expanded_keywords:
                    expanded_keywords = original_keywords
            except Exception as e:
                logger.warning(f"  关键词扩展失败，回退使用原始关键词: {e}")
                expanded_keywords = original_keywords
            
            logger.info(f"  扩展关键词: {expanded_keywords}")
            
            # 使用扩展关键词进行扩大搜索
            expanded_evidences = self.document_retriever.retrieve(
                keywords=expanded_keywords,
                max_results=max_results * 2,  # 扩大检索范围
                doc_id=doc_id
            )
            
            if expanded_evidences:
                logger.info(f"  扩展检索召回 {len(expanded_evidences)} 个证据")
                
                # 去重：过滤掉第一阶段已有的证据
                existing_paths = {(ev.doc_id, ev.file_path) for ev in evidences}
                new_evidences = [
                    ev for ev in expanded_evidences
                    if (ev.doc_id, ev.file_path) not in existing_paths
                ]
                
                if new_evidences:
                    logger.info(f"  新增 {len(new_evidences)} 个证据（已去重）")
                    logger.info("")
                    logger.info("步骤3: 验证扩展检索结果（打分）")
                    
                    # 与原文检索一致：过滤0.txt + 合并 + 验证
                    new_max_score = verify_and_merge(
                        stage="扩展检索",
                        query=query,
                        verification_query=verification_query,
                        new_evidences=new_evidences,
                        result=result,
                        verifier=self.verifier,
                        config=self.config,
                        logger=logger,
                        keywords=expanded_keywords,
                        reasoning=f"使用扩展关键词检索，原始关键词: {original_keywords}, 扩展关键词: {expanded_keywords}"
                    )
                    
                    logger.info(f"  阶段2完成: 总证据数 {len(result.evidences)}，阶段最高分 {new_max_score:.2f}")
                else:
                    logger.info("  扩展检索未找到新证据（已去重）")
            else:
                logger.info("  扩展检索未召回结果")
        
        # 步骤4: 最终排序（验证后）——不再去重，仅排序并同步分数字典
        if result.evidences:
            # 按验证分数（已写入 relevance_score）降序排序
            result.evidences.sort(key=lambda x: x.relevance_score, reverse=True)

            # 同步 verification_scores 索引，确保与排序后一致
            result.verification_scores = {
                str(idx): ev.relevance_score for idx, ev in enumerate(result.evidences)
            }

            # 记录排序结果
            max_score = result.evidences[0].relevance_score
            min_score = result.evidences[-1].relevance_score
            logger.info(f"证据排序完成: {len(result.evidences)} 个证据，最高分 {max_score:.3f}, 最低分 {min_score:.3f}")
        
        # 步骤5: 构建引用
        citations = self.document_retriever.build_citations(result.evidences)
        result.citations = citations
        
        logger.info("=" * 80)
        logger.info(f"检索完成 | 证据: {len(result.evidences)} 个 | 引用: {len(result.citations)} 个 | 关键词: {', '.join(result.keywords[:3])}{'...' if len(result.keywords) > 3 else ''}")
        
        return result
    
    @staticmethod
    def _build_verification_query(original_query: str, intent_query: str) -> str:
        """
        构造用于验证打分的查询文本：
        - 优先使用意图识别结果
        - 若未识别到意图则回退到原始提问
        """
        cleaned_intent = (intent_query or "").strip()
        if not cleaned_intent:
            return original_query
        return cleaned_intent

    def _assess_evidence_quality(self, verification_scores: dict, evidences: list, config: dict) -> dict:
        """
        评估证据质量，判断是否需要继续检索
        
        Args:
            verification_scores: 验证分数字典
            evidences: 证据列表
            config: 配置字典
            
        Returns:
            包含评估结果的字典
        """
        if not verification_scores or not evidences:
            return {
                "sufficient": False,
                "needs_more": True,
                "assessment": "未找到证据或验证失败"
            }
        
        # 从配置中获取阈值（默认值）
        quality_config = config.get("quality", {})
        min_score_threshold = quality_config.get("min_score_threshold", 0.5)  # 最低分数阈值
        high_score_threshold = quality_config.get("high_score_threshold", 0.7)  # 高分数阈值
        min_high_score_count = quality_config.get("min_high_score_count", 1)  # 至少需要的高分数证据数
        min_avg_score = quality_config.get("min_avg_score", 0.4)  # 最低平均分数
        
        # 计算统计信息
        scores = list(verification_scores.values())
        max_score = max(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0
        high_score_count = sum(1 for s in scores if s >= high_score_threshold)
        
        # 判断逻辑
        assessment_parts = []
        
        # 检查最高分数
        if max_score < min_score_threshold:
            assessment_parts.append(f"最高验证分数({max_score:.2f})低于阈值({min_score_threshold})")
            return {
                "sufficient": False,
                "needs_more": True,
                "assessment": "；".join(assessment_parts) if assessment_parts else f"最高分数: {max_score:.2f}"
            }
        
        # 检查是否有足够的高质量证据
        if high_score_count < min_high_score_count:
            assessment_parts.append(f"高质量证据数量({high_score_count})不足(需要{min_high_score_count}个)")
        
        # 检查平均分数
        if avg_score < min_avg_score:
            assessment_parts.append(f"平均验证分数({avg_score:.2f})低于阈值({min_avg_score})")
        
        # 综合判断
        sufficient = (
            max_score >= min_score_threshold and
            high_score_count >= min_high_score_count and
            avg_score >= min_avg_score
        )
        
        if not assessment_parts:
            assessment_parts.append(f"证据质量良好(最高:{max_score:.2f}, 平均:{avg_score:.2f}, 高质量:{high_score_count}个)")
        
        return {
            "sufficient": sufficient,
            "needs_more": not sufficient,
            "assessment": "；".join(assessment_parts)
        }
    
    def _get_weighted_keywords_from_llm(self, query: str, current_max_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        使用大模型进行分词并分配权重（根据通用性原则）
        
        Args:
            query: 原始查询
            current_max_score: 当前检索的最高分数（用于反馈）
            
        Returns:
            带权重的关键词列表 [{"keyword": "关键词", "weight": 0.9}, ...]
        """
        # 构建质量反馈
        if current_max_score > 0:
            quality_feedback = f"当前检索最高分数: {current_max_score:.2f}，分数较低，需要优化关键词"
        else:
            quality_feedback = "未召回结果，需要优化关键词"
        
        prompt = format_keyword_segmentation_weight(query, quality_feedback)
        
        try:
            from openai import OpenAI
            import httpx
            import json
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai")
            return []
        
        llm_config = self.config.get("openai", {})
        client = OpenAI(
            base_url=llm_config.get("base_url", "http://localhost:8000/v1"),
            api_key=llm_config.get("api_key", ""),
            timeout=httpx.Timeout(self.config.get("processing", {}).get("timeout", 120), connect=10.0)
        )
        
        try:
            response = client.chat.completions.create(
                model=llm_config.get("model", "gpt-3.5-turbo"),
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
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
            try:
                # 移除可能的代码块标记
                if response_text.startswith("```"):
                    first_newline = response_text.find("\n")
                    if first_newline > 0:
                        response_text = response_text[first_newline:].strip()
                    if response_text.endswith("```"):
                        response_text = response_text[:-3].strip()
                
                result_dict = json.loads(response_text)
                keywords_data = result_dict.get("keywords", [])
                
                # 验证并格式化结果
                weighted_keywords = []
                for kw_data in keywords_data:
                    if isinstance(kw_data, dict):
                        keyword = kw_data.get("keyword", "")
                        weight = float(kw_data.get("weight", 0.5))
                        # 确保权重在合理范围内
                        weight = max(0.1, min(1.0, weight))
                        if keyword:
                            weighted_keywords.append({"keyword": keyword, "weight": weight})
                    elif isinstance(kw_data, str):
                        # 兼容格式：只有关键词，没有权重
                        weighted_keywords.append({"keyword": kw_data, "weight": 0.5})
                
                # 确保第一个是原始查询，权重1.0
                if weighted_keywords and weighted_keywords[0]["keyword"] != query:
                    weighted_keywords.insert(0, {"keyword": query, "weight": 1.0})
                elif not weighted_keywords:
                    weighted_keywords.append({"keyword": query, "weight": 1.0})
                else:
                    weighted_keywords[0]["weight"] = 1.0  # 确保原始查询权重最高
                
                return weighted_keywords
                
            except json.JSONDecodeError as e:
                logger.error(f"  解析JSON失败: {e}")
                # 返回默认值
                return [{"keyword": query, "weight": 1.0}]
            
        except Exception as e:
            logger.error(f"调用大模型分词失败: {e}")
            # 返回默认值
            return [{"keyword": query, "weight": 1.0}]
    
    
    def _load_config(self, config_path: Path) -> dict:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"  配置文件加载成功: {config_path}")
            return config
        except Exception as e:
            logger.warning(f"  配置文件加载失败: {e}，使用默认配置")
            return {
                "openai": {
                    "base_url": "http://localhost:8000/v1",
                    "api_key": "",
                    "model": "gpt-3.5-turbo"
                },
                "processing": {
                    "timeout": 120,
                    "enable_intent_analysis": True,
                    "intent_max_tokens": 400
                },
                "quality": {
                    "min_score_threshold": 0.5,
                    "high_score_threshold": 0.7,
                    "min_high_score_count": 1,
                    "min_avg_score": 0.4,
                    "final_score_threshold": 0.3
                }
            }

