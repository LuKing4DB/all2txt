# all2txt

文档转换工具：支持PDF和DOCX文件转换为TXT格式的Python包。

## 功能特性

- ✅ **PDF转TXT**：支持将PDF文件转换为纯文本格式
- ✅ **DOCX转TXT**：支持将DOCX文件转换为纯文本格式
- ✅ **图片提取**：支持从PDF中提取图片（可选）
- ✅ **表格提取**：支持从PDF中提取表格（可选）
- ✅ **元数据导出**：支持导出PDF元数据（可选）
- ✅ **并行处理**：支持多进程并行处理PDF文件

## 安装

### 从 Git 仓库安装（推荐）

```bash
# 从 GitHub 安装（主分支）
pip install git+https://github.com/yourusername/all2txt.git

# 安装指定分支
pip install git+https://github.com/yourusername/all2txt.git@分支名

# 安装指定标签/版本
pip install git+https://github.com/yourusername/all2txt.git@v0.1.0

# 从本地 Git 仓库安装
pip install git+file:///path/to/all2txt

# 从其他 Git 托管平台安装（如 GitLab、Gitee）
pip install git+https://gitee.com/yourusername/all2txt.git
```

### 从本地安装

```bash
# 克隆或下载项目后，在项目根目录执行
pip install .

# 或者使用开发模式安装（推荐开发时使用）
pip install -e .
```

## 使用方法

### 命令行使用

安装后，可以通过命令行工具 `all2txt` 使用：

```bash
# 转换PDF文档
all2txt document.pdf

# 转换DOCX文档
all2txt document.docx

# 指定输出目录
all2txt document.pdf --output ./output

# PDF特有选项：提取图片和表格
all2txt document.pdf --images --tables

# 启用调试模式
all2txt document.pdf --debug

# 查看所有选项
all2txt --help
```

### Python API使用

```python
from all2txt import convert_pdf, docx_to_txt_simple
from pathlib import Path

# 转换PDF
convert_pdf(
    file_path="document.pdf",
    output_dir=Path("./output"),
    extract_images=True,
    extract_tables=True,
    debug=False
)

# 转换DOCX
docx_to_txt_simple(
    docx_path="document.docx",
    output_path="./output/document.txt",
    debug=False
)
```

### 统一转换接口

```python
from all2txt.main import convert_document

# 自动根据文件类型选择处理模块
convert_document(
    file_path="document.pdf",  # 或 document.docx
    output="./output",
    extract_images=True,
    extract_tables=True,
    debug=False
)
```

## 输出文件说明

### PDF转换输出

- `text.txt` - 提取的文本内容
- `{filename}_index.txt` - 每行对应的索引信息
- `{filename}_page.txt` - 每行对应的页码信息
- `{filename}_coordinate.txt` - 每行对应的坐标信息
- `images/` - 提取的图片目录（如果启用）
- `tables/` - 提取的表格目录（如果启用）
- `metadata_pdf.txt` - 元数据文件（如果启用）

### DOCX转换输出

- `{filename}.txt` - 提取的文本内容
- `{filename}_index.txt` - 每行对应的索引信息
- `{filename}_page.txt` - 页码信息（如果存在）
- `{filename}_bookmarked.docx` - 带书签的DOCX副本

## 依赖项

- python-docx >= 1.1.0
- pdfplumber == 0.11.7
- pypdf >= 3.9.0
- lxml >= 4.9.0
- Pillow >= 9.0.0

## 系统要求

- Python >= 3.7

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试（如果有）
pytest
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

