"""
书签处理模块
为DOCX文件中的段落、表格和图片添加书签
"""

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx import Document
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger
from lib.paragraph_processor import extract_paragraph_text_raw
from lib.image_detector import has_image

logger = get_logger(__name__)


def add_bookmark_to_paragraph(element, bookmark_name: str, bookmark_id: int, has_image_in_para: bool = False):
    """
    为段落元素添加书签（正确插入到段落内部）
    
    对于所有段落（包括包含图片的段落），都将书签插入到段落级别（在第一个run之前和最后一个run之后），
    而不是run内部。这样docx-preview可以识别段落级别的书签。
    
    注意：如果docx-preview仍然无法识别图片段落中的书签，可能需要其他方案。
    
    Args:
        element: 段落XML元素
        bookmark_name: 书签名称
        bookmark_id: 书签ID（必须唯一）
        has_image_in_para: 段落是否包含图片（当前未使用，保留用于未来扩展）
    """
    # 创建书签起始元素
    bookmark_start = OxmlElement('w:bookmarkStart')
    bookmark_start.set(qn('w:id'), str(bookmark_id))
    bookmark_start.set(qn('w:name'), bookmark_name)
    
    # 创建书签结束元素
    bookmark_end = OxmlElement('w:bookmarkEnd')
    bookmark_end.set(qn('w:id'), str(bookmark_id))
    
    # 段落结构：w:p -> w:pPr (可选) -> w:r (run) -> ...
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    
    # 获取段落的所有直接子元素（按顺序）
    # 对于所有段落（包括包含图片的段落），都将书签插入到段落级别
    # 因为docx-preview主要识别段落级别的书签，而不是run内部的书签
    # 这样可以确保图片段落中的书签也能被docx-preview识别
    children = list(element)
    
    # 找到第一个和最后一个run元素的索引
    first_run_index = None
    last_run_index = None
    
    for i, child in enumerate(children):
        child_tag = child.tag
        if callable(child_tag):
            child_tag = child_tag()
        if isinstance(child_tag, str) and (child_tag.endswith('}r') or child_tag == 'r'):
            if first_run_index is None:
                first_run_index = i
            last_run_index = i
    
    if first_run_index is not None and last_run_index is not None:
        # 如果有run元素，将书签插入到段落元素内部
        # 使用addprevious和addnext方法，确保书签插入到段落元素内部
        # 获取第一个和最后一个run元素对象
        first_run = children[first_run_index]
        last_run = children[last_run_index]
        
        # 在第一个run之前插入起始书签（会插入到段落元素内部）
        first_run.addprevious(bookmark_start)
        
        # 在最后一个run之后插入结束书签（会插入到段落元素内部）
        last_run.addnext(bookmark_end)
    else:
        # 如果没有run元素，检查是否有段落属性（pPr）
        pPr_index = None
        for i, child in enumerate(children):
            child_tag = child.tag
            if callable(child_tag):
                child_tag = child_tag()
            if isinstance(child_tag, str) and (child_tag.endswith('}pPr') or child_tag == 'pPr'):
                pPr_index = i
                break
        
        if pPr_index is not None:
            # 在pPr之后插入书签
            element.insert(pPr_index + 1, bookmark_start)
            element.insert(pPr_index + 2, bookmark_end)
        else:
            # 既没有run也没有pPr，插入到段落元素的第一个位置和最后一个位置
            # 但这种情况应该很少，因为我们已经过滤了空段落
            element.insert(0, bookmark_start)
            element.append(bookmark_end)


def add_bookmark_to_table(element, bookmark_name: str, bookmark_id: int):
    """
    为表格元素添加书签
    将书签插入到表格第一行第一列的第一个run中，以便docx-preview能够识别
    
    Args:
        element: 表格XML元素
        bookmark_name: 书签名称
        bookmark_id: 书签ID（必须唯一）
    """
    # 创建书签起始元素
    bookmark_start = OxmlElement('w:bookmarkStart')
    bookmark_start.set(qn('w:id'), str(bookmark_id))
    bookmark_start.set(qn('w:name'), bookmark_name)
    
    # 创建书签结束元素
    bookmark_end = OxmlElement('w:bookmarkEnd')
    bookmark_end.set(qn('w:id'), str(bookmark_id))
    
    # 表格结构：w:tbl -> w:tblPr (可选) -> w:tr (行) -> w:tc (单元格) -> w:p (段落) -> w:r (run)
    # 为了docx-preview能够识别，将书签插入到第一行第一列的第一个run中
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    
    # 查找第一行
    first_row = element.find(f'.//{ns}tr')
    if first_row is not None:
        # 查找第一列
        first_cell = first_row.find(f'.//{ns}tc')
        if first_cell is not None:
            # 查找第一个段落
            first_para = first_cell.find(f'.//{ns}p')
            if first_para is not None:
                # 查找第一个run
                first_run = first_para.find(f'.//{ns}r')
                if first_run is not None:
                    # 在第一个run之前插入起始书签
                    first_run.addprevious(bookmark_start)
                    # 在第一个run之后插入结束书签
                    first_run.addnext(bookmark_end)
                    return
    
    # 如果找不到合适的插入位置，回退到原来的方法（插入到表格级别）
    # 但这不是最佳方案，因为docx-preview可能无法识别
    element.insert(0, bookmark_start)
    element.append(bookmark_end)


def add_bookmarks_to_docx(docx_path: str, output_path: str = None) -> str:
    """
    为DOCX文件中的所有段落、表格和图片添加书签，并生成副本
    
    Args:
        docx_path: 输入的DOCX文件路径
        output_path: 输出的DOCX文件路径，如果为None则自动生成（在原文件名后加_bookmarked）
        
    Returns:
        生成的带书签的DOCX文件路径
    """
    docx_file = Path(docx_path)
    
    if not docx_file.exists():
        raise FileNotFoundError(f"文件不存在: {docx_path}")
    
    if not docx_file.suffix.lower() == '.docx':
        raise ValueError(f"不是DOCX文件: {docx_path}")
    
    # 确定输出路径
    if output_path is None:
        output_path = docx_file.parent / (docx_file.stem + '_bookmarked.docx')
    else:
        output_path = Path(output_path)
    
    # 读取DOCX文件
    doc = Document(docx_path)
    
    # 删除文档中所有已存在的书签
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    removed_count = 0
    
    # 从文档body中查找所有书签（包括嵌套的元素）
    bookmark_starts = doc.element.body.findall(f'.//{ns}bookmarkStart')
    bookmark_ends = doc.element.body.findall(f'.//{ns}bookmarkEnd')
    
    # 删除所有书签起始标记
    for bookmark_start in bookmark_starts:
        parent = bookmark_start.getparent()
        if parent is not None:
            parent.remove(bookmark_start)
            removed_count += 1
    
    # 删除所有书签结束标记
    for bookmark_end in bookmark_ends:
        parent = bookmark_end.getparent()
        if parent is not None:
            parent.remove(bookmark_end)
            removed_count += 1
    
    if removed_count > 0:
        logger.info(f"已删除 {removed_count} 个已存在的书签")
    
    # 优化：一次性建立元素到Paragraph对象的映射
    element_to_para = {para._element: para for para in doc.paragraphs}
    
    # 书签ID计数器（从1开始，因为已经删除了所有旧书签）
    bookmark_id_counter = 0
    
    # 遍历文档body中的所有元素（按阅读顺序）
    for element_index, element in enumerate(doc.element.body):
        try:
            # 安全获取tag
            tag = element.tag
            if callable(tag):
                tag = tag()
            if not isinstance(tag, str):
                tag = str(tag) if tag is not None else ''
            
            # 处理段落 (w:p)
            if tag.endswith('}p') or tag == 'p':
                # 检查段落是否为空：既没有文本也没有图片
                raw_text = extract_paragraph_text_raw(doc, element, element_to_para)
                has_image_in_para = has_image(element)
                
                # 如果段落有文本或图片，才添加书签
                if raw_text or has_image_in_para:
                    bookmark_name = f'index_{element_index}'
                    bookmark_id_counter += 1
                    add_bookmark_to_paragraph(element, bookmark_name, bookmark_id_counter, has_image_in_para)
                    logger.debug(f"为段落 {element_index} 添加书签: {bookmark_name} (包含图片: {has_image_in_para})")
                else:
                    logger.debug(f"跳过空段落 {element_index}")
            
            # 处理表格 (w:tbl)
            elif tag.endswith('}tbl') or tag == 'tbl':
                bookmark_name = f'index_{element_index}'
                bookmark_id_counter += 1
                add_bookmark_to_table(element, bookmark_name, bookmark_id_counter)
                logger.debug(f"为表格 {element_index} 添加书签: {bookmark_name}")
            
            # 其他元素类型（如sectPr等）跳过，不添加书签
        except Exception as e:
            logger.warning(f"处理元素 {element_index} 时出错: {e}，已跳过该元素")
            continue
    
    # 保存带书签的文档
    doc.save(str(output_path))
    logger.info(f"已生成带书签的文档副本: {output_path}")
    
    return str(output_path)

