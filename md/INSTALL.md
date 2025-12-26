# 安装说明

## 从 Git 仓库安装（推荐）

### 方式一：从远程 Git 仓库安装

```bash
# 从 GitHub 安装（主分支）
pip install git+https://github.com/yourusername/all2txt.git

# 安装指定分支
pip install git+https://github.com/yourusername/all2txt.git@分支名

# 安装指定标签/版本
pip install git+https://github.com/yourusername/all2txt.git@v0.1.0

# 从其他 Git 托管平台安装
pip install git+https://gitee.com/yourusername/all2txt.git
pip install git+https://gitlab.com/yourusername/all2txt.git
```

### 方式二：从本地 Git 仓库安装

```bash
# 从本地 Git 仓库安装
pip install git+file:///path/to/all2txt

# Windows 路径示例
pip install git+file:///C:/Users/username/Documents/code/all2txt
```

## 本地安装

### 方式一：使用 pip install（推荐）

```bash
# 在项目根目录执行
pip install .

# 或者使用开发模式安装（推荐开发时使用，修改代码后无需重新安装）
pip install -e .
```

### 方式二：使用 setup.py

```bash
# 在项目根目录执行
python setup.py install

# 或者开发模式
python setup.py develop
```

### 方式三：构建分发包后安装

```bash
# 安装构建工具（如果还没有）
pip install build

# 构建分发包
python -m build

# 安装构建的包
pip install dist/all2txt-0.1.0-py3-none-any.whl
```

## 验证安装

安装完成后，可以通过以下方式验证：

```bash
# 检查命令行工具是否可用
all2txt --help

# 在Python中测试导入
python -c "from all2txt import convert_pdf, docx_to_txt_simple; print('安装成功！')"
```

## 卸载

```bash
pip uninstall all2txt
```

## 注意事项

1. **包结构**：包的实际代码在 `src` 目录下，通过 `package_dir` 配置映射为 `all2txt` 包名
2. **Python版本**：需要 Python 3.7 或更高版本
3. **依赖项**：安装时会自动安装所有必需的依赖项

## 开发模式

如果需要在开发时修改代码，建议使用开发模式安装：

```bash
pip install -e .
```

这样修改代码后无需重新安装，可以直接使用最新代码。

