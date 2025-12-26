"""
文档搜索模块
实现split文件搜索功能（优化版本：使用内存索引、文件缓存和并发搜索）
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from utils.logger import get_logger
from retriever.lib.models import SearchStrategy, SearchResult
from retriever.lib.scorer import Scorer
from retriever.lib.file_cache import FileCache
from retriever.lib.in_memory_index import InMemoryIndex

logger = get_logger(__name__)


class DocumentSearcher:
    """文档搜索器（优化版本）"""
    
    def __init__(self, scorer: Scorer, 
                 use_index: bool = True,
                 use_cache: bool = True,
                 max_workers: int = 20,
                 index_cache_file: Optional[str] = None):
        """
        初始化文档搜索器
        
        Args:
            scorer: 评分器实例
            use_index: 是否使用内存索引
            use_cache: 是否使用文件缓存
            max_workers: 并发搜索的最大线程数
            index_cache_file: 索引缓存文件路径（可选）
        """
        self.scorer = scorer
        self.use_index = use_index
        self.use_cache = use_cache
        self.max_workers = max_workers
        
        # 初始化文件缓存
        if self.use_cache:
            self.file_cache = FileCache(max_size=1000)
        else:
            self.file_cache = None
        
        # 初始化内存索引
        if self.use_index:
            self.index = InMemoryIndex(cache_file=index_cache_file)
        else:
            self.index = None
    
    def _is_leaf_node(self, file_path: Path, split_dir: Path) -> bool:
        """
        判断文件是否为叶子节点（所在目录下没有子目录）
        
        Args:
            file_path: 文件路径
            split_dir: split根目录
            
        Returns:
            是否为叶子节点
        """
        file_dir = file_path.parent
        # 检查该目录下是否有子目录
        for item in file_dir.iterdir():
            if item.is_dir():
                return False
        return True
    
    def _is_parent_of(self, parent_file: Path, child_file: Path, split_dir: Path) -> bool:
        """
        判断parent_file是否是child_file的父文件
        
        Args:
            parent_file: 可能的父文件路径
            child_file: 子文件路径
            split_dir: split根目录
            
        Returns:
            是否为父子关系
        """
        parent_dir = parent_file.parent
        child_dir = child_file.parent
        
        # 如果child_dir是parent_dir的子目录，且parent_dir下有子目录，则parent_file是child_file的父文件
        try:
            # 检查child_dir是否是parent_dir的子目录
            if parent_dir != child_dir and parent_dir in child_dir.parents:
                # 检查parent_dir下是否有子目录（说明parent_file不是叶子节点）
                for item in parent_dir.iterdir():
                    if item.is_dir():
                        return True
        except:
            pass
        return False
    
    def _remove_parent_results(self, results: List[SearchResult], split_dir: Path) -> List[SearchResult]:
        """
        移除父文件结果：如果父子文件都命中，只保留子文件（叶子节点）
        
        Args:
            results: 检索结果列表
            split_dir: split根目录
            
        Returns:
            去重后的结果列表
        """
        if not results:
            return results
        
        # 收集所有命中的文件路径
        result_paths = {Path(r.file_path) for r in results}
        
        # 过滤结果：如果某个文件的子文件也在结果中，则移除该文件
        filtered_results = []
        removed_count = 0
        
        for result in results:
            result_path = Path(result.file_path)
            should_keep = True
            
            # 检查是否有子文件也在结果中
            for other_path in result_paths:
                if other_path != result_path and self._is_parent_of(result_path, other_path, split_dir):
                    should_keep = False
                    removed_count += 1
                    logger.debug(f"        移除父文件结果: {result_path.name}（子文件 {other_path.name} 也在结果中）")
                    break
            
            if should_keep:
                filtered_results.append(result)
        
        if removed_count > 0:
            logger.info(f"      移除了 {removed_count} 个父文件结果（保留叶子节点）")
        
        return filtered_results
    
    def search_split_files(self, doc_dir: Path, strategy: SearchStrategy) -> List[SearchResult]:
        """
        搜索split文件：在split目录及其子目录中查找，优先返回叶子节点文件
        如果split目录不存在，则回退到检索原始txt文件
        支持使用内存索引加速搜索
        
        Args:
            doc_dir: 文档目录
            strategy: 检索策略
            
        Returns:
            检索结果列表（优先返回叶子节点文件，每个结果包含命中的split文件内容）
        """
        results = []
        
        split_dir = doc_dir / f"{doc_dir.name}_split"
        if not split_dir.exists():
            logger.debug(f"      分割目录不存在: {split_dir}，尝试检索原始txt文件")
            # 回退到检索原始txt文件
            original_txt_file = doc_dir / f"{doc_dir.name}.txt"
            if original_txt_file.exists() and original_txt_file.is_file():
                logger.info(f"      找到原始txt文件: {original_txt_file}，开始检索")
                # 使用相同的搜索逻辑检索原始txt文件
                original_results = self._search_files([original_txt_file], strategy, "原始txt")
                results.extend(original_results)
                logger.info(f"      原始txt文件检索完成: 找到 {len(original_results)} 个匹配")
            else:
                logger.debug(f"      原始txt文件也不存在: {original_txt_file}")
            return results
        
        # 构建查询字符串用于索引搜索
        query_str = ' '.join(strategy.keywords[:5])  # 限制关键词数量
        
        # 如果使用索引，先通过索引找到候选文件
        if self.index and self.index.index:
            candidate_files = self.index.search(query_str)
            logger.debug(f"      索引搜索查询: '{query_str}', 找到 {len(candidate_files)} 个候选文件")
            
            # 转换为Path对象并过滤，只保留当前文档目录下的文件
            candidate_paths = []
            for file_path_str in candidate_files:
                file_path = Path(file_path_str)
                # 检查文件是否在当前文档的split目录下
                if split_dir in file_path.parents or file_path.parent.parent == split_dir:
                    candidate_paths.append(file_path)
            
            if candidate_paths:
                logger.info(f"      索引找到 {len(candidate_paths)} 个候选文件，仅搜索这些文件")
                # 只搜索候选文件
                txt_files = candidate_paths
            else:
                # 索引未找到候选文件，回退到全量搜索
                txt_files = list(split_dir.rglob("*.txt"))
                logger.debug(f"      索引未找到候选文件（查询: '{query_str}'），使用全量搜索: {len(txt_files)} 个文件")
        else:
            # 未使用索引，递归搜索split目录及其所有子目录中的文件
            txt_files = list(split_dir.rglob("*.txt"))
            logger.debug(f"      在 {split_dir} 目录及其子目录中找到 {len(txt_files)} 个文件")
        
        # 过滤文件
        filtered_files = []
        for txt_file in txt_files:
            # 仅当0.txt只有一行时才跳过（通常是占位/无内容）
            if txt_file.name == "0.txt":
                try:
                    # 使用缓存读取（如果可用）
                    if self.file_cache:
                        content = self.file_cache.get(txt_file)
                        if content:
                            line_count = len(content.split('\n'))
                        else:
                            line_count = 0
                    else:
                        line_count = 0
                        with txt_file.open("r", encoding="utf-8", errors="ignore") as f:
                            for _ in f:
                                line_count += 1
                                if line_count > 1:
                                    break
                    if line_count <= 1:
                        logger.debug(f"      跳过单行0.txt: {txt_file}")
                        continue
                except Exception as e:
                    logger.warning(f"      读取0.txt失败，默认跳过: {txt_file}，错误: {e}")
                    continue

            # 跳过TOC文件（toc.txt、outline.txt、*_outline.txt）
            if (txt_file.name == "toc.txt" 
                or txt_file.name == "outline.txt" 
                or txt_file.name.endswith("_outline.txt")):
                continue
            
            filtered_files.append(txt_file)
        
        # 分离叶子节点和非叶子节点文件
        leaf_files = []
        non_leaf_files = []
        
        for txt_file in filtered_files:
            if self._is_leaf_node(txt_file, split_dir):
                leaf_files.append(txt_file)
            else:
                non_leaf_files.append(txt_file)
        
        logger.debug(f"      叶子节点文件: {len(leaf_files)} 个，非叶子节点文件: {len(non_leaf_files)} 个")
        
        # 优先搜索叶子节点文件
        leaf_results = self._search_files(leaf_files, strategy, "叶子节点")
        results.extend(leaf_results)
        
        # 如果叶子节点结果不够，再搜索非叶子节点文件
        non_leaf_results = []
        if len(results) < strategy.max_results:
            non_leaf_results = self._search_files(non_leaf_files, strategy, "非叶子节点")
            results.extend(non_leaf_results)
        
        # 去重：如果父子文件都命中，只保留子文件（叶子节点）
        # results = self._remove_parent_results(results, split_dir)  # 已取消移除父节点逻辑
        
        logger.info(f"      找到 {len(results)} 个匹配的split文件（叶子节点: {len(leaf_results)}, 非叶子节点: {len(non_leaf_results)}）")
        return results
    
    def build_index(self, data_dir: Path):
        """
        构建内存索引（如果启用）
        
        Args:
            data_dir: 数据目录
        """
        if self.index:
            self.index.build_index(data_dir, max_workers=self.max_workers)
        else:
            logger.warning("内存索引未启用，无法构建索引")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息字典
        """
        stats = {}
        if self.file_cache:
            stats['file_cache'] = self.file_cache.get_stats()
        if self.index:
            stats['index'] = self.index.get_stats()
        return stats
    
    def _aggregate_lines(self, lines: List[str], matching_line_indices: List[int], 
                        line_scores: Dict[int, float],
                        before_lines: int = 3, after_lines: int = 4) -> List[Tuple[int, int, float]]:
        """
        聚合匹配的行（前3后4，连续命中聚合）
        
        规则：
        1. 如果一行命中，则前3后4一起命中，共同聚合为一条证据
        2. 如果连续多行命中，则一直聚合到后4不命中为止
        
        Args:
            lines: 所有行的列表
            matching_line_indices: 匹配的行索引列表（已排序）
            line_scores: 每行的分数字典 {行号: 分数}
            before_lines: 命中行前包含的行数
            after_lines: 命中行后包含的行数
            
        Returns:
            [(起始行号, 结束行号, 聚合分数), ...]
        """
        if not matching_line_indices:
            return []
        
        aggregated = []
        total_lines = len(lines)
        matching_set = set(matching_line_indices)
        
        # 处理连续命中的行段
        i = 0
        while i < len(matching_line_indices):
            # 找到连续命中的行段
            segment_start_idx = matching_line_indices[i]
            segment_end_idx = segment_start_idx
            
            # 向前扩展：找到连续命中的最后一行
            j = i
            while j < len(matching_line_indices) - 1:
                if matching_line_indices[j + 1] == matching_line_indices[j] + 1:
                    # 连续命中，继续
                    segment_end_idx = matching_line_indices[j + 1]
                    j += 1
                else:
                    break
            
            # 对于这个连续段，计算聚合范围
            # 起始位置：第一个命中行的前before_lines行
            evidence_start = max(0, segment_start_idx - before_lines)
            
            # 结束位置：需要检查连续命中后的情况
            # 从最后一个命中行开始，向后检查after_lines行
            # 如果这after_lines行中有命中的，继续延伸
            evidence_end = min(total_lines - 1, segment_end_idx + after_lines)
            
            # 检查后after_lines行范围内是否有命中，如果有则继续延伸
            # 使用循环来递归检查
            changed = True
            while changed:
                changed = False
                # 检查当前evidence_end范围内是否有新的命中行
                for check_idx in range(segment_end_idx + 1, evidence_end + 1):
                    if check_idx in matching_set:
                        # 如果命中，需要重新计算结束位置
                        new_end = min(total_lines - 1, check_idx + after_lines)
                        if new_end > evidence_end:
                            evidence_end = new_end
                            changed = True
                            break  # 重新开始检查
            
            # 计算这个证据段的分数（使用匹配行的分数加权平均）
            matching_in_segment = [idx for idx in matching_line_indices 
                                  if evidence_start <= idx <= evidence_end]
            if matching_in_segment:
                segment_scores = [line_scores.get(idx, 0.0) for idx in matching_in_segment]
                segment_score = sum(segment_scores) / len(segment_scores) if segment_scores else 0.0
            else:
                segment_score = 0.0
            
            aggregated.append((evidence_start, evidence_end, segment_score))
            
            # 移动到下一个未处理的命中行
            i = j + 1
        
        return aggregated
    
    def _search_files(self, txt_files: List[Path], strategy: SearchStrategy, file_type: str) -> List[SearchResult]:
        """
        搜索文件列表（按行检索并聚合，支持并发和缓存）
        
        Args:
            txt_files: 文件列表
            strategy: 检索策略
            file_type: 文件类型描述（用于日志）
            
        Returns:
            检索结果列表
        """
        if not txt_files:
            return []
        
        # 使用并发搜索
        results = []
        searched_count = 0
        skipped_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._search_single_file, txt_file, strategy, file_type): txt_file
                for txt_file in txt_files
            }
            
            for future in as_completed(futures):
                txt_file = futures[future]
                try:
                    file_results = future.result()
                    if file_results:
                        results.extend(file_results)
                        searched_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.debug(f"        搜索{file_type}文件失败 {txt_file}: {e}")
                    skipped_count += 1
        
        logger.debug(f"      [{file_type}] 搜索了 {searched_count} 个文件，跳过 {skipped_count} 个文件，找到 {len(results)} 个匹配")
        return results
    
    def _search_single_file(self, txt_file: Path, strategy: SearchStrategy, file_type: str) -> List[SearchResult]:
        """
        搜索单个文件
        
        Args:
            txt_file: 文件路径
            strategy: 检索策略
            file_type: 文件类型描述
            
        Returns:
            该文件的检索结果列表
        """
        try:
            # 使用缓存读取文件
            if self.file_cache:
                content = self.file_cache.get(txt_file)
            else:
                with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            
            if not content:
                return []
            
            # 如果文件太小，跳过
            if len(content) < 50:
                return []
            
            # 按行检索
            lines = content.split('\n')
            matching_lines = self.scorer.find_matching_lines(content, strategy, min_score=0.01)
            
            if not matching_lines:
                return []
            
            logger.debug(f"        [{file_type}] 文件 {txt_file.name}: 找到 {len(matching_lines)} 个匹配行")
            
            # 提取匹配的行索引和分数
            matching_line_indices = [line_idx for line_idx, score in matching_lines]
            line_scores = {line_idx: score for line_idx, score in matching_lines}
            
            # 聚合匹配的行（前3后4，连续命中聚合）
            aggregated_segments = self._aggregate_lines(
                lines, matching_line_indices, line_scores, before_lines=3, after_lines=4
            )
            
            if not aggregated_segments:
                return []
            
            logger.debug(f"        [{file_type}] 文件 {txt_file.name}: 聚合为 {len(aggregated_segments)} 个证据段")
            
            # 为每个聚合段创建结果
            file_results = []
            for start_idx, end_idx, segment_score in aggregated_segments:
                # 提取聚合段的内容
                segment_lines = lines[start_idx:end_idx + 1]
                segment_content = '\n'.join(segment_lines)
                
                # 计算聚合段的分数（使用匹配行的分数加权平均）
                matching_scores_in_segment = [line_scores.get(idx, 0.0) 
                                              for idx in range(start_idx, end_idx + 1) 
                                              if idx in line_scores]
                if matching_scores_in_segment:
                    # 使用匹配行的平均分数
                    final_score = sum(matching_scores_in_segment) / len(matching_scores_in_segment)
                else:
                    final_score = segment_score
                
                logger.debug(f"        [{file_type}] 证据段: 行{start_idx+1}-{end_idx+1}, 分数: {final_score:.3f}")
                
                file_results.append(SearchResult(
                    file_path=str(txt_file),
                    content=segment_content,
                    score=final_score,
                    context=f"文件: {txt_file.name}，行{start_idx+1}-{end_idx+1}，匹配行数: {len([idx for idx in matching_line_indices if start_idx <= idx <= end_idx])}",
                    start_line=start_idx,  # 0-based
                    end_line=end_idx  # 0-based
                ))
            
            return file_results
            
        except Exception as e:
            logger.debug(f"        搜索{file_type}文件失败 {txt_file}: {e}")
            return []

