# docx-preview无法识别图片和表格中书签的问题

## 问题描述

`docx-preview` 库在渲染DOCX文档时，无法识别图片和表格中的书签。这导致通过书签跳转到这些位置时失败。

## 问题原因

### 1. 表格书签问题

**原始实现**：
- 书签直接插入到 `w:tbl` 元素的开头和末尾
- 书签的父元素是表格容器本身

**问题**：
- `docx-preview` 主要关注可渲染的内容（如文本run元素）
- 表格级别的书签不在可渲染内容范围内
- 因此无法被识别和渲染

### 2. 图片书签问题

**原始实现**：
- 书签插入到段落级别（`w:p` 元素）
- 对于包含图片的段落，书签可能不在包含图片的run中

**问题**：
- `docx-preview` 在渲染图片时，可能无法识别段落级别的书签
- 书签应该插入到包含图片的run元素内部

## 解决方案

### 1. 表格书签修复

将书签插入到表格第一行第一列的第一个run中，而不是表格元素级别：

```python
# 查找第一行第一列的第一个run
first_row = element.find(f'.//{ns}tr')
first_cell = first_row.find(f'.//{ns}tc')
first_para = first_cell.find(f'.//{ns}p')
first_run = first_para.find(f'.//{ns}r')

# 在第一个run之前插入起始书签
first_run.addprevious(bookmark_start)
# 在第一个run之后插入结束书签
first_run.addnext(bookmark_end)
```

### 2. 图片书签修复（当前实现）

**当前方案**：将书签插入到段落级别（在第一个run之前和最后一个run之后），与普通段落相同：

```python
# 对于所有段落（包括包含图片的段落），都将书签插入到段落级别
first_run.addprevious(bookmark_start)
last_run.addnext(bookmark_end)
```

**问题**：即使将书签插入到段落级别，docx-preview在渲染图片段落时可能仍然无法识别书签。

**可能的原因**：
- docx-preview在渲染图片时，可能不会将段落级别的书签传递到DOM中
- 图片段落的DOM结构与普通段落不同，书签可能丢失

**如果仍然无法识别，可以考虑**：
1. 在图片段落中查找文本run，如果有文本run，确保书签在文本run附近
2. 检查docx-preview的版本，看是否有更新支持图片书签
3. 使用其他定位方式（如通过元素索引）作为备用方案

## 修改后的代码

### `add_bookmark_to_table` 函数

- 优先将书签插入到表格第一行第一列的第一个run中
- 如果找不到合适的插入位置，回退到原来的方法（表格级别）

### `add_bookmark_to_paragraph` 函数

- 新增 `has_image_in_para` 参数
- 如果段落包含图片，将书签插入到包含图片的run中
- 否则，使用原来的方法（段落级别）

## 注意事项

1. **兼容性**：修改后的代码仍然保持向后兼容，如果找不到合适的插入位置，会回退到原来的方法

2. **性能**：查找表格第一行第一列和图片run需要额外的DOM遍历，但对性能影响很小

3. **测试**：建议重新生成带书签的DOCX文件，并在docx-preview中测试书签跳转功能

## 验证方法

1. 重新运行 `add_bookmarks_to_docx` 函数生成带书签的DOCX文件
2. 在 `docx_preview.html` 页面中加载文件
3. 尝试跳转到表格和图片的书签
4. 检查浏览器控制台，查看是否找到书签元素

## 相关文件

- `docx2data/docx2txt/lib/bookmark_processor.py` - 书签处理模块
- `web/static/docx_preview.html` - DOCX预览页面

