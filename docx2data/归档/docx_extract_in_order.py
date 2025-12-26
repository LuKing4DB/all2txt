"""
按照阅读顺序提取DOCX文件内容
遍历doc.element.body，按文档顺序提取文本、图片和表格
文本直接提取，图片和表格使用占位符标记
"""

import argparse
import sys
from pathlib import Path
from docx import Document

# 添加src目录到路径，以便导入image_filter模块
sys.path.insert(0, str(Path(__file__).parent))
from image_filter import (
    has_image, 
    is_large_image, 
    is_not_stamp_image,
    save_stamp_images,
    save_non_stamp_image
)


def extract_text_from_paragraph_element(doc, element):
    """
    从段落XML元素中提取文本内容
    使用python-docx的Paragraph对象来正确提取文本，避免重复
    
    Args:
        doc: Document对象
        element: 段落XML元素
        
    Returns:
        提取的文本字符串
    """
    # 找到对应的Paragraph对象
    for para in doc.paragraphs:
        if para._element == element:
            return para.text.strip()
    # 如果找不到对应的Paragraph对象，使用备用方法
    # 只提取直接子元素中的文本，避免重复
    text_parts = []
    for run in element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
        for t in run.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            if t.text:
                text_parts.append(t.text)
    return ''.join(text_parts).strip()


def extract_content_in_order(
    docx_path: str, 
    output_path: str = None, 
    min_image_size_cm: float = 2.0,
    use_stamp_detection: bool = True,
    debug: bool = False,
    save_stamps_dir: str = None,
    save_images_dir: str = None
) -> None:
    """
    按照阅读顺序提取DOCX文件中的所有内容
    
    Args:
        docx_path: DOCX文件路径
        output_path: 输出TXT文件路径，如果为None则自动生成
        min_image_size_cm: 图片最小尺寸阈值（厘米），小于此尺寸的图片将被过滤掉，默认2厘米
        use_stamp_detection: 是否使用特征检测来过滤印章，默认True（通过红色特征判定）
        debug: 是否输出调试信息，默认False
        save_stamps_dir: 保存印章图片的目录路径，如果为None则不保存，默认None
        save_images_dir: 保存非印章图片的目录路径，如果为None则不保存，默认None
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
        output_path = docx_file.with_name(docx_file.stem + '_ordered.txt')
    else:
        output_path = Path(output_path)
    
    try:
        # 读取DOCX文件
        doc = Document(docx_path)
        
        # 如果启用印章检测，使用特征检测判定印章
        stamp_hashes = set()
        if use_stamp_detection:
            from image_filter import detect_stamp_images_by_features
            stamp_hashes = detect_stamp_images_by_features(
                doc,
                check_red=True,
                debug=debug
            )
            if stamp_hashes:
                print(f"检测到 {len(stamp_hashes)} 个印章图片（大部分像素为红色的图片）")
                if debug:
                    print(f"  印章图片hash列表:")
                    for hash_val in stamp_hashes:
                        print(f"    - {hash_val}")
                
                # 如果指定了保存目录，保存印章图片
                if save_stamps_dir:
                    print(f"正在保存印章图片到: {save_stamps_dir}")
                    saved_files = save_stamp_images(doc, stamp_hashes, save_stamps_dir, debug=debug)
                    if saved_files:
                        print(f"已保存 {len(saved_files)} 个印章图片:")
                        for hash_val, filepath in saved_files.items():
                            print(f"  - {filepath} (hash: {hash_val[:8]}...)")
                    else:
                        print("警告: 未能保存任何印章图片")
            else:
                print("未检测到印章图片")
        
        # 存储提取的内容项
        content_items = []
        
        # 统计过滤的印章图片数量
        filtered_stamp_count = 0
        
        # 图片计数器（用于生成文件名）
        image_index = 0
        
        # 如果没有指定保存目录，使用输出文件所在目录下的images文件夹
        if save_images_dir is None:
            images_dir = output_path.parent / 'images'
        else:
            images_dir = Path(save_images_dir)
        
        # 遍历文档body中的所有元素（按阅读顺序）
        for element in doc.element.body:
            tag = element.tag
            
            # 处理段落 (w:p)
            if tag.endswith('}p') or tag == 'p':
                # 检查段落中是否有图片
                if has_image(element):
                    # 先提取文本（如果有）
                    text = extract_text_from_paragraph_element(doc, element)
                    if text:
                        content_items.append(('text', text))
                    
                    # 多重过滤条件
                    should_include = True
                    
                    # 1. 尺寸过滤
                    if not is_large_image(doc, element, min_image_size_cm):
                        should_include = False
                    
                    # 2. 印章检测过滤（如果启用）
                    if should_include and use_stamp_detection:
                        is_not_stamp, image_hash = is_not_stamp_image(doc, element, stamp_hashes, debug=debug)
                        if not is_not_stamp:
                            # 检测到印章图片，设置为False，完全过滤掉
                            should_include = False
                            filtered_stamp_count += 1
                            if debug:
                                print(f"  [过滤] 印章图片 (hash: {image_hash[:8] if image_hash else 'None'}...)，不保存也不输出")
                        else:
                            # 如果hash为None，需要直接检测是否为红色图片（因为无法通过hash判断）
                            if image_hash is None:
                                from image_filter import is_red_image
                                if is_red_image(doc, element, red_threshold=0.3, debug=debug):
                                    # 检测到红色图片，判定为印章
                                    should_include = False
                                    filtered_stamp_count += 1
                                    if debug:
                                        print(f"  [过滤] 红色图片（无法获取hash），不保存也不输出")
                            elif debug:
                                print(f"  [保留] 图片 (hash: {image_hash[:8]}...)")
                    
                    # 只有非印章图片才会保存和输出
                    if should_include:
                        # 先检查是否能获取图片数据
                        from image_filter import get_image_data_from_paragraph
                        image_data = get_image_data_from_paragraph(doc, element, debug=debug)
                        
                        if image_data is None:
                            # 无法获取图片数据（可能是链接图片或其他原因），直接过滤掉
                            if debug:
                                print(f"  [过滤] 无法获取图片数据（可能是链接图片），不保存也不输出")
                            # 不输出任何内容，直接跳过
                        else:
                            # 可以获取图片数据，尝试保存
                            image_path = save_non_stamp_image(
                                doc, 
                                element, 
                                str(images_dir), 
                                image_index, 
                                debug=debug
                            )
                            
                            if image_path:
                                # 保存成功，增加索引并输出路径
                                image_index += 1
                                # 计算相对路径（相对于输出文本文件）
                                try:
                                    rel_path = Path(image_path).relative_to(output_path.parent)
                                    image_path = str(rel_path).replace('\\', '/')  # 统一使用正斜杠
                                except ValueError:
                                    # 如果无法计算相对路径，使用绝对路径
                                    pass
                                
                                # 只有成功保存的图片才输出路径
                                content_items.append(('image', image_path))
                            else:
                                # 保存失败，直接过滤掉，不输出任何内容
                                if debug:
                                    print(f"  [过滤] 图片保存失败，不保存也不输出")
                                # 不增加索引，不输出任何内容
                    # else: 印章图片被过滤，不保存也不输出，直接跳过
                else:
                    # 普通段落，提取文本
                    text = extract_text_from_paragraph_element(doc, element)
                    if text:  # 只添加非空段落
                        content_items.append(('text', text))
            
            # 处理表格 (w:tbl)
            elif tag.endswith('}tbl') or tag == 'tbl':
                # 添加表格占位符
                content_items.append(('table', '[表格]'))
            
            # 其他元素类型（如sectPr等）可以忽略或根据需要处理
            # elif tag.endswith('}sectPr'):
            #     pass
        
        # 写入输出文件
        with open(output_path, 'w', encoding='utf-8') as f:
            for item_type, content in content_items:
                f.write(content + '\n')
        
        # 统计信息
        text_count = sum(1 for t, _ in content_items if t == 'text')
        image_count = sum(1 for t, _ in content_items if t == 'image')
        table_count = sum(1 for t, _ in content_items if t == 'table')
        
        print(f"提取完成: {docx_path} -> {output_path}")
        print(f"共提取 {len(content_items)} 个内容项:")
        print(f"  - 文本段落: {text_count} 个")
        filter_info = f"（已过滤小于{min_image_size_cm}cm的图片"
        if use_stamp_detection and stamp_hashes:
            filter_info += f"，已过滤{filtered_stamp_count}个印章图片实例（{len(stamp_hashes)}种不同的印章）"
        filter_info += "）"
        print(f"  - 图片{filter_info}: {image_count} 个")
        if image_count > 0:
            print(f"  - 图片已保存到: {images_dir}")
            # 统计实际保存的图片数量
            saved_image_files = list(images_dir.glob('image_*.png')) + list(images_dir.glob('image_*.jpg')) + list(images_dir.glob('image_*.gif')) + list(images_dir.glob('image_*.bmp'))
            print(f"  - 实际保存的图片文件数: {len(saved_image_files)} 个")
            if len(saved_image_files) < image_count and debug:
                print(f"  [警告] 保存的图片数量 ({len(saved_image_files)}) 少于输出的图片数量 ({image_count})")
        print(f"  - 表格: {table_count} 个")
        
    except Exception as e:
        print(f"错误: 处理文件时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='按照阅读顺序提取DOCX文件内容（文本、图片、表格）'
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
        help='输出的TXT文件路径（可选，默认生成 <原文件名>_ordered.txt）'
    )
    parser.add_argument(
        '--min-image-size',
        type=float,
        default=2.0,
        help='图片最小尺寸阈值（厘米），小于此尺寸的图片将被过滤掉，默认2.0厘米'
    )
    parser.add_argument(
        '--no-stamp-detection',
        action='store_true',
        help='禁用印章检测（特征检测：红色），默认启用'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='输出调试信息，显示检测到的印章图片和过滤过程'
    )
    parser.add_argument(
        '--save-stamps',
        type=str,
        default=None,
        help='保存印章图片的目录路径，如果指定则会将检测到的印章图片保存到该目录'
    )
    parser.add_argument(
        '--save-images',
        type=str,
        default=None,
        help='保存非印章图片的目录路径，如果指定则会将非印章图片保存到该目录，并在文本中使用图片路径替换[图片]占位符。如果不指定，默认保存到输出文件所在目录下的images文件夹'
    )
    
    args = parser.parse_args()
    extract_content_in_order(
        args.docx_path, 
        args.output, 
        args.min_image_size,
        use_stamp_detection=not args.no_stamp_detection,
        debug=args.debug,
        save_stamps_dir=args.save_stamps,
        save_images_dir=args.save_images
    )


if __name__ == '__main__':
    main()

