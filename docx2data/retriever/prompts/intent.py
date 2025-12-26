"""
意图识别器提示词模板与格式化函数。
"""

INTENT_ANALYSIS_PROMPT = """你是检索意图识别助手，需将简短或不完整的用户提问转换为可用于验证的完整描述。

请基于用户原始输入推断其真实需求，补充缺失信息（如主体、客体、时间、地点、限制条件），但不要幻想不存在的约束。

用户原始输入: {query}

输出JSON：
{{
  "intent": "补全后的验证用查询，清晰表达用户真正想要查找的内容",
  "reasoning": "你是如何理解该需求的（可简短说明）"
}}

要求：
- intent需可直接用于判断证据是否满足需求，避免无关展开
- 不要把意图改写成疑问句，优先用贴近答案语义的陈述句表达
- 若无法确定，保留原文并说明假设
- 只返回JSON，不要其他内容。/nothink"""


def format_intent_analysis(query: str) -> str:
    """格式化意图识别提示词"""
    return INTENT_ANALYSIS_PROMPT.format(query=query)

