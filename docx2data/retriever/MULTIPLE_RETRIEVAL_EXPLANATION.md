# 多次检索流程说明

## 问题现象

日志中出现多次"Anti-RAG检索流程开始"，例如：
```
14:52:13 - Anti-RAG检索流程开始 | 查询: 投标人须知 | 阶段: 1
14:52:15 - 检索完成 | 证据: 0 个
14:52:15 - Anti-RAG检索流程开始 | 查询: 投标人须知 | 阶段: 1
14:52:16 - 文档检索 | 关键词: 投标人须知 | 文档: 20251219_101332...
```

## 问题原因

### 代码位置

在 `web/app.py` 的 `search_documents` 函数中（第505-520行）：

```python
# 如果指定了doc_ids，需要分别检索每个文档
if doc_ids and len(doc_ids) > 0:
    # 多文档检索：分别检索每个文档，然后合并结果
    all_evidences = []
    all_citations = []
    all_verification_scores = {}
    all_keywords = []
    
    for doc_id in doc_ids:  # ← 循环遍历每个文档
        try:
            result = retriever.retrieve(  # ← 每个文档都调用一次完整的检索流程
                query=request.query,
                max_results=request.max_results,
                doc_id=doc_id,
                stage=stage_value
            )
            # 合并结果...
```

### 原因分析

**设计逻辑**：
- 当查询**多个文档**时（通过 `doc_ids` 或 `group_id` 指定）
- 系统会**为每个文档单独调用一次完整的检索流程**
- 每次调用都会：
  1. 输出"Anti-RAG检索流程开始"日志
  2. 执行意图识别
  3. 执行原文检索
  4. 执行验证
  5. 输出"检索完成"日志

**为什么这样设计**：
- 每个文档独立检索，可以单独控制每个文档的检索结果
- 便于合并多个文档的检索结果
- 便于追踪每个文档的检索过程

## 影响

### 优点
- ✅ 每个文档的检索过程清晰可见
- ✅ 便于调试和追踪
- ✅ 可以单独控制每个文档的检索参数

### 缺点
- ⚠️ 日志重复，看起来混乱
- ⚠️ 多次意图识别（相同查询重复识别）
- ⚠️ 性能开销：多次初始化检索流程

## 优化方案

### 方案1：批量检索（推荐）⭐⭐⭐

**思路**：一次性检索所有文档，而不是循环检索

**实现**：
```python
# 修改 DocumentRetriever.retrieve 支持多文档
if doc_ids and len(doc_ids) > 0:
    # 一次性检索所有文档
    result = retriever.retrieve(
        query=request.query,
        max_results=request.max_results,
        doc_ids=doc_ids,  # 支持列表
        stage=stage_value
    )
```

**优点**：
- 只执行一次检索流程
- 减少日志重复
- 性能更好

**缺点**：
- 需要修改 `DocumentRetriever` 接口
- 需要重构代码

### 方案2：调整日志级别 ⭐⭐

**思路**：在多文档检索时，降低日志级别或合并日志

**实现**：
```python
for idx, doc_id in enumerate(doc_ids):
    if idx == 0:
        logger.info(f"开始检索 {len(doc_ids)} 个文档...")
    else:
        logger.debug(f"检索文档 {idx+1}/{len(doc_ids)}: {doc_id}")
    
    result = retriever.retrieve(...)
```

**优点**：
- 简单易实现
- 不影响现有逻辑
- 日志更清晰

**缺点**：
- 仍然执行多次检索流程
- 性能没有提升

### 方案3：添加批量检索模式 ⭐⭐⭐

**思路**：添加一个批量检索方法，内部循环但不输出重复日志

**实现**：
```python
def retrieve_batch(self, query: str, doc_ids: List[str], ...):
    """批量检索多个文档"""
    logger.info(f"批量检索开始 | 查询: {query} | 文档数: {len(doc_ids)}")
    
    all_evidences = []
    for idx, doc_id in enumerate(doc_ids):
        logger.debug(f"检索文档 {idx+1}/{len(doc_ids)}: {doc_id}")
        result = self._retrieve_single(query, doc_id, ...)  # 内部方法，不输出开始日志
        all_evidences.extend(result.evidences)
    
    logger.info(f"批量检索完成 | 共找到 {len(all_evidences)} 个证据")
    return all_evidences
```

**优点**：
- 保持现有接口不变
- 日志更清晰
- 性能更好

**缺点**：
- 需要新增方法
- 需要重构部分代码

## 当前行为说明

### 正常行为

**单文档查询**：
```
查询: 投标人须知, doc_id: doc1
→ 1次检索流程
→ 1次"Anti-RAG检索流程开始"
```

**多文档查询**：
```
查询: 投标人须知, doc_ids: [doc1, doc2, doc3]
→ 3次检索流程
→ 3次"Anti-RAG检索流程开始"
```

### 日志示例

**多文档查询日志**：
```
14:52:13 - Anti-RAG检索流程开始 | 查询: 投标人须知 | 阶段: 1
14:52:13 - 意图识别: ...
14:52:13 - 阶段1: 原文检索
14:52:13 - 文档检索 | 关键词: 投标人须知 | 文档: doc1
14:52:15 - 检索完成 | 证据: 0 个

14:52:15 - Anti-RAG检索流程开始 | 查询: 投标人须知 | 阶段: 1  ← 第二次
14:52:15 - 意图识别: ...
14:52:15 - 阶段1: 原文检索
14:52:15 - 文档检索 | 关键词: 投标人须知 | 文档: doc2
14:52:16 - 检索完成 | 证据: 2 个
```

## 建议

### 短期方案（快速修复）

**调整日志级别**：
- 在多文档检索时，只在第一次输出"Anti-RAG检索流程开始"
- 后续文档使用DEBUG级别或合并日志

### 长期方案（性能优化）

**实现批量检索**：
- 修改 `DocumentRetriever.retrieve` 支持多文档
- 一次性检索所有文档，减少重复流程

## 总结

**问题**：多文档查询时，每个文档都会执行一次完整的检索流程，导致日志重复

**原因**：设计上采用循环检索每个文档的方式

**影响**：
- 日志重复，看起来混乱
- 性能开销：多次意图识别和初始化

**解决方案**：
1. **短期**：调整日志级别，减少重复日志
2. **长期**：实现批量检索，提升性能

**当前状态**：这是**正常的设计行为**，不是bug，但可以优化

