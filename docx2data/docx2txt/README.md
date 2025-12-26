# DOCX转TXT工具

将DOCX文件转换为TXT格式的工具，支持段落、图片、表格的提取和标记。

## 功能特性

- **段落提取**：将DOCX文件中的所有段落转换为TXT格式，每段一行
- **图片标记**：自动检测并标记图片位置（`[图片]`）
- **表格标记**：自动检测并标记表格位置（`[表格]`）
- **印章过滤**：自动过滤印章图片（方形或红色特征）
- **自动编号处理**：自动检测并处理DOCX中的自动编号
- **索引文件**：生成索引文件，记录每行在原始文档中的位置
- **页码文件**：提取并记录页码信息
- **字数统计**：提供详细的字数统计（中文、英文、数字等）

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `python-docx` - 处理DOCX文件
- `Pillow` - 图片处理（可选，用于印章检测）

## 使用方法

### 基本用法

```bash
python src/docx2txt/main.py <docx文件路径>
```

### 指定输出目录

```bash
python src/docx2txt/main.py <docx文件路径> -o <输出目录>
```

### 启用调试模式

```bash
python src/docx2txt/main.py <docx文件路径> --debug
```

### 示例

```bash
# 转换DOCX文件，自动生成同名文件夹
python src/docx2txt/main.py data/docx/1.docx

# 指定输出目录
python src/docx2txt/main.py data/docx/1.docx -o output/result

# 启用调试模式查看详细信息
python src/docx2txt/main.py data/docx/1.docx --debug
```

## 输出文件

脚本会在输出目录生成以下文件：

1. **`<文件名>.txt`** - 文本内容文件
   - 每行一个段落
   - 图片标记为 `[图片]`
   - 表格标记为 `[表格]`

2. **`<文件名>_index.txt`** - 索引文件
   - 记录每行在原始文档中的位置索引

3. **`<文件名>_page.txt`** - 页码文件（如果文档包含页码）
   - 格式：`索引序号|页码`

### 输出示例

```
data/docx/
└── 1.docx
data/
└── 1/
    ├── 1.txt              # 文本内容
    ├── 1_index.txt        # 索引文件
    └── 1_page.txt         # 页码文件（如果有）
```

## 功能说明

### 自动编号处理

脚本会自动检测DOCX文件中的自动编号，并在处理前自动删除编号，确保提取的文本不包含自动编号格式。

### 印章过滤

脚本会自动检测并过滤印章图片：
- **检测方法**：检查图片是否具有印章特征
  - 方形特征：长宽比接近1:1（容差0.3）
  - 红色特征：红色像素占比 >= 30%
- **过滤规则**：满足任一特征即判定为印章，不输出 `[图片]` 标记

### 字数统计

脚本会统计以下信息：
- 总字符数（去除空格）
- 中文字符数
- 英文字符数
- 数字字符数
- 其他字符数

## 命令行参数

- `docx_path` - 输入的DOCX文件路径（必需）
- `-o, --output` - 输出目录路径（可选，默认在输入文件同目录下创建同名文件夹）
- `--debug` - 启用debug模式，输出图片处理的详细信息

## 注意事项

- 脚本需要 `python-docx` 库
- 如果 `Pillow` 不可用，印章检测功能会被禁用，所有图片都会输出 `[图片]` 标记
- 输出文件使用UTF-8编码

## 项目结构

```
src/docx2txt/
├── main.py              # 主入口文件
├── extract_toc.py       # 目录提取工具
└── lib/                 # 库文件
    ├── image_detector.py      # 图片检测
    ├── paragraph_processor.py # 段落处理
    ├── table_processor.py     # 表格处理
    └── del_docx_auto_num.py   # 自动编号处理
```

