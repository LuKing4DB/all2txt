# Anti-RAG检索模块

基于Anti-RAG范式实现的文档检索模块，包含路由决策、检索、验证和引用功能。

## 功能特点

1. **路由决策（Router）**：智能判断用户查询是否需要检索外部文档知识库
2. **文档检索（Retriever）**：在data目录中检索相关文档片段
3. **结果验证（Verifier）**：验证检索结果的相关性和准确性
4. **引用生成（Citation）**：自动生成带有证据和引用的检索结果

## 架构设计

```
Anti-RAG检索流程:
1. 用户输入自然语言查询
2. Router判断是否需要检索
3. 如果需要，DocumentRetriever在data目录中检索
4. Verifier验证检索结果的相关性
5. 生成带有证据和引用的结果
```

## 数据结构

### 文档结构

data目录中的每个文档文件夹包含：
- `{doc_id}_outline.txt` - 文档目录结构
- `{doc_id}.txt` - 文档全文
- `{doc_id}_split/` - 递归分割的文档片段文件夹

### 检索结果

- **Evidence（证据）**：包含内容、文件路径、章节路径、相关性分数
- **Citation（引用）**：包含文档ID、章节标题、文件路径等信息

## 使用方法

### 命令行使用

```bash
# 在所有文档中搜索
python -m retriever.main "投标保证金要求是什么？"

# 在指定文档中搜索
python -m retriever.main "评标办法" -d 13

# 保存结果到文件
python -m retriever.main "技术标准要求" -o results.txt

# 显示详细日志
python -m retriever.main "投标保证金" -v

# 控制检索阶段（1=仅原文，2=原文+分词，3=全流程）
python -m retriever.main "投标保证金" -s 2

# 指定最大结果数
python -m retriever.main "合同条款" -m 20
```

### Python API使用

```python
from retriever.lib.anti_rag_retriever import AntiRAGRetriever

# 创建检索器
retriever = AntiRAGRetriever()

# 执行检索
result = retriever.retrieve("投标保证金要求是什么？", max_results=10, stage=3)

# 访问结果
print(f"需要检索: {result.needs_retrieval}")
print(f"证据数量: {len(result.evidences)}")
print(f"引用数量: {len(result.citations)}")

# 遍历证据
for evidence in result.evidences:
    if evidence.section:
        print(f"章节: {evidence.section}")
    print(f"文件路径: {evidence.file_path}")
    print(f"内容: {evidence.content[:200]}...")
    print(f"相关性分数: {evidence.relevance_score}")
```

### MVP测试

运行MVP测试脚本：

```bash
python -m retriever.test_mvp
```

## 配置

配置文件路径：`src/retriever/config/config.yaml`

首次使用时，可以复制示例配置文件：
```bash
cp src/retriever/config/config.yaml.example src/retriever/config/config.yaml
```

然后编辑 `config.yaml` 文件，设置你的LLM API信息：

```yaml
openai:
  base_url: http://8.130.178.63:3000/v1  # 或你的API地址
  api_key: your-api-key                   # 你的API密钥
  model: qwen3-32b-awq                    # 模型名称

processing:
  timeout: 120                            # API调用超时时间（秒）
```

## 模块结构

```
src/retriever/
├── __init__.py
├── main.py              # 命令行入口
├── test_mvp.py          # MVP测试脚本
├── README.md            # 本文档
├── config/
│   ├── config.yaml      # 配置文件（需要配置）
│   └── config.yaml.example  # 配置文件示例
└── lib/
    ├── __init__.py
    ├── models.py        # 数据模型
    ├── router.py        # 路由决策器
    ├── document_retriever.py  # 文档检索器
    ├── verifier.py      # 验证器
    └── anti_rag_retriever.py  # 主检索类
```

## 依赖

- openai >= 1.0.0
- PyYAML >= 6.0
- 其他依赖见 requirements.txt

## 工作流程示例

1. **用户查询**: "投标保证金要求是什么？"
2. **路由决策**: Router判断需要检索（查询涉及具体规定）
3. **文档检索**: DocumentRetriever在data目录中搜索关键词"投标保证金"
4. **结果验证**: Verifier验证检索到的证据片段的相关性
5. **生成结果**: 返回带有证据和引用的检索结果

## 注意事项

- 确保data目录存在且包含文档文件夹
- 配置文件需要正确设置LLM API信息
- 文档文件夹需要包含outline和split文件

