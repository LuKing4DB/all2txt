"""
验证器提示词模板与格式化函数。
"""

VERIFIER_BATCH_PROMPT = """你是一个文档验证器。根据用户的查询，评估每个检索到的证据片段的相关性和准确性。

用户查询: {query}

检索到的证据片段:
{evidence_list}

请评估每个证据片段与查询的相关性，返回JSON格式：
{{
    "0": 0.0-1.0,  // 证据0的相关性分数
    "1": 0.0-1.0,  // 证据1的相关性分数
    ...
}}

评分标准：
- 1.0: 完全相关，直接回答查询
- 0.7-0.9: 高度相关，包含重要信息
- 0.4-0.6: 部分相关，包含一些相关信息
- 0.0-0.3: 不相关或相关性很低

只返回JSON，不要其他内容。/nothink"""

VERIFIER_SINGLE_PROMPT = """查询:{query}
证据:{content_snippet}

相关性分数(0-1):/nothink"""


def format_verifier_batch(query: str, evidence_list: str) -> str:
    """格式化批量验证提示词"""
    return VERIFIER_BATCH_PROMPT.format(query=query, evidence_list=evidence_list)


def format_verifier_single(query: str, content_snippet: str) -> str:
    """格式化单个验证提示词"""
    return VERIFIER_SINGLE_PROMPT.format(query=query, content_snippet=content_snippet)

