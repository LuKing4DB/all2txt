# 从 Git 仓库安装指南

本指南说明如何通过 Git 仓库使用 `pip install` 安装 `all2txt` 包。

## 前置要求

确保已安装 Git 和 pip：

```bash
# 检查 Git
git --version

# 检查 pip
pip --version
```

## 安装方式

### 1. 从 GitHub 安装（主分支）

```bash
pip install git+https://github.com/yourusername/all2txt.git
```

### 2. 安装指定分支

```bash
# 安装 develop 分支
pip install git+https://github.com/yourusername/all2txt.git@develop

# 安装 feature 分支
pip install git+https://github.com/yourusername/all2txt.git@feature/new-feature
```

### 3. 安装指定标签/版本

```bash
# 安装 v0.1.0 版本
pip install git+https://github.com/yourusername/all2txt.git@v0.1.0

# 安装特定提交
pip install git+https://github.com/yourusername/all2txt.git@abc123def
```

### 4. 从本地 Git 仓库安装

```bash
# Linux/Mac
pip install git+file:///path/to/all2txt

# Windows
pip install git+file:///C:/Users/username/Documents/code/all2txt

# 或者使用相对路径（在项目父目录）
cd ..
pip install git+file:///$(pwd)/all2txt
```

### 5. 从其他 Git 托管平台安装

```bash
# GitLab
pip install git+https://gitlab.com/yourusername/all2txt.git

# Gitee
pip install git+https://gitee.com/yourusername/all2txt.git

# Bitbucket
pip install git+https://bitbucket.org/yourusername/all2txt.git

# 私有仓库（需要认证）
pip install git+https://username:token@github.com/yourusername/all2txt.git
```

### 6. 使用 SSH 协议（需要配置 SSH 密钥）

```bash
# GitHub SSH
pip install git+ssh://git@github.com/yourusername/all2txt.git

# GitLab SSH
pip install git+ssh://git@gitlab.com/yourusername/all2txt.git
```

## 开发模式安装

如果需要在开发时修改代码，可以使用可编辑模式安装：

```bash
# 先克隆仓库
git clone https://github.com/yourusername/all2txt.git
cd all2txt

# 可编辑模式安装
pip install -e .
```

这样修改代码后无需重新安装。

## 更新安装

如果已经安装过，需要更新到最新版本：

```bash
# 更新到最新主分支
pip install --upgrade git+https://github.com/yourusername/all2txt.git

# 更新到指定分支
pip install --upgrade git+https://github.com/yourusername/all2txt.git@develop
```

## 卸载

```bash
pip uninstall all2txt
```

## 验证安装

安装完成后，验证是否安装成功：

```bash
# 检查命令行工具
all2txt --help

# 在 Python 中测试导入
python -c "from all2txt import convert_pdf, docx_to_txt_simple; print('安装成功！')"
```

## 常见问题

### 1. 安装失败：找不到 Git

**错误信息**：`fatal: not a git repository`

**解决方案**：
- 确保已安装 Git
- 检查 Git 是否在系统 PATH 中

### 2. 安装失败：权限问题

**错误信息**：`Permission denied`

**解决方案**：
- 使用 `--user` 参数：`pip install --user git+https://...`
- 或使用虚拟环境：`python -m venv venv && source venv/bin/activate`

### 3. 私有仓库认证

对于私有仓库，需要提供认证信息：

```bash
# 使用 token
pip install git+https://username:token@github.com/yourusername/all2txt.git

# 或配置 Git 凭据
git config --global credential.helper store
```

### 4. 网络问题

如果遇到网络问题，可以：

```bash
# 使用代理
pip install --proxy http://proxy.example.com:8080 git+https://github.com/...

# 或使用国内镜像（如果项目在 Gitee）
pip install git+https://gitee.com/yourusername/all2txt.git
```

## 在 requirements.txt 中使用

可以在 `requirements.txt` 中指定从 Git 安装：

```txt
# 安装主分支
all2txt @ git+https://github.com/yourusername/all2txt.git

# 安装指定分支
all2txt @ git+https://github.com/yourusername/all2txt.git@develop

# 安装指定版本
all2txt @ git+https://github.com/yourusername/all2txt.git@v0.1.0
```

然后使用：

```bash
pip install -r requirements.txt
```

## 注意事项

1. **版本控制**：从 Git 安装时，pip 会检查仓库是否有 `pyproject.toml` 或 `setup.py`
2. **依赖安装**：pip 会自动安装 `pyproject.toml` 或 `requirements.txt` 中声明的依赖
3. **缓存**：pip 会缓存 Git 仓库，更新时可能需要使用 `--upgrade` 参数
4. **网络要求**：需要能够访问 Git 仓库（GitHub、GitLab 等）

