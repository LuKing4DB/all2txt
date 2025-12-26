"""
文件内容缓存模块
实现文件内容的缓存机制，避免重复读取
"""

import hashlib
from pathlib import Path
from typing import Dict, Optional
from collections import OrderedDict
from utils.logger import get_logger

logger = get_logger(__name__)


class FileCache:
    """文件内容缓存"""
    
    def __init__(self, max_size: int = 1000):
        """
        初始化文件缓存
        
        Args:
            max_size: 最大缓存文件数
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, str] = OrderedDict()  # 使用OrderedDict实现FIFO
        self.cache_hashes: Dict[str, str] = {}  # 文件哈希值，用于判断文件是否修改
    
    def get(self, file_path: Path) -> Optional[str]:
        """
        获取文件内容（带缓存）
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容，如果读取失败返回None
        """
        cache_key = str(file_path)
        
        # 检查缓存是否存在且文件未修改
        if cache_key in self.cache:
            current_hash = self._get_file_hash(file_path)
            if self.cache_hashes.get(cache_key) == current_hash:
                # 更新访问顺序（LRU）
                self.cache.move_to_end(cache_key)
                return self.cache[cache_key]
        
        # 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.debug(f"读取文件失败 {file_path}: {e}")
            return None
        
        # 更新缓存
        self._update_cache(cache_key, content, file_path)
        
        return content
    
    def _update_cache(self, cache_key: str, content: str, file_path: Path):
        """
        更新缓存
        
        Args:
            cache_key: 缓存键
            content: 文件内容
            file_path: 文件路径
        """
        # 如果缓存已满，删除最旧的
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            if oldest_key in self.cache_hashes:
                del self.cache_hashes[oldest_key]
        
        # 添加新缓存
        self.cache[cache_key] = content
        self.cache_hashes[cache_key] = self._get_file_hash(file_path)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """
        获取文件哈希（用于判断是否修改）
        使用文件修改时间和大小作为哈希
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件哈希字符串
        """
        try:
            stat = file_path.stat()
            return f"{stat.st_mtime}_{stat.st_size}"
        except Exception:
            return ""
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_hashes.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'cached_files': len(self.cache),
            'max_size': self.max_size
        }

