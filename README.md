# all2txt

文档转换工具：支持PDF和DOCX文件转换为TXT格式的Python包。

## 功能特性

- ✅ **PDF转TXT**：支持将PDF文件转换为纯文本格式
- ✅ **DOCX转TXT**：支持将DOCX文件转换为纯文本格式
- ✅ **图片提取**：支持从PDF中提取图片（可选）
- ✅ **表格提取**：支持从PDF中提取表格（可选）
- ✅ **元数据导出**：支持导出PDF元数据（可选）
- ✅ **并行处理**：支持多进程并行处理PDF文件
- ✅ **异步支持**：提供异步接口，支持并发处理多个文件，适合Web服务和异步框架

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

#### 同步方式（阻塞）

```python
import all2txt

# 自动根据文件类型选择处理模块
try:
    all2txt.convert_document(
        file_path="document.pdf",  # 或 document.docx
        output="./output",
        extract_images=True,
        extract_tables=True,
        debug=False
    )
    print("转换完成！")
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
except ValueError as e:
    print(f"不支持的文件类型: {e}")
except Exception as e:
    print(f"转换失败: {e}")
```

#### 异步方式（推荐，支持并发）

```python
import asyncio
import all2txt

async def main():
    # 单个文件转换
    result = await all2txt.aconvert_document(
        "document.pdf",
        output="./output",
        extract_images=True,
        extract_tables=True
    )
    
    if result['success']:
        print(f"✓ 转换成功: {result['output']}")
    else:
        print(f"✗ 转换失败: {result['error']}")
    
    # 并发处理多个文件（推荐）
    tasks = [
        all2txt.aconvert_document("doc1.pdf", extract_images=True),
        all2txt.aconvert_document("doc2.pdf", extract_images=True),
        all2txt.aconvert_document("doc3.docx"),
    ]
    
    results = await asyncio.gather(*tasks)
    for result in results:
        if result['success']:
            print(f"✓ {result['file_path']} 转换完成 -> {result['output']}")
        else:
            print(f"✗ {result['file_path']} 转换失败: {result['error']}")

asyncio.run(main())
```

#### 在异步 Web 框架中使用

```python
from fastapi import FastAPI
import all2txt

app = FastAPI()

@app.post("/convert")
async def convert_endpoint(file_path: str):
    result = await all2txt.aconvert_document(file_path)
    return result
```

> 📖 **详细说明**：更多异步使用方法请参考 [异步使用文档](md/ASYNC_USAGE.md)

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

