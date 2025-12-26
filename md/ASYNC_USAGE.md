# 使用说明

## 概述

`all2txt` 提供两种调用方式：
1. **同步方式**：`convert_document()` - 阻塞直到完成
2. **异步方式**：`aconvert_document()` - 支持 `await`，不阻塞事件循环

两种方式都使用进程隔离执行转换，适合计算密集型任务。结果直接写入硬盘。

## 方式1：同步转换（阻塞）

### 基本使用

```python
import all2txt

# 同步转换（阻塞直到完成）
try:
    all2txt.convert_document(
        "document.pdf",
        output="./output",
        extract_images=True,
        extract_tables=True
    )
    print("转换完成！")
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
except ValueError as e:
    print(f"不支持的文件类型: {e}")
except Exception as e:
    print(f"转换失败: {e}")
```

### 批量处理

```python
import all2txt

files = ["doc1.pdf", "doc2.pdf", "doc3.docx"]
for file in files:
    try:
        all2txt.convert_document(
            file,
            output=f"./output/{file}",
            extract_images=True
        )
        print(f"✓ {file} 转换完成")
    except Exception as e:
        print(f"✗ {file} 转换失败: {e}")
```

## 方式2：异步转换（支持 await）

### 基本使用

```python
import asyncio
import all2txt

async def main():
    # 使用 await 等待转换完成
    result = await all2txt.aconvert_document(
        "document.pdf",
        output="./output",
        extract_images=True
    )
    
    if result['success']:
        print(f"✓ 转换成功: {result['output']}")
    else:
        print(f"✗ 转换失败: {result['error']}")

asyncio.run(main())
```

### 并发处理多个文件（推荐）

```python
import asyncio
import all2txt

async def main():
    # 并发处理多个文件
    tasks = [
        all2txt.aconvert_document("doc1.pdf", extract_images=True),
        all2txt.aconvert_document("doc2.pdf", extract_images=True),
        all2txt.aconvert_document("doc3.docx"),
    ]
    
    # 使用 asyncio.gather 并发执行
    results = await asyncio.gather(*tasks)
    
    # 处理结果
    for result in results:
        if result['success']:
            print(f"✓ {result['file_path']} 转换完成 -> {result['output']}")
        else:
            print(f"✗ {result['file_path']} 转换失败: {result['error']}")

asyncio.run(main())
```

### 在异步 Web 框架中使用

```python
from fastapi import FastAPI
import all2txt

app = FastAPI()

@app.post("/convert")
async def convert_endpoint(file_path: str):
    result = await all2txt.aconvert_document(file_path)
    return result
```

## 返回值说明

### 同步方式 (`convert_document`)

- 成功：无返回值（结果写入硬盘）
- 失败：抛出异常

### 异步方式 (`aconvert_document`)

返回字典，包含：
- `success`: `bool` - 是否成功
- `file_path`: `str` - 输入文件路径
- `output`: `str` - 输出目录路径（成功时）
- `error`: `Optional[Exception]` - 异常对象（失败时）

## 参数说明

两种方式支持相同的参数：

- `file_path`: 输入文件路径（PDF或DOCX）
- `output`: 输出目录路径（可选，默认在输入文件同目录下创建同名文件夹）
- `debug`: 是否启用调试模式
- `extract_images`: 是否提取图片（仅PDF）
- `extract_tables`: 是否提取表格（仅PDF）
- `table_images`: 是否保存表格截图（仅PDF）
- `export_metadata`: 是否导出元数据（仅PDF）
- `num_workers`: 并行处理的工作进程数（仅PDF，0=自动）

## 优势对比

| 特性 | 同步方式 | 异步方式 |
|------|---------|---------|
| 阻塞 | 是（阻塞当前线程） | 否（不阻塞事件循环） |
| 返回值 | 无（抛出异常） | 结果字典 |
| 并发 | 串行执行 | 支持并发（asyncio.gather） |
| 适用场景 | 简单脚本、命令行工具 | 异步框架、Web服务 |
| 异常处理 | try/except | 检查 result['success'] |

## 注意事项

1. **进程隔离**：两种方式都使用进程隔离，适合计算密集型任务
2. **结果在硬盘**：转换结果直接写入硬盘，不通过返回值传递
3. **Windows 兼容**：Windows 平台使用 `spawn` 方式启动进程，已自动处理
4. **资源开销**：每个转换任务会创建独立进程，有一定内存开销
5. **异步环境**：`aconvert_document` 必须在异步环境中调用（async 函数内）

## 示例：混合使用

```python
import asyncio
import all2txt

# 同步方式：简单场景
all2txt.convert_document("simple.pdf")

# 异步方式：需要并发时
async def process_batch():
    tasks = [
        all2txt.aconvert_document(f"doc{i}.pdf")
        for i in range(10)
    ]
    results = await asyncio.gather(*tasks)
    return results

results = asyncio.run(process_batch())
```
