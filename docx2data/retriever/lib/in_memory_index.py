"""
内存索引模块
构建关键词到文件的映射索引，加速搜索
"""

import pickle
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import get_logger

logger = get_logger(__name__)


class InMemoryIndex:
    """内存索引"""
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        初始化内存索引
        
        Args:
            cache_file: 索引缓存文件路径（可选）
        """
        self.cache_file = Path(cache_file) if cache_file else None
        self.index: Dict[str, List[Dict]] = {}  # {keyword: [doc_info]}
        self.doc_metadata: Dict[str, Dict] = {}  # {doc_id: metadata}
        self.file_keywords: Dict[str, Set[str]] = {}  # {file_path: set(keywords)}
        
        if self.cache_file and self.cache_file.exists():
            self.load_cache()
    
    def build_index(self, data_dir: Path, max_workers: int = 20):
        """
        构建索引：扫描所有文件，提取关键词
        
        Args:
            data_dir: 数据目录
            max_workers: 最大并发线程数
        """
        logger.info(f"开始构建内存索引: {data_dir}")
        
        # 收集所有txt文件
        all_files = []
        for doc_dir in data_dir.iterdir():
            if not doc_dir.is_dir() or doc_dir.name.endswith('.pdf'):
                continue
            
            split_dir = doc_dir / f"{doc_dir.name}_split"
            if split_dir.exists():
                txt_files = list(split_dir.rglob("*.txt"))
                # 过滤TOC文件
                txt_files = [f for f in txt_files 
                            if f.name not in ['toc.txt', 'outline.txt'] 
                            and not f.name.endswith('_outline.txt')]
                all_files.extend(txt_files)
            else:
                # 如果没有split目录，使用原始txt文件
                original_txt = doc_dir / f"{doc_dir.name}.txt"
                if original_txt.exists():
                    all_files.append(original_txt)
        
        logger.info(f"找到 {len(all_files)} 个文件需要索引")
        
        # 并发索引文件
        indexed_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._index_file, f): f for f in all_files}
            
            for future in as_completed(futures):
                try:
                    future.result()
                    indexed_count += 1
                    if indexed_count % 100 == 0:
                        logger.info(f"已索引 {indexed_count}/{len(all_files)} 个文件")
                except Exception as e:
                    file_path = futures[future]
                    logger.warning(f"索引文件失败 {file_path}: {e}")
        
        logger.info(f"索引构建完成: 共 {indexed_count} 个文件，{len(self.index)} 个关键词")
        
        # 保存缓存（如果指定了缓存文件路径）
        if self.cache_file:
            self.save_cache()
        else:
            logger.warning("未指定索引缓存文件路径，索引将不会保存，下次启动需要重新构建")
    
    def _index_file(self, file_path: Path):
        """
        索引单个文件
        
        Args:
            file_path: 文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 如果文件太小，跳过
            if len(content) < 50:
                return
            
            # 提取关键词
            keywords = self._extract_keywords(content)
            
            # 获取doc_id
            doc_id = file_path.parent.parent.name if file_path.parent.parent.name != 'data' else file_path.parent.name
            
            doc_info = {
                'file_path': str(file_path),
                'doc_id': doc_id,
                'content_length': len(content)
            }
            
            # 更新索引
            for keyword in keywords:
                if keyword not in self.index:
                    self.index[keyword] = []
                self.index[keyword].append(doc_info)
            
            # 保存文件的关键词集合
            self.file_keywords[str(file_path)] = keywords
            
        except Exception as e:
            logger.debug(f"索引文件失败 {file_path}: {e}")
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """
        提取关键词（简单分词）
        
        Args:
            text: 文本内容
            
        Returns:
            关键词集合
        """
        # 提取2-10字的中文词和2个字符以上的英文单词
        words = re.findall(r'[\u4e00-\u9fff]{2,10}|[a-zA-Z]{2,}', text)
        # 转换为小写并去重
        keywords = set(word.lower() for word in words)
        return keywords
    
    def search(self, query: str) -> List[str]:
        """
        搜索：基于内存索引快速定位文件
        
        Args:
            query: 查询字符串
            
        Returns:
            候选文件路径列表
        """
        query_words = self._extract_keywords(query)
        
        if not query_words:
            logger.debug(f"索引搜索: 查询 '{query}' 未提取到关键词")
            return []
        
        logger.debug(f"索引搜索: 查询 '{query}' 提取关键词: {list(query_words)[:10]}")
        
        # 统计每个文件的匹配度（命中关键词数）
        file_scores: Dict[str, int] = {}
        matched_keywords = []
        
        for word in query_words:
            if word in self.index:
                matched_keywords.append(word)
                for doc_info in self.index[word]:
                    file_path = doc_info['file_path']
                    file_scores[file_path] = file_scores.get(file_path, 0) + 1
        
        if matched_keywords:
            logger.debug(f"索引搜索: 匹配到 {len(matched_keywords)} 个关键词: {matched_keywords[:5]}")
        else:
            logger.debug(f"索引搜索: 查询关键词均不在索引中")
        
        # 按匹配度排序，返回候选文件
        candidate_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)
        result = [file_path for file_path, score in candidate_files]
        
        if result:
            logger.debug(f"索引搜索: 找到 {len(result)} 个候选文件（最高匹配度: {candidate_files[0][1] if candidate_files else 0}）")
        
        return result
    
    def save_cache(self):
        """保存索引缓存"""
        if not self.cache_file:
            return
        
        try:
            cache_data = {
                'index': self.index,
                'metadata': self.doc_metadata,
                'file_keywords': {k: list(v) for k, v in self.file_keywords.items()}  # Set转List以便序列化
            }
            
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"索引缓存已保存: {self.cache_file}")
        except Exception as e:
            logger.warning(f"保存索引缓存失败: {e}")
    
    def load_cache(self):
        """加载索引缓存"""
        if not self.cache_file:
            logger.debug("未指定索引缓存文件路径，跳过加载")
            return
        
        if not self.cache_file.exists():
            logger.debug(f"索引缓存文件不存在: {self.cache_file}，将需要重新构建")
            return
        
        try:
            with open(self.cache_file, 'rb') as f:
                data = pickle.load(f)
                self.index = data.get('index', {})
                self.doc_metadata = data.get('metadata', {})
                # List转Set
                file_keywords_data = data.get('file_keywords', {})
                self.file_keywords = {k: set(v) for k, v in file_keywords_data.items()}
            
            logger.info(f"索引缓存已加载: {len(self.index)} 个关键词，{len(self.file_keywords)} 个文件")
        except Exception as e:
            logger.warning(f"加载索引缓存失败: {e}，将需要重新构建")
    
    def clear(self):
        """清空索引"""
        self.index.clear()
        self.doc_metadata.clear()
        self.file_keywords.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取索引统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'keywords': len(self.index),
            'indexed_files': len(self.file_keywords),
            'total_entries': sum(len(docs) for docs in self.index.values())
        }

