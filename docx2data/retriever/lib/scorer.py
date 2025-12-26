"""
评分和匹配模块
实现文本匹配和相关性评分功能
"""

import sys
import re
import logging
from pathlib import Path
from typing import List, Tuple

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import SearchStrategy

logger = get_logger(__name__)


class Scorer:
    """评分器"""
    
    @staticmethod
    def find_matches(content: str, strategy: SearchStrategy) -> List[Tuple[str, float, int]]:
        """
        在内容中查找匹配
        
        Args:
            content: 文本内容
            strategy: 检索策略
            
        Returns:
            [(匹配文本, 分数, 位置), ...]
        """
        matches = []
        
        for keyword in strategy.keywords:
            if strategy.match_mode == "exact":
                # 精确匹配
                pos = 0
                while True:
                    pos = content.find(keyword, pos)
                    if pos == -1:
                        break
                    # 提取包含关键词的句子或段落（最多200字符）
                    start = max(0, pos - 50)
                    end = min(len(content), pos + len(keyword) + 150)
                    match_text = content[start:end].strip()
                    matches.append((match_text, 1.0, pos))
                    pos += len(keyword)
            else:
                # 模糊匹配（不区分大小写）
                pattern = re.escape(keyword)
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    # 提取包含关键词的句子或段落（最多200字符）
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 150)
                    match_text = content[start:end].strip()
                    matches.append((match_text, 0.8, match.start()))
        
        return matches
    
    @staticmethod
    def _get_keyword_weight(keyword: str, strategy: SearchStrategy, index: int) -> float:
        """
        获取关键词权重（优先使用策略中的权重，否则自动计算）
        
        Args:
            keyword: 关键词
            strategy: 检索策略
            index: 关键词索引
            
        Returns:
            权重值（0-1）
        """
        # 如果策略中已指定权重，直接使用
        if strategy.keyword_weights and keyword in strategy.keyword_weights:
            return strategy.keyword_weights[keyword]
        
        # 否则使用自动计算（向后兼容）
        # 1. 位置权重：第一个关键词（原始查询）权重最高
        position_weight = 1.0 - (index * 0.2)  # 第一个1.0，第二个0.8，第三个0.6...
        position_weight = max(position_weight, 0.3)  # 最小权重0.3
        
        # 2. 长度权重：长词更具体，权重更高
        length_weight = min(len(keyword) / 6.0, 1.0)  # 6字以上的词权重为1.0
        if len(keyword) <= 3:
            length_weight = 0.5
        
        # 3. 综合权重
        weight = (position_weight * 0.6 + length_weight * 0.4)
        
        return weight
    
    @staticmethod
    def calculate_score(text: str, strategy: SearchStrategy) -> float:
        """
        计算文本与策略的相关性分数（优化版：短语优先、自动加权）
        
        策略：
        1. 完整短语匹配获得显著加成
        2. 关键词根据位置和长度自动加权
        3. 多个关键词匹配时累加分数
        
        Args:
            text: 文本内容
            strategy: 检索策略
            
        Returns:
            相关性分数（0-1）
        """
        if not strategy.keywords:
            return 0.0
        
        text_lower = text.lower()
        
        # 计算每个关键词的权重（优先使用策略中的权重）
        keyword_weights = {}
        total_weight = 0.0
        for i, keyword in enumerate(strategy.keywords):
            weight = Scorer._get_keyword_weight(keyword, strategy, i)
            keyword_weights[keyword] = weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # 归一化权重
        keyword_weights = {k: v / total_weight for k, v in keyword_weights.items()}
        
        score = 0.0
        keyword_scores = {}
        original_query = strategy.keywords[0] if strategy.keywords else ""
        
        # 1. 优先检查完整短语匹配（第一个关键词通常是原始查询）
        if original_query and len(original_query) >= 3:
            if original_query.lower() in text_lower:
                # 完整短语匹配，给予显著加成
                phrase_weight = keyword_weights.get(original_query, 0.5)
                phrase_score = phrase_weight * 2.0  # 短语匹配加成100%
                score += min(phrase_score, 1.0)
                keyword_scores[original_query] = min(phrase_score, 1.0)
                logger.debug(f"        完整短语匹配: {original_query}, 分数: {min(phrase_score, 1.0):.2f}")
        
        # 2. 检查其他关键词匹配
        for keyword in strategy.keywords:
            if keyword in keyword_scores:
                continue  # 已经处理过（完整短语）
            
            keyword_lower = keyword.lower()
            keyword_score = 0.0
            weight = keyword_weights.get(keyword, 1.0 / len(strategy.keywords))
            
            if strategy.match_mode == "exact":
                if keyword_lower in text_lower:
                    keyword_score = weight
                    score += keyword_score
            else:
                # 模糊匹配：计算出现次数
                count = text_lower.count(keyword_lower)
                if count > 0:
                    # 出现次数越多，分数越高，但受权重限制
                    keyword_score = min(count * 0.3, 1.0) * weight
                    score += keyword_score
            
            if keyword_score > 0:
                keyword_scores[keyword] = keyword_score
        
        # 详细日志（仅在debug级别）
        if keyword_scores and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"        分数计算详情: {keyword_scores}, 总分: {score:.2f}")
        
        return min(score, 1.0)  # 确保分数不超过1.0
    
    @staticmethod
    def calculate_line_score(line: str, strategy: SearchStrategy) -> float:
        """
        计算单行与策略的相关性分数（按权重叠加）
        
        Args:
            line: 单行文本
            strategy: 检索策略
            
        Returns:
            相关性分数（0-1）
        """
        if not strategy.keywords:
            return 0.0
        
        line_lower = line.lower()
        score = 0.0
        
        # 计算每个关键词的权重（优先使用策略中的权重）
        for i, keyword in enumerate(strategy.keywords):
            # 获取关键词权重
            weight = Scorer._get_keyword_weight(keyword, strategy, i)
            
            keyword_lower = keyword.lower()
            
            if strategy.match_mode == "exact":
                if keyword_lower in line_lower:
                    score += weight
            else:
                # 模糊匹配：计算出现次数
                count = line_lower.count(keyword_lower)
                if count > 0:
                    # 出现次数越多，分数越高，但受权重限制
                    score += min(count * 0.3, 1.0) * weight
        
        return min(score, 1.0)  # 确保分数不超过1.0
    
    @staticmethod
    def find_matching_lines(content: str, strategy: SearchStrategy, min_score: float = 0.01) -> List[Tuple[int, float]]:
        """
        查找匹配的行（按行检索）
        
        Args:
            content: 文本内容
            strategy: 检索策略
            min_score: 最小分数阈值
            
        Returns:
            [(行号(0-based), 分数), ...]
        """
        lines = content.split('\n')
        matching_lines = []
        
        for line_idx, line in enumerate(lines):
            score = Scorer.calculate_line_score(line, strategy)
            if score >= min_score:
                matching_lines.append((line_idx, score))
        
        return matching_lines

