"""
文档检索器
在data目录中检索相关文档片段
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import Evidence, Citation, SearchStrategy
from retriever.lib.document_searcher import DocumentSearcher
from retriever.lib.scorer import Scorer

logger = get_logger(__name__)


class DocumentRetriever:
    """文档检索器"""
    
    def __init__(self, data_dir: str = "data",
                 use_index: bool = True,
                 use_cache: bool = True,
                 max_workers: int = 20,
                 index_cache_file: Optional[str] = None):
        """
        初始化文档检索器
        
        Args:
            data_dir: 数据目录路径
            use_index: 是否使用内存索引
            use_cache: 是否使用文件缓存
            max_workers: 并发搜索的最大线程数
            index_cache_file: 索引缓存文件路径（可选）
        """
        self.data_dir = Path(data_dir)
        self.scorer = Scorer()
        self.searcher = DocumentSearcher(
            self.scorer,
            use_index=use_index,
            use_cache=use_cache,
            max_workers=max_workers,
            index_cache_file=index_cache_file
        )
        
        logger.info(f"文档检索器初始化完成")
        logger.info(f"  数据目录: {self.data_dir}")
        logger.info(f"  使用索引: {use_index}")
        logger.info(f"  使用缓存: {use_cache}")
        logger.info(f"  并发线程数: {max_workers}")
    
    def build_index(self):
        """
        构建内存索引（如果启用）
        """
        if self.searcher.index:
            logger.info("开始构建内存索引...")
            self.searcher.build_index(self.data_dir)
            logger.info("内存索引构建完成")
        else:
            logger.warning("内存索引未启用，无法构建索引")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息字典
        """
        return self.searcher.get_cache_stats()
    
    def retrieve(self, keywords: List[str], max_results: int = 200,
                 keyword_weights: Optional[Dict[str, float]] = None, 
                 doc_id: Optional[str] = None) -> List[Evidence]:
        """
        检索文档
        
        Args:
            keywords: 关键词列表
            max_results: 最大返回结果数
            doc_id: 文档ID（可选，如果为None则搜索所有文档）
            
        Returns:
            证据列表
        """
        keywords_str = ', '.join(keywords[:3]) + ('...' if len(keywords) > 3 else '')
        logger.info(f"文档检索 | 关键词: {keywords_str} | 文档: {doc_id if doc_id else '全部'}")
        
        # 创建检索策略（支持权重）
        strategy = SearchStrategy(
            keywords=keywords,
            keyword_weights=keyword_weights or {},
            match_mode="fuzzy",
            max_results=max_results
        )
        
        # 获取要搜索的文档列表
        if doc_id:
            doc_dirs = [self.data_dir / doc_id]
        else:
            doc_dirs = [d for d in self.data_dir.iterdir() if d.is_dir() and not d.name.endswith('.pdf')]
        
        evidences = []
        
        for doc_dir in doc_dirs:
            if not doc_dir.exists():
                logger.warning(f"文档目录不存在: {doc_dir}")
                continue
            
            # 使用现有的检索器搜索split文件
            search_results = self.searcher.search_split_files(doc_dir, strategy)
            
            # 转换为Evidence对象
            for result in search_results:
                evidence = self._convert_to_evidence(result, doc_dir.name)
                evidences.append(evidence)
            
        # 按分数排序
        evidences.sort(key=lambda x: x.relevance_score, reverse=True)
        evidences = evidences[:max_results]
        
        logger.info(f"检索完成: {len(evidences)} 个证据")
        return evidences
    
    def _convert_to_evidence(self, search_result, doc_id: str) -> Evidence:
        """
        将SearchResult转换为Evidence
        
        Args:
            search_result: 检索结果
            doc_id: 文档ID
            
        Returns:
            Evidence对象
        """
        file_path = Path(search_result.file_path)
        
        # 读取文件第一行作为章节标题
        section = self._read_file_first_line(file_path)
        
        # 计算相对路径
        relative_path = str(file_path.relative_to(self.data_dir))
        
        # 转换行号（从0-based转为1-based）
        start_line = search_result.start_line + 1 if search_result.start_line is not None else None
        end_line = search_result.end_line + 1 if search_result.end_line is not None else None
        
        return Evidence(
            content=search_result.content,
            file_path=relative_path,
            doc_id=doc_id,
            section=section,
            relevance_score=search_result.score,
            start_line=start_line,  # 1-based
            end_line=end_line  # 1-based
        )
    
    def _read_file_first_line(self, file_path: Path) -> str:
        """
        读取文件的第一行作为章节标题
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件第一行内容（去除首尾空白）
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                return first_line.strip()
        except Exception as e:
            logger.debug(f"  读取文件第一行失败: {e}")
            return ""
    
    def build_citations(self, evidences: List[Evidence]) -> List[Citation]:
        """
        构建引用列表
        
        Args:
            evidences: 证据列表
            
        Returns:
            引用列表
        """
        citations = []
        seen_paths = set()
        
        for evidence in evidences:
            # 避免重复引用
            citation_key = (evidence.doc_id, evidence.file_path)
            if citation_key in seen_paths:
                continue
            seen_paths.add(citation_key)
            
            citation = Citation(
                doc_id=evidence.doc_id,
                file_path=evidence.file_path,
                section=evidence.section
            )
            citations.append(citation)
        
        return citations

