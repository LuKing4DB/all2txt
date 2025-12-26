"""
提示词模块聚合。
将不同类型的提示词拆分到独立文件，并在此统一导出。
"""

from .verifier import (
    VERIFIER_BATCH_PROMPT,
    VERIFIER_SINGLE_PROMPT,
    format_verifier_batch,
    format_verifier_single,
)
from .intent import INTENT_ANALYSIS_PROMPT, format_intent_analysis
from .keywords import (
    COMMON_FILTERING_RULES,
    KEYWORD_EXPANSION_PROMPT,
    KEYWORD_SEGMENTATION_WEIGHT_PROMPT,
    format_keyword_expansion,
    format_keyword_segmentation_weight,
)

__all__ = [
    "VERIFIER_BATCH_PROMPT",
    "VERIFIER_SINGLE_PROMPT",
    "INTENT_ANALYSIS_PROMPT",
    "COMMON_FILTERING_RULES",
    "KEYWORD_EXPANSION_PROMPT",
    "KEYWORD_SEGMENTATION_WEIGHT_PROMPT",
    "format_verifier_batch",
    "format_verifier_single",
    "format_intent_analysis",
    "format_keyword_expansion",
    "format_keyword_segmentation_weight",
]

