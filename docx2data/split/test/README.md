# Split 模块单元测试

本目录包含 split 模块的单元测试脚本。

## 测试结构

- `test_split.py` - 主要的测试文件，包含所有模块的测试用例
- `run_tests.py` - 便捷的测试运行脚本
- `__init__.py` - 使测试目录成为一个 Python 包

## 测试覆盖

测试覆盖了以下模块：

1. **number_extractor** - 数字提取功能
   - 阿拉伯数字提取
   - 中文数字提取
   - 括号格式数字提取
   - "第X章"格式提取

2. **toc_detector** - 目录检测功能
   - 目录项识别
   - 目录区域检测
   - 基于关键字的目录区域检测

3. **ordered_list_detector** - 有序列表检测功能
   - 有序列表项识别
   - 有序列表格式类型识别
   - 有序列表区域检测

4. **regex_splitter** - 正则表达式分割功能
   - 基本分割功能
   - 序号校验
   - 目录区域跳过
   - 有序列表跳过
   - 错误处理

## 运行测试

### 方法 1: 使用便捷脚本

```bash
python src/split/test/run_tests.py
```

### 方法 2: 使用 unittest 模块

```bash
python -m unittest discover -s src/split/test -p test_*.py -v
```

### 方法 3: 运行单个测试文件

```bash
python -m unittest src.split.test.test_split -v
```

### 方法 4: 运行特定测试类

```bash
python -m unittest src.split.test.test_split.TestNumberExtractor -v
```

### 方法 5: 运行特定测试方法

```bash
python -m unittest src.split.test.test_split.TestNumberExtractor.test_extract_arabic_number -v
```

## 测试示例

测试会创建临时文件和目录，测试完成后自动清理，不会影响项目文件。

## 注意事项

- 测试使用 Python 标准库的 `unittest` 模块，无需额外依赖
- 所有测试都是独立的，可以单独运行
- 测试会创建临时文件系统，但会在测试后自动清理

