"""
统一的格式化工具
用于日志输出、接口返回和Web展示的统一格式化
"""

from typing import List, Dict, Any, Optional
from retriever.lib.models import Evidence, Citation, RetrievalResult


def format_evidence_unified(evidence: Evidence, index: int, verification_scores: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    统一格式化单个证据（用于日志、接口和Web展示）
    
    Args:
        evidence: 证据对象
        index: 证据索引（从0开始）
        verification_scores: 验证分数字典（可选）
        
    Returns:
        格式化后的证据字典
    """
    # 获取验证分数
    verification_score = None
    if verification_scores:
        verification_score = verification_scores.get(str(index), None)
    if verification_score is None:
        verification_score = evidence.relevance_score
    
    # 获取检索分数
    retrieval_score = evidence.retrieval_score if evidence.retrieval_score > 0 else evidence.relevance_score
    
    # 构建行号信息
    line_info = None
    if evidence.start_line is not None and evidence.end_line is not None:
        if evidence.start_line == evidence.end_line:
            line_info = f"行{evidence.start_line}"
        else:
            line_info = f"行{evidence.start_line}-{evidence.end_line}"
    
    # 构建文件路径信息
    file_info_parts = []
    if evidence.doc_id:
        file_info_parts.append(f"文档: {evidence.doc_id}")
    if evidence.file_path:
        file_info_parts.append(f"文件: {evidence.file_path}")
    if line_info:
        file_info_parts.append(line_info)
    
    file_info = " | ".join(file_info_parts) if file_info_parts else ""
    
    # 生成不包含行号的显示内容（因为行号已经在file_info中显示了）
    display_content = evidence.content
    if len(display_content) > 500:
        display_content = display_content[:500] + "..."
    
    return {
        "index": index + 1,  # 显示索引从1开始
        "retrieval_score": retrieval_score,
        "verification_score": verification_score,
        "relevance_score": evidence.relevance_score,
        "doc_id": evidence.doc_id,
        "file_path": evidence.file_path,
        "section": evidence.section or "",
        "content": evidence.content,
        "display_content": display_content,  # 不包含行号的内容
        "line_info": line_info,
        "file_info": file_info,
        "start_line": evidence.start_line,
        "end_line": evidence.end_line,
        # 用于日志输出的格式化字符串
        "log_header": f"证据 {index + 1} (检索分数: {retrieval_score:.2f}, 验证分数: {verification_score:.2f})",
        "log_file_info": file_info,
    }


def format_citation_unified(citation: Citation, index: int) -> Dict[str, Any]:
    """
    统一格式化单个引用（用于日志、接口和Web展示）
    
    Args:
        citation: 引用对象
        index: 引用索引（从0开始）
        
    Returns:
        格式化后的引用字典
    """
    citation_info_parts = []
    if citation.doc_id:
        citation_info_parts.append(f"文档: {citation.doc_id}")
    if citation.file_path:
        citation_info_parts.append(f"路径: {citation.file_path}")
    if citation.section:
        citation_info_parts.append(f"章节: {citation.section}")
    
    citation_info = " | ".join(citation_info_parts) if citation_info_parts else ""
    
    return {
        "index": index + 1,  # 显示索引从1开始
        "doc_id": citation.doc_id,
        "file_path": citation.file_path,
        "section": citation.section or "",
        "citation_info": citation_info,
        # 用于日志输出的格式化字符串
        "log_header": f"引用 {index + 1}:",
    }


def format_result_for_log(result: RetrievalResult, keywords: Optional[List[str]] = None) -> str:
    """
    格式化检索结果用于日志输出
    
    Args:
        result: 检索结果对象
        keywords: 关键词列表（用于提取相关内容片段）
        
    Returns:
        格式化后的日志字符串
    """
    output = []
    output.append("=" * 80)
    output.append("Anti-RAG检索结果")
    output.append("=" * 80)
    output.append(f"查询: {result.query}")
    output.append(f"路由决策: {'需要检索' if result.needs_retrieval else '不需要检索'}")
    output.append(f"决策推理: {result.reasoning}")
    
    # 显示证据质量评估
    if result.needs_retrieval and result.quality_assessment:
        output.append(f"证据质量评估: {result.quality_assessment}")
        output.append(f"证据是否足够: {'是' if result.evidence_sufficient else '否'}")
        if result.needs_more_retrieval:
            output.append("⚠️  建议继续检索以获取更多相关证据")
    
    output.append("")
    
    if not result.needs_retrieval:
        output.append("根据路由决策，此查询不需要检索外部文档。")
        return "\n".join(output)
    
    if not result.evidences:
        output.append("未找到相关证据。")
        return "\n".join(output)
    
    output.append(f"找到 {len(result.evidences)} 个证据片段，{len(result.citations)} 个引用")
    output.append("")
    
    # 显示证据
    output.append("-" * 80)
    output.append("证据片段（仅显示直接相关内容）")
    output.append("-" * 80)
    
    for i, evidence in enumerate(result.evidences):
        formatted = format_evidence_unified(evidence, i, result.verification_scores)
        output.append("")
        output.append(formatted["log_header"])
        # 如果有章节信息，显示章节（在证据号下方，文档信息上方）
        if formatted["section"]:
            output.append(f"章节: {formatted['section']}")
        output.append(formatted["log_file_info"])
        output.append("")
        output.append("相关内容片段:")
        output.append(formatted["display_content"])
        output.append("-" * 80)
    
    # 显示引用
    if result.citations:
        output.append("")
        output.append("-" * 80)
        output.append("引用列表")
        output.append("-" * 80)
        
        for i, citation in enumerate(result.citations):
            formatted = format_citation_unified(citation, i)
            output.append("")
            output.append(formatted["log_header"])
            output.append(f"  {formatted['citation_info']}")
    
    output.append("")
    output.append("=" * 80)
    
    return "\n".join(output)


def format_result_for_api(result: RetrievalResult) -> Dict[str, Any]:
    """
    格式化检索结果用于API返回
    
    Args:
        result: 检索结果对象
        
    Returns:
        格式化后的字典（可直接序列化为JSON）
    """
    return {
        "query": result.query,
        "needs_retrieval": result.needs_retrieval,
        "reasoning": result.reasoning,
        "evidences": [
            format_evidence_unified(ev, i, result.verification_scores)
            for i, ev in enumerate(result.evidences)
        ],
        "citations": [
            format_citation_unified(cit, i)
            for i, cit in enumerate(result.citations)
        ],
        "total_results": result.total_results,
        "keywords": result.keywords,
        "verification_scores": result.verification_scores,
        "evidence_sufficient": result.evidence_sufficient,
        "needs_more_retrieval": result.needs_more_retrieval,
        "quality_assessment": result.quality_assessment
    }

