# PDF转TXT工具

将PDF文件转换为TXT格式的工具，支持文本提取、图片提取、表格提取等功能。

## 功能特性

- **文本提取**：从PDF中提取文本内容，转换为TXT格式
- **图片提取**：可选提取PDF中的图片（PNG格式）
- **表格提取**：可选提取PDF中的表格（CSV格式）
- **表格截图**：可选保存表格截图（PNG格式）
- **元数据导出**：可选导出元数据（NDJSON格式，包含bbox和字体信息）
- **自动修复**：自动检测并修复损坏的PDF文件
- **并行处理**：支持多进程并行处理，提高处理速度
- **索引文件**：生成索引文件，记录每行对应的页码
- **页码文件**：提取并记录页码信息

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `pdfplumber` - PDF文本提取
- `PyMuPDF` (fitz) - PDF处理和修复
- `Pillow` - 图片处理

## 使用方法

### 基本用法

```bash
python src/pdf2txt/main.py <pdf文件路径>
```

### 指定输出目录

```bash
python src/pdf2txt/main.py <pdf文件路径> --out <输出目录>
```

### 提取图片

```bash
python src/pdf2txt/main.py <pdf文件路径> --images
```

### 提取表格

```bash
python src/pdf2txt/main.py <pdf文件路径> --tables
```

### 保存表格截图

```bash
python src/pdf2txt/main.py <pdf文件路径> --tables --table-images
```

### 导出元数据

```bash
python src/pdf2txt/main.py <pdf文件路径> --metadata
```

### 完整示例

```bash
# 基本转换
python src/pdf2txt/main.py data/pdf/1.pdf

# 提取文本、图片和表格
python src/pdf2txt/main.py data/pdf/1.pdf --images --tables

# 指定输出目录并启用调试
python src/pdf2txt/main.py data/pdf/1.pdf --out output/result --debug

# 使用多进程处理（自动检测CPU核心数）
python src/pdf2txt/main.py data/pdf/1.pdf --workers 4
```

## 输出文件

脚本会在输出目录生成以下文件：

1. **`<文件名>.txt`** - 文本内容文件
   - 每行一个文本片段
   - 使用UTF-8编码

2. **`<文件名>_index.txt`** - 索引文件
   - 记录每行对应的页码

3. **`<文件名>_page.txt`** - 页码文件（如果PDF包含页码）
   - 格式：`索引序号|页码`

4. **`images/`** - 图片目录（如果启用 `--images`）
   - 包含提取的图片文件（PNG格式）

5. **`tables/`** - 表格目录（如果启用 `--tables`）
   - 包含提取的表格文件（CSV格式）
   - 如果启用 `--table-images`，还包含表格截图（PNG格式）

6. **`metadata_pdf.txt`** - 元数据文件（如果启用 `--metadata`）
   - NDJSON格式，包含每行的bbox和字体信息

### 输出示例

```
data/pdf/
└── 1.pdf
data/
└── 1/
    ├── 1.txt              # 文本内容
    ├── 1_index.txt        # 索引文件
    ├── 1_page.txt         # 页码文件（如果有）
    ├── images/            # 图片目录（如果启用）
    │   ├── image_0000.png
    │   └── ...
    ├── tables/            # 表格目录（如果启用）
    │   ├── table_0000.csv
    │   └── ...
    └── metadata_pdf.txt   # 元数据文件（如果启用）
```

## 功能说明

### 自动修复

脚本会自动检测PDF文件是否损坏，并在需要时尝试修复：
- 检测PDF文件的有效性
- 如果检测到问题，自动尝试修复
- 修复后的文件会保存为 `<原文件名>_fixed.pdf`

### 并行处理

脚本支持多进程并行处理：
- `--workers 0` - 自动检测CPU核心数（默认）
- `--workers 1` - 串行处理
- `--workers N` - 使用N个进程并行处理

### 文本规范化

提取的文本会自动进行规范化处理：
- NFKC规范化（全角/兼容字符归一）
- 去除不换行空格与控制字符
- 保留英文单词之间的空格
- 去除其他空格

## 命令行参数

- `file` - PDF文件路径（必需）
- `--out` - 输出目录（可选，默认输出到输入文件同级目录）
- `--images` - 提取图片（默认：不提取）
- `--tables` - 提取表格（默认：不提取）
- `--table-images` - 保存表格截图（PNG，默认：否）
- `--metadata` - 导出元数据到NDJSON（默认：不导出）
- `--workers` - 并行处理的工作进程数（0=自动，1=串行，默认：0）
- `--debug` - 打印调试信息

## 注意事项

- 处理大型PDF文件时，建议使用并行处理以提高速度
- 图片和表格提取会增加处理时间和输出文件大小
- 元数据导出会生成较大的文件，仅用于需要详细位置信息的场景
- 修复后的PDF文件会保留在原文件目录下，供后续使用

## 项目结构

```
src/pdf2txt/
├── main.py              # 主入口文件（包含适配器基础类）
├── pdf_precheck_tool.py # PDF预检工具
└── lib/                 # 库文件
    ├── pdf_parallel.py      # 并行处理
    ├── pdf_writer.py         # 文件写入
    ├── pdf_precheck.py       # PDF预检和修复
    ├── pdf_text_extractor.py # 文本提取
    ├── pdf_element_extractor.py # 元素提取
    ├── pdf_exporter.py        # 导出功能
    ├── pdf_adapter.py         # PDF适配器
    ├── pdf_utils.py           # 工具函数
    └── pdf_fix_tool.py        # PDF修复工具
```

