# 文档处理流水线（使用AI生成正则表达式）

这是一个自动化处理文档的流水线工具，支持 DOCX 和 PDF 格式。能够将文档转换为TXT，使用AI生成正则表达式，然后根据正则表达式分割文档。

## 功能流程

1. **文档转TXT**：使用 `docx2txt` 或 `pdf2txt` 将文档转换为TXT格式
2. **提取样本**：从TXT文件中提取前N个字符作为样本（默认500字符）
3. **AI生成正则表达式**：调用OpenAI API（支持自定义模型和base URL），使用提示词模板生成匹配第一层级标题的正则表达式
4. **分割文档**：使用生成的正则表达式分割TXT文件

## 安装依赖

确保已安装项目依赖：

```bash
pip install -r requirements.txt
```

主要依赖包括：
- `python-docx` - 处理DOCX文件
- `openai` - 调用OpenAI API
- `PyYAML` - 读取配置文件

## 快速开始

### 1. 创建配置文件（推荐）

复制示例配置文件并修改：

```bash
cp src/pipeline/config/config.yaml.example src/pipeline/config/config.yaml
```

编辑 `src/pipeline/config/config.yaml`，填入你的API配置：

```yaml
openai:
  base_url: https://api.openai.com/v1
  api_key: sk-your-api-key-here
  model: gpt-4

processing:
  prompt_file: prompt/prompt_select
  sample_chars: 500
```

### 2. 测试连通性（可选但推荐）

在运行主脚本之前，建议先测试配置是否正确：

```bash
# 测试默认配置文件
python src/pipeline/test/test_connection.py

# 测试指定配置文件
python src/pipeline/test/test_connection.py --config config/config.yaml

# 显示详细信息
python src/pipeline/test/test_connection.py -v
```

如果测试成功，会显示"连通性测试通过！"，然后可以继续使用主脚本。

### 3. 运行脚本

```bash
# 使用配置文件（最简单）
python src/pipeline/main.py data/docx/1.docx
```

## 使用方法

### 方法1：使用配置文件（推荐）

创建 `config.yaml` 文件后，直接运行：

```bash
python src/pipeline/main.py <docx文件路径>
```

配置文件会自动从以下位置查找：
1. 当前工作目录下的 `config.yaml`
2. 脚本目录下的 `config/config.yaml`
3. 脚本目录下的 `config.yaml`（向后兼容）

### 方法2：使用命令行参数

如果不想使用配置文件，可以通过命令行参数提供所有必需参数：

```bash
python src/pipeline/main.py <docx文件路径> \
  --base-url https://api.openai.com/v1 \
  --api-key sk-xxx \
  --model gpt-4
```

### 方法3：混合使用（命令行参数覆盖配置）

配置文件中的参数可以通过命令行参数覆盖：

```bash
# 使用配置文件，但临时更换模型
python src/pipeline/main.py data/docx/1.docx \
  --model gpt-3.5-turbo
```

### 方法4：使用自定义配置文件

```bash
python src/pipeline/main.py data/docx/1.docx \
  --config custom_config.yaml
```

## 命令行参数

### 必需参数

- `file_path` - 输入的文档文件路径（位置参数，支持 .docx 或 .pdf）

### 可选参数

- `--config` - 配置文件路径（默认：查找当前目录或脚本目录下的config/config.yaml）
- `--base-url` - OpenAI API的base URL（覆盖配置文件）
  - 官方API: `https://api.openai.com/v1`
  - 本地模型: `http://localhost:8000/v1`
- `--api-key` - API密钥（覆盖配置文件）
- `--model` - 模型名称（覆盖配置文件）
  - 例如: `gpt-4`, `gpt-3.5-turbo`, 或自定义模型名称
- `--prompt-file` - 提示词文件路径（覆盖配置文件）
  - 默认: 脚本目录下的 `prompt/prompt_select`
- `--sample-chars` - 样本字符数（覆盖配置文件）
  - 默认: 500
- `-o, --output` - 输出目录（可选）
  - 默认: 在输入文件同目录下创建同名文件夹

## 配置文件说明

配置文件使用YAML格式，示例文件：`config/config.yaml.example`

### 配置结构

```yaml
# OpenAI API 配置
openai:
  base_url: https://api.openai.com/v1  # API的base URL
  api_key: sk-your-api-key-here        # API密钥
  model: gpt-4                         # 模型名称

# 处理配置
processing:
  prompt_file: prompt/prompt_select    # 提示词文件路径
  sample_chars: 500                    # 样本字符数
  # output_dir: null                   # 输出目录（可选）
```

### 配置项说明

#### openai 部分

- `base_url`: OpenAI API的基础URL
  - 官方API: `https://api.openai.com/v1`
  - 本地模型（如Ollama）: `http://localhost:8000/v1`
- `api_key`: API密钥
  - 对于本地模型，可以设置为任意值
- `model`: 要使用的模型名称
  - OpenAI模型: `gpt-4`, `gpt-3.5-turbo` 等
  - 自定义模型: 根据你的API服务提供商设置

#### processing 部分

- `prompt_file`: 提示词文件路径
  - 可以是相对路径（相对于脚本目录）或绝对路径
  - 如果未指定，默认使用脚本目录下的 `prompt/prompt_select`
- `sample_chars`: 从TXT文件中提取的样本字符数
  - 默认: 500
  - 建议值: 300-1000，根据文档结构调整
- `output_dir`: 输出目录（可选）
  - 如果未指定，默认在输入文件同目录下创建同名文件夹

## 输出说明

脚本会在以下位置生成文件：

1. **TXT文件**: `<输入文件目录>/<文件名>/<文件名>.txt`
   - 包含转换后的文本内容
   - 同时生成索引文件 `*_index.txt` 和页码文件 `*_page.txt`

2. **分割结果**: `<输入文件目录>/<文件名>/<文件名>_split/`
   - 包含按正则表达式分割后的多个文件
   - 文件命名: `0.txt`, `1.txt`, `2.txt` ...

### 示例输出结构

```
data/docx/
└── 1.docx
data/
└── 1/
    ├── 1.txt              # 转换后的TXT文件
    ├── 1_index.txt        # 索引文件
    ├── 1_page.txt         # 页码文件
    └── 1_split/           # 分割结果目录
        ├── 0.txt
        ├── 1.txt
        ├── 2.txt
        └── ...
```

## 提示词文件

脚本使用 `prompt/prompt_select` 作为提示词模板，该文件包含：

- 样本占位符：`<开头样本>` 和 `</开头样本>`
- 任务说明：分析文档中的第一层级标题格式
- 正则表达式选项：8个预定义的正则表达式选项

脚本会自动将提取的文本样本插入到提示词中，然后发送给AI生成正则表达式。

## 工作原理

1. **文档转换**：将DOCX或PDF文件转换为TXT格式
   - DOCX：每段一行，保留图片和表格标记
   - PDF：提取文本内容，每行一个文本片段
2. **样本提取**：提取TXT文件的前N个字符（保留换行符），用于分析文档结构
3. **AI分析**：将样本插入提示词模板，调用OpenAI API分析文档中的第一层级标题格式
4. **正则生成**：AI从8个预定义选项中选择最合适的正则表达式，或直接返回正则表达式
5. **文档分割**：使用生成的正则表达式在匹配位置分割TXT文件

## 使用示例

### 示例1：处理DOCX文件

```bash
# 使用配置文件处理DOCX
python src/pipeline/main.py data/docx/1.docx
```

### 示例2：处理PDF文件

```bash
# 使用配置文件处理PDF
python src/pipeline/main.py data/pdf/1.pdf
```

### 示例3：使用OpenAI官方API

```bash
# 创建配置文件 config/config.yaml
cat > config/config.yaml << EOF
openai:
  base_url: https://api.openai.com/v1
  api_key: sk-your-key-here
  model: gpt-4
processing:
  sample_chars: 500
EOF

# 运行脚本
python src/pipeline/main.py data/docx/1.docx
```

### 示例4：使用本地模型（Ollama）

```bash
# 创建配置文件 config/config.yaml
cat > config/config.yaml << EOF
openai:
  base_url: http://localhost:11434/v1
  api_key: not-needed
  model: llama2
processing:
  sample_chars: 500
EOF

# 运行脚本
python src/pipeline/main.py data/docx/1.docx
```

### 示例5：临时更换模型

```bash
# 使用配置文件，但临时使用不同的模型
python src/pipeline/main.py data/docx/1.docx \
  --model gpt-3.5-turbo
```

### 示例6：指定输出目录

```bash
python src/pipeline/main.py data/docx/1.docx \
  -o output/result
```

## 测试连通性

在运行主脚本处理文档之前，建议先使用测试脚本验证配置是否正确：

```bash
# 基本测试
python src/pipeline/test/test_connection.py

# 显示详细信息（包括token使用情况等）
python src/pipeline/test/test_connection.py -v

# 测试指定的配置文件
python src/pipeline/test/test_connection.py --config config/custom_config.yaml
```

测试脚本会：
1. 加载配置文件
2. 验证必需参数是否存在
3. 创建OpenAI客户端
4. 发送一个简单的测试请求
5. 显示连接结果和响应

如果测试失败，脚本会提供具体的错误信息和解决建议。

## 故障排除

### 1. 配置文件未找到

**错误信息**：
```
警告: 未找到配置文件。请创建 config.yaml 文件，或使用 --config 参数指定配置文件路径。
```

**解决方法**：
- 创建 `config/config.yaml` 文件（复制 `config/config.yaml.example`）
- 或使用 `--config` 参数指定配置文件路径
- 或通过命令行参数提供所有必需参数

### 2. 缺少必需参数

**错误信息**：
```
错误: 缺少必需参数。请提供 --base-url, --api-key, --model 或在配置文件中设置。
```

**解决方法**：
- 在配置文件中设置这些参数
- 或通过命令行参数提供

### 3. API调用失败

**错误信息**：
```
错误: 调用OpenAI API失败: ...
```

**解决方法**：
- 检查 `base_url` 是否正确
- 检查 `api_key` 是否有效
- 检查网络连接
- 检查模型名称是否正确

### 4. 未找到匹配的正则表达式

**错误信息**：
```
警告: 未找到匹配的行（模式: ...）
```

**解决方法**：
- 增加 `sample_chars` 的值，提取更多样本
- 检查文档是否包含第一层级标题
- 手动指定正则表达式（修改脚本或提示词）

## 项目结构

```
src/pipeline/
├── README.md                    # 本文档
├── main.py                      # 主脚本
├── config/                      # 配置文件目录
│   ├── config.yaml              # 配置文件
│   └── config.yaml.example      # 配置文件示例
├── prompt/                      # 提示词文件目录
│   └── prompt_select            # 提示词模板文件
├── test/                        # 测试文件目录
│   └── test_connection.py      # 连通性测试脚本
└── lib/                         # 支持库
    ├── __init__.py
    ├── config_loader.py         # 配置加载器
    ├── prompt_loader.py         # 提示词加载器
    ├── sample_extractor.py      # 样本提取器
    └── openai_client.py         # OpenAI客户端
```

## 注意事项

1. **API密钥安全**：不要将包含真实API密钥的 `config/config.yaml` 提交到版本控制系统
2. **配置文件位置**：脚本会优先查找当前工作目录下的配置文件，然后是 `config/config.yaml`
3. **样本大小**：样本字符数建议在300-1000之间，太小可能无法识别标题格式，太大可能增加API调用成本
4. **正则表达式选项**：脚本预定义了8个正则表达式选项，如果文档格式特殊，可能需要修改 `prompt/prompt_select` 文件

## 许可证

请参考项目根目录的许可证文件。

## 相关文档

- [项目主README](../../README.md)
- [DOCX转TXT文档](../docx2txt/README.md)
- [PDF转TXT文档](../pdf2txt/README.md)
- [分割脚本文档](../split/README.md)

