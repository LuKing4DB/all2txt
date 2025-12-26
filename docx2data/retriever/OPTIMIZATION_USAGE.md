# 文件查询优化使用说明

## 概述

按照方案C（优化文件系统）实现了文件查询优化，包括：

1. **内存索引**：构建关键词到文件的映射，快速定位候选文件
2. **文件缓存**：缓存文件内容，避免重复读取
3. **并发搜索**：使用线程池并发搜索文件，提升性能

## 主要改进

### 1. 内存索引（InMemoryIndex）

- 自动提取文件中的关键词（2-10字中文词，2字符以上英文单词）
- 构建关键词到文件的倒排索引
- 支持索引缓存，避免重复构建
- 搜索时先通过索引定位候选文件，减少需要搜索的文件数量

### 2. 文件缓存（FileCache）

- LRU缓存机制，自动管理缓存大小
- 通过文件修改时间和大小判断文件是否变更
- 避免重复读取相同文件，提升性能

### 3. 并发搜索

- 使用线程池并发搜索多个文件
- 可配置并发线程数（默认20）
- 显著提升多文件搜索性能

## 使用方法

### 基本使用（启用所有优化）

```python
from pathlib import Path
from retriever.lib.document_retriever import DocumentRetriever

# 初始化检索器（默认启用索引和缓存）
retriever = DocumentRetriever(
    data_dir="data",
    use_index=True,      # 启用内存索引
    use_cache=True,      # 启用文件缓存
    max_workers=20,      # 并发线程数
    index_cache_file="search_index.pkl"  # 索引缓存文件路径（可选）
)

# 首次使用需要构建索引（一次性操作）
retriever.build_index()

# 检索文档
evidences = retriever.retrieve(
    keywords=["关键词1", "关键词2"],
    max_results=20,
    doc_id=None  # None表示搜索所有文档
)
```

### 仅使用缓存（不使用索引）

```python
retriever = DocumentRetriever(
    data_dir="data",
    use_index=False,     # 禁用索引
    use_cache=True,      # 启用缓存
    max_workers=20
)

# 不需要构建索引
evidences = retriever.retrieve(keywords=["关键词"], max_results=20)
```

### 不使用任何优化（保持原有行为）

```python
retriever = DocumentRetriever(
    data_dir="data",
    use_index=False,     # 禁用索引
    use_cache=False,     # 禁用缓存
    max_workers=1        # 单线程
)

evidences = retriever.retrieve(keywords=["关键词"], max_results=20)
```

## 性能优化建议

### 1. 索引构建

- **首次使用**：需要构建索引，可能需要一些时间（取决于文件数量）
- **后续使用**：如果指定了`index_cache_file`，索引会自动加载，无需重新构建
- **索引更新**：当文件变更时，需要重新构建索引（删除缓存文件或调用`build_index()`）

### 2. 缓存配置

- **缓存大小**：默认缓存1000个文件，可根据内存情况调整
- **缓存清理**：缓存会自动管理，使用LRU策略淘汰旧文件

### 3. 并发配置

- **线程数**：默认20个线程，可根据CPU核心数和I/O性能调整
- **建议值**：
  - CPU密集型：线程数 = CPU核心数
  - I/O密集型：线程数 = CPU核心数 * 2-4

## 查看统计信息

```python
# 获取缓存和索引统计信息
stats = retriever.get_cache_stats()
print(f"文件缓存: {stats.get('file_cache', {})}")
print(f"索引统计: {stats.get('index', {})}")
```

## 注意事项

1. **索引缓存文件**：如果指定了`index_cache_file`，索引会保存到该文件，下次启动会自动加载
2. **文件变更检测**：文件缓存通过修改时间和大小判断文件是否变更，如果文件内容变更但大小和时间未变，可能需要手动清理缓存
3. **内存占用**：索引和缓存会占用一定内存，可根据实际情况调整缓存大小
4. **向后兼容**：所有优化都是可选的，默认行为与原有实现兼容

## 性能对比

根据方案C的设计，优化后的性能提升：

- **查询响应**：<1秒（使用索引），<5秒（不使用索引）
- **并发查询**：10-50 QPS（取决于并发配置）
- **数据规模**：支持100-1000个文档

相比原有实现：
- 使用索引时，搜索速度提升约5-10倍
- 使用缓存时，重复搜索相同文件时速度提升约10-100倍
- 并发搜索时，多文件搜索速度提升约5-20倍（取决于文件数量）

