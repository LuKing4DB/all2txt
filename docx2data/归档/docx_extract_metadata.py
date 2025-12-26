"""
提取DOCX文件中每个段落的格式信息
包括段落编号、对齐方式、样式、加粗、字体、字号、原文等信息，并写入metadata.txt
"""

import argparse
import sys
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


def get_alignment_name(alignment):
    """
    将对齐方式枚举值转换为字符串
    
    Args:
        alignment: WD_ALIGN_PARAGRAPH枚举值或None
        
    Returns:
        对齐方式字符串
    """
    if alignment is None:
        return "左对齐"
    
    alignment_map = {
        WD_ALIGN_PARAGRAPH.LEFT: "左对齐",
        WD_ALIGN_PARAGRAPH.CENTER: "居中",
        WD_ALIGN_PARAGRAPH.RIGHT: "右对齐",
        WD_ALIGN_PARAGRAPH.JUSTIFY: "两端对齐",
        WD_ALIGN_PARAGRAPH.DISTRIBUTE: "分散对齐",
    }
    
    return alignment_map.get(alignment, f"未知对齐({alignment})")


def get_font_from_style(style):
    """
    从样式中获取字体名称
    
    Args:
        style: Style对象
        
    Returns:
        字体名称字符串，如果无法获取则返回None
    """
    if style is None:
        return None
    
    try:
        # 尝试从样式的字体设置中获取
        if hasattr(style, 'font') and style.font:
            if style.font.name:
                return style.font.name
            elif hasattr(style.font, 'complex_script') and style.font.complex_script:
                return style.font.complex_script
    except:
        pass
    
    return None


def get_size_from_style(style):
    """
    从样式中获取字号
    
    Args:
        style: Style对象
        
    Returns:
        字号字符串（如"12.0pt"），如果无法获取则返回None
    """
    if style is None:
        return None
    
    try:
        # 尝试从样式的字体设置中获取
        if hasattr(style, 'font') and style.font and style.font.size:
            return f"{style.font.size.pt:.1f}pt"
    except:
        pass
    
    return None


def convert_font_to_english(font_name):
    """
    将中文字体名称转换为英文名称
    
    Args:
        font_name: 字体名称字符串
        
    Returns:
        转换后的英文字体名称
    """
    if not font_name:
        return font_name
    
    font_name_lower = font_name.lower().strip()
    
    # 中文字体名称到英文名称的映射
    font_mapping = {
        # 常见中文字体
        '宋体': 'SimSun',
        '黑体': 'SimHei',
        '楷体': 'SimKai',
        '仿宋': 'SimFang',
        '微软雅黑': 'Microsoft YaHei',
        '微软正黑体': 'Microsoft JhengHei',
        '华文宋体': 'STSong',
        '华文黑体': 'STHeiti',
        '华文楷体': 'STKaiti',
        '华文仿宋': 'STFangsong',
        '华文细黑': 'STXihei',
        '华文中宋': 'STZhongsong',
        '华文隶书': 'STLiti',
        '华文彩云': 'STCaiyun',
        '华文行楷': 'STXingkai',
        '华文新魏': 'STXinwei',
        '幼圆': 'YouYuan',
        '隶书': 'LiSu',
        # 英文名称的变体（保持原样或标准化）
        'songti': 'SimSun',
        'heiti': 'SimHei',
        'kaiti': 'SimKai',
        'fangsong': 'SimFang',
        'yahei': 'Microsoft YaHei',
        'jhenghei': 'Microsoft JhengHei',
        'stsong': 'STSong',
        'stheit': 'STHeiti',
        'stkaiti': 'STKaiti',
        'stfangsong': 'STFangsong',
        'stxihei': 'STXihei',
        'stzhongsong': 'STZhongsong',
        'stliti': 'STLiti',
        'stcaiyun': 'STCaiyun',
        'stxingkai': 'STXingkai',
        'stxinwei': 'STXinwei',
        'youyuan': 'YouYuan',
        'lishu': 'LiSu',
    }
    
    # 检查是否包含中文字符
    import re
    if re.search(r'[\u4e00-\u9fff]', font_name):
        # 包含中文字符，尝试映射
        for chinese_name, english_name in font_mapping.items():
            if chinese_name in font_name:
                return english_name
    
    # 检查是否为已知的英文变体
    for key, value in font_mapping.items():
        if font_name_lower == key.lower() or font_name_lower.startswith(key.lower() + ' ') or font_name_lower.endswith(' ' + key.lower()):
            return value
    
    # 如果已经是标准英文名称（如SimSun, SimHei等），保持原样
    standard_fonts = ['simsun', 'simhei', 'simkai', 'simfang', 'microsoft yahei', 'microsoft jhenghei',
                      'stsong', 'stheit', 'stkaiti', 'stfangsong', 'stxihei', 'stzhongsong',
                      'stliti', 'stcaiyun', 'stxingkai', 'stxinwei', 'youyuan', 'lisu']
    
    for std_font in standard_fonts:
        if font_name_lower == std_font or font_name_lower.startswith(std_font + ' ') or font_name_lower.endswith(' ' + std_font):
            # 标准化大小写
            if std_font == 'simsun':
                return 'SimSun'
            elif std_font == 'simhei':
                return 'SimHei'
            elif std_font == 'simkai':
                return 'SimKai'
            elif std_font == 'simfang':
                return 'SimFang'
            elif std_font == 'microsoft yahei':
                return 'Microsoft YaHei'
            elif std_font == 'microsoft jhenghei':
                return 'Microsoft JhengHei'
            elif std_font == 'stsong':
                return 'STSong'
            elif std_font == 'stheit':
                return 'STHeiti'
            elif std_font == 'stkaiti':
                return 'STKaiti'
            elif std_font == 'stfangsong':
                return 'STFangsong'
            elif std_font == 'stxihei':
                return 'STXihei'
            elif std_font == 'stzhongsong':
                return 'STZhongsong'
            elif std_font == 'stliti':
                return 'STLiti'
            elif std_font == 'stcaiyun':
                return 'STCaiyun'
            elif std_font == 'stxingkai':
                return 'STXingkai'
            elif std_font == 'stxinwei':
                return 'STXinwei'
            elif std_font == 'youyuan':
                return 'YouYuan'
            elif std_font == 'lisu':
                return 'LiSu'
    
    # 如果无法识别，返回原样
    return font_name


def is_chinese_font(font_name):
    """
    判断是否为中文字体
    
    Args:
        font_name: 字体名称字符串
        
    Returns:
        如果是中文字体返回True，否则返回False
    """
    if not font_name:
        return False
    
    font_name_lower = font_name.lower().strip()
    # 常见中文字体名称（不区分大小写）
    chinese_font_keywords = [
        'simsun', 'simhei', 'simkai', 'simfang', 'fangsong', 'kaiti',
        'microsoft yahei', 'yahei', 'microsoft jhenghei', 'jhenghei',
        'stsong', 'stheit', 'stkaiti', 'stfangsong', 'stxihei',
        'stzhongsong', 'stliti', 'stcaiyun', 'stxingkai', 'stxinwei',
        'songti', 'heiti', 'youyuan', 'lishu',
        'kaiti sc', 'songti sc', 'heiti sc', 'fangsong sc',
        '宋体', '黑体', '楷体', '仿宋', '微软雅黑', '华文'
    ]
    
    # 精确匹配或包含中文字体关键词
    for keyword in chinese_font_keywords:
        if font_name_lower == keyword or font_name_lower.startswith(keyword + ' ') or font_name_lower.endswith(' ' + keyword) or (' ' + keyword + ' ') in (' ' + font_name_lower + ' '):
            return True
    
    # 检查是否包含中文字符
    import re
    if re.search(r'[\u4e00-\u9fff]', font_name):
        return True
    
    return False


def get_paragraph_format_info(para, doc=None):
    """
    提取段落的格式信息
    当段落中有多个字体时，优先选择中文字体
    
    Args:
        para: Paragraph对象
        doc: Document对象（可选，用于获取默认样式）
        
    Returns:
        包含格式信息的字典
    """
    # 获取段落对齐方式
    alignment = get_alignment_name(para.alignment)
    
    # 获取段落样式
    style_name = para.style.name if para.style else "无样式"
    para_style = para.style if para.style else None
    
    # 获取段落中的字体信息（优先选择中文字体）
    font_name = None
    font_size = None
    is_bold = False
    chinese_font_found = False
    fallback_font = None  # 备选字体（非中文字体）
    fallback_size = None
    fallback_bold = False
    
    if para.runs:
        # 遍历所有runs，优先查找中文字体
        for run in para.runs:
            if run.text.strip():
                # 获取字体名称
                current_font = None
                if run.font.name:
                    current_font = run.font.name
                elif run.font.complex_script:
                    current_font = run.font.complex_script
                
                # 如果找到中文字体，优先使用
                if current_font and is_chinese_font(current_font):
                    if not chinese_font_found:
                        font_name = current_font
                        chinese_font_found = True
                        # 获取字号和加粗信息
                        if run.font.size:
                            font_size = f"{run.font.size.pt:.1f}pt"
                        is_bold = run.bold if run.bold is not None else False
                # 如果还没找到中文字体，记录第一个字体作为备选
                elif current_font and fallback_font is None:
                    fallback_font = current_font
                    if run.font.size:
                        fallback_size = f"{run.font.size.pt:.1f}pt"
                    fallback_bold = run.bold if run.bold is not None else False
        
        # 如果所有run都为空，使用第一个run的格式
        if font_name is None and fallback_font is None and para.runs:
            run = para.runs[0]
            if run.font.name:
                fallback_font = run.font.name
            elif run.font.complex_script:
                fallback_font = run.font.complex_script
            
            if run.font.size:
                fallback_size = f"{run.font.size.pt:.1f}pt"
            
            fallback_bold = run.bold if run.bold is not None else False
    
    # 如果没有找到中文字体，从段落样式或文档样式中获取中文字体
    if not chinese_font_found:
        # 先尝试从段落样式中获取
        style_font = get_font_from_style(para_style)
        if style_font and is_chinese_font(style_font):
            font_name = style_font
        # 如果段落样式也没有中文字体，尝试从Normal样式中获取
        elif doc is not None:
            try:
                normal_style = doc.styles.get('Normal', None)
                if normal_style:
                    normal_font = get_font_from_style(normal_style)
                    if normal_font and is_chinese_font(normal_font):
                        font_name = normal_font
            except:
                pass
        
        # 如果仍然没有找到中文字体，使用默认的中文字体
        if font_name is None or not is_chinese_font(font_name):
            font_name = "宋体"  # 中文文档常见默认字体
        
        # 使用备选字体的字号和加粗信息（如果存在）
        if fallback_size:
            font_size = fallback_size
        if fallback_bold:
            is_bold = fallback_bold
    
    # 如果run中没有字号信息，从段落样式中获取
    if font_size is None:
        font_size = get_size_from_style(para_style)
        # 如果段落样式也没有，尝试从Normal样式中获取
        if font_size is None and doc is not None:
            try:
                normal_style = doc.styles.get('Normal', None)
                if normal_style:
                    font_size = get_size_from_style(normal_style)
            except:
                pass
    
    # 如果仍然无法获取字号，使用默认值
    if font_size is None:
        font_size = "12.0pt"  # Word常见默认字号
    
    # 将字体名称转换为英文
    font_name = convert_font_to_english(font_name)
    
    return {
        "对齐方式": alignment,
        "样式": style_name,
        "字体": font_name,
        "字号": font_size,
        "加粗": "是" if is_bold else "否"
    }


def extract_paragraph_metadata(
    docx_path: str,
    output_path: str = None
) -> None:
    """
    提取DOCX文件中每个段落的格式信息并写入metadata.txt
    输出格式：索引|字体|字号|原文
    
    Args:
        docx_path: DOCX文件路径
        output_path: 输出metadata文件路径，如果为None则自动生成
    """
    docx_file = Path(docx_path)
    
    if not docx_file.exists():
        print(f"错误: 文件不存在: {docx_path}")
        sys.exit(1)
    
    if not docx_file.suffix.lower() == '.docx':
        print(f"错误: 不是DOCX文件: {docx_path}")
        sys.exit(1)
    
    # 如果没有指定输出路径，自动生成：文件名_metadata.txt
    if output_path is None:
        metadata_path = docx_file.parent / f'{docx_file.stem}_metadata.txt'
    else:
        metadata_path = Path(output_path)
    
    try:
        # 读取DOCX文件
        doc = Document(docx_path)
        
        # 存储所有段落的格式信息
        metadata_list = []
        
        # 遍历所有段落
        for idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:  # 只处理非空段落
                format_info = get_paragraph_format_info(para, doc)
                format_info["原始索引"] = idx
                format_info["原文"] = text  # 添加原文内容
                
                metadata_list.append(format_info)
        
        # 写入metadata文件，使用|分割格式：索引|字体|字号|原文
        with open(metadata_path, 'w', encoding='utf-8') as f:
            for meta in metadata_list:
                line = (
                    f"{meta['原始索引']}|"
                    f"{meta['字体']}|"
                    f"{meta['字号']}|"
                    f"{meta['原文']}"
                )
                f.write(line + '\n')
        
        print(f"提取完成: {docx_path} -> {metadata_path}")
        print(f"共提取 {len(metadata_list)} 个段落的格式信息")
        
    except Exception as e:
        print(f"错误: 处理文件时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='提取DOCX文件中每个段落的格式信息，输出格式：索引|字体|字号|原文'
    )
    parser.add_argument(
        'docx_path',
        type=str,
        help='输入的DOCX文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出的metadata文件路径（可选，默认为metadata.txt）'
    )
    
    args = parser.parse_args()
    extract_paragraph_metadata(args.docx_path, args.output)


if __name__ == '__main__':
    main()

