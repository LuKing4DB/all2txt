"""
DOCX转TXT脚本
将DOCX文件中的每个段落转换为TXT文件的一行，并输出包含页码的metadata文件
页码从页脚信息中读取
"""

import argparse
import sys
from pathlib import Path
from docx import Document

# 添加src目录到路径，以便导入page_number_extractor模块
sys.path.insert(0, str(Path(__file__).parent))
from page_number_extractor import get_page_numbers_for_paragraphs


def docx_to_txt(docx_path: str, output_path: str = None) -> None:
    """
    将DOCX文件转换为TXT文件，每个段落作为一行，并输出metadata文件
    
    Args:
        docx_path: DOCX文件路径
        output_path: 输出TXT文件路径，如果为None则自动生成
    """
    docx_file = Path(docx_path)
    
    if not docx_file.exists():
        print(f"错误: 文件不存在: {docx_path}")
        sys.exit(1)
    
    if not docx_file.suffix.lower() == '.docx':
        print(f"错误: 不是DOCX文件: {docx_path}")
        sys.exit(1)
    
    # 如果没有指定输出路径，自动生成
    if output_path is None:
        output_path = docx_file.with_suffix('.txt')
    else:
        output_path = Path(output_path)
    
    # metadata文件路径
    metadata_path = output_path.with_name(output_path.stem + '_metadata.txt')
    
    try:
        # 读取DOCX文件
        doc = Document(docx_path)
        
        # 提取所有段落文本和索引
        paragraphs = []
        paragraph_indices = []
        for idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:  # 只添加非空段落
                paragraphs.append(text)
                paragraph_indices.append(idx)
        
        # 为每个段落计算页码（启用调试模式以查看页脚读取详情）
        page_numbers = get_page_numbers_for_paragraphs(doc, paragraph_indices, debug=True)
        
        # 写入TXT文件
        with open(output_path, 'w', encoding='utf-8') as f:
            for para_text in paragraphs:
                f.write(para_text + '\n')
        
        # 写入metadata文件（每行对应txt文件的一行，只包含页码）
        with open(metadata_path, 'w', encoding='utf-8') as f:
            for page_num in page_numbers:
                f.write(f"{page_num}\n")
        
        print(f"转换完成: {docx_path} -> {output_path}")
        print(f"Metadata文件: {metadata_path}")
        print(f"共提取 {len(paragraphs)} 个段落")
        
    except Exception as e:
        print(f"错误: 处理文件时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将DOCX文件转换为TXT文件，每个段落作为一行'
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
        help='输出的TXT文件路径（可选，默认与输入文件同名）'
    )
    
    args = parser.parse_args()
    docx_to_txt(args.docx_path, args.output)


if __name__ == '__main__':
    main()

