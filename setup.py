#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
setup.py for all2txt package
"""

from setuptools import setup, find_packages
from pathlib import Path

# 读取README文件
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# 读取requirements.txt
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        requirements = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

setup(
    name="all2txt",
    version="0.1.0",
    description="文档转换工具：支持PDF和DOCX文件转换为TXT格式",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="all2txt contributors",
    author_email="",
    url="https://github.com/yourusername/all2txt",
    packages=["all2txt", "all2txt.pdf2txt", "all2txt.pdf2txt.lib", "all2txt.docx2txt", "all2txt.docx2txt.lib", "all2txt.utils"],
    package_dir={"all2txt": "src"},
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "all2txt=all2txt.main:main",
        ],
    },
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Text Processing",
        "Topic :: Utilities",
    ],
    keywords="pdf docx converter text document",
)

