"""
Anti-RAG数据模型
定义检索结果、证据和引用的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Evidence:
    """证据片段"""
    content: str  # 证据内容
    file_path: str  # 文件路径（相对于data目录）
    doc_id: str  # 文档ID
    relevance_score: float  # 相关性分数（0-1，验证后可能被替换为验证分数）
    section: str = ""  # 章节标题（文件的第一行）
    retrieval_score: float = 0.0  # 检索分数（原始相关性分数，验证前）
    start_position: Optional[int] = None  # 在文件中的起始位置
    end_position: Optional[int] = None  # 在文件中的结束位置
    start_line: Optional[int] = None  # 起始行号（1-based）
    end_line: Optional[int] = None  # 结束行号（1-based）
    
    def get_display_content(self, max_length: Optional[int] = None) -> str:
        """
        获取用于展示的证据内容
        
        Args:
            max_length: 最大长度限制（字符数），如果超过则截断并添加省略号
            
        Returns:
            格式化后的展示内容
        """
        display_content = self.content
        
        # 如果设置了行号，添加行号信息
        if self.start_line is not None and self.end_line is not None:
            if self.start_line == self.end_line:
                line_info = f"[行{self.start_line}]"
            else:
                line_info = f"[行{self.start_line}-{self.end_line}]"
            display_content = f"{line_info} {display_content}"
        
        # 如果设置了最大长度，进行截断
        if max_length is not None and len(display_content) > max_length:
            display_content = display_content[:max_length] + "..."
        
        return display_content
    
    def get_summary(self) -> str:
        """
        获取证据摘要信息（用于日志或调试）
        
        Returns:
            摘要字符串
        """
        parts = []
        
        if self.file_path:
            parts.append(f"文件: {self.file_path}")
        
        if self.start_line is not None and self.end_line is not None:
            if self.start_line == self.end_line:
                parts.append(f"行{self.start_line}")
            else:
                parts.append(f"行{self.start_line}-{self.end_line}")
        
        if self.relevance_score > 0:
            parts.append(f"分数: {self.relevance_score:.3f}")
        
        return " | ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（用于序列化）
        
        Returns:
            字典格式的证据数据
        """
        return {
            "content": self.content,
            "file_path": self.file_path,
            "doc_id": self.doc_id,
            "section": self.section,
            "relevance_score": self.relevance_score,
            "retrieval_score": self.retrieval_score,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "display_content": self.get_display_content()
        }


@dataclass
class Citation:
    """引用信息"""
    doc_id: str  # 文档ID
    file_path: str  # 文件路径
    doc_name: Optional[str] = None  # 文档名称（如果有）
    section: str = ""  # 章节标题（文件的第一行）


@dataclass
class RetrievalResult:
    """检索结果"""
    query: str  # 原始查询
    needs_retrieval: bool  # 是否需要检索（路由决策结果）
    reasoning: str  # 路由决策的推理过程
    intent_query: str = ""  # 意图识别后的查询（用于验证打分）
    intent_reasoning: str = ""  # 意图识别的推理说明
    evidences: List[Evidence] = field(default_factory=list)  # 证据列表
    citations: List[Citation] = field(default_factory=list)  # 引用列表
    verification_scores: Dict[str, float] = field(default_factory=dict)  # 验证分数
    total_results: int = 0  # 总结果数
    keywords: List[str] = field(default_factory=list)  # 检索使用的关键词
    evidence_sufficient: bool = True  # 证据是否足够（基于验证分数判断）
    needs_more_retrieval: bool = False  # 是否需要继续检索
    quality_assessment: str = ""  # 证据质量评估说明


@dataclass
class RouterDecision:
    """路由决策结果"""
    needs_retrieval: bool  # 是否需要检索
    confidence: float  # 决策置信度（0-1）
    reasoning: str  # 决策推理过程
    keywords: List[str] = field(default_factory=list)  # 提取的关键词


@dataclass
class SearchStrategy:
    """检索策略"""
    keywords: List[str]  # 关键词列表
    keyword_weights: Dict[str, float] = field(default_factory=dict)  # 关键词权重字典
    match_mode: str = "fuzzy"  # 匹配模式: "exact", "fuzzy"
    max_results: int = 30  # 最大返回结果数


@dataclass
class SearchResult:
    """检索结果"""
    file_path: str  # 文件路径
    content: str  # 匹配的内容片段
    score: float  # 相关性分数
    context: str = ""  # 上下文信息（如章节标题）
    start_line: Optional[int] = None  # 起始行号（0-based，用于内部处理）
    end_line: Optional[int] = None  # 结束行号（0-based，用于内部处理）
