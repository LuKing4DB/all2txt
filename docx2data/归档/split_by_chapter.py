"""
按章节分割TXT文件脚本
输入一个文件目录，例如data/1，将其中同名txt文件（1.txt），
利用正则规则（默认用"第x章"）分解成n个子文件，导出到一个文件夹中
"""

import argparse
import re
import sys
from pathlib import Path


def chinese_to_number(chinese_num):
    """将中文数字转换为阿拉伯数字，支持基本数字和组合数字"""
    # 基本数字映射
    basic_nums = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
    }
    
    # 单位映射
    units = {'十': 10, '百': 100, '千': 1000, '万': 10000}
    
    # 如果直接匹配，直接返回
    if chinese_num in basic_nums:
        return basic_nums[chinese_num]
    
    # 处理简单组合，如"十一"到"十九"
    if len(chinese_num) == 2 and chinese_num[0] == '十' and chinese_num[1] in basic_nums:
        return 10 + basic_nums[chinese_num[1]]
    
    # 处理"二十"、"三十"等
    if len(chinese_num) == 2 and chinese_num[1] == '十':
        if chinese_num[0] in basic_nums:
            return basic_nums[chinese_num[0]] * 10
    
    # 处理"二十一"到"九十九"
    if len(chinese_num) == 3 and chinese_num[1] == '十':
        if chinese_num[0] in basic_nums and chinese_num[2] in basic_nums:
            return basic_nums[chinese_num[0]] * 10 + basic_nums[chinese_num[2]]
    
    # 对于更复杂的数字（如"百"、"千"、"万"），返回None，让文件名使用原始文本
    # 这样可以避免复杂的解析逻辑，同时保持兼容性
    return None


def sanitize_filename(title: str) -> str:
    """
    清理文件名，移除不安全的字符，但保留中文字符
    
    Args:
        title: 原始标题文本
        
    Returns:
        清理后的安全文件名
    """
    # Windows和Unix都不允许的字符：< > : " / \ | ? *
    # 同时移除控制字符（ASCII 0-31）
    # 保留中文字符、字母、数字、空格、连字符、下划线等
    unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
    safe_title = re.sub(unsafe_chars, '', title)
    # 将多个连续空格替换为单个下划线
    safe_title = re.sub(r'\s+', '_', safe_title)
    # 移除开头和结尾的下划线
    safe_title = safe_title.strip('_')
    return safe_title if safe_title else 'unknown'


def parse_chapter_number(chapter_match):
    """解析章节号，支持中文和阿拉伯数字"""
    # 检查是否有捕获组
    try:
        chapter_text = chapter_match.group(1)  # 获取"一"、"二"或"1"、"2"等
    except IndexError:
        # 如果没有捕获组，尝试从整个匹配文本中提取数字部分
        full_match = chapter_match.group(0)
        # 尝试提取"第"和"章"/"卷"之间的内容
        # 例如："第一卷" -> "一"，"第3章" -> "3"
        match = re.search(r'第([一二三四五六七八九十百千万\d]+)[卷章]', full_match)
        if match:
            chapter_text = match.group(1)
        else:
            # 如果无法提取，返回None
            return None
    
    # 尝试转换为数字
    if chapter_text.isdigit():
        return int(chapter_text)
    else:
        num = chinese_to_number(chapter_text)
        if num is not None:
            return num
        # 如果无法转换，返回None，使用原始文本作为文件名的一部分
        return None


def split_by_chapter(input_dir: str, pattern: str = None, output_dir: str = None, merge_threshold: int = 3):
    """
    按章节分割TXT文件
    
    Args:
        input_dir: 输入目录路径，例如 data/1
        pattern: 正则表达式模式，默认为"^第[一二三四五六七八九十\\d]+章"（匹配行首）
        output_dir: 输出目录，如果为None则在输入目录下创建sub文件夹
        merge_threshold: 合并重复章节的行号阈值，如果两个相同章节号的行号相差小于等于此值，则合并（默认3行）
    """
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)
    
    if not input_path.is_dir():
        print(f"错误: 不是目录: {input_dir}")
        sys.exit(1)
    
    # 获取目录名作为文件名（例如 data/1 -> 1.txt）
    dir_name = input_path.name
    txt_file = input_path / f"{dir_name}.txt"
    
    if not txt_file.exists():
        print(f"错误: 文件不存在: {txt_file}")
        sys.exit(1)
    
    # 设置默认正则表达式模式（匹配行首的章节标题）
    if pattern is None:
        # 匹配：行首的"第x章"
        pattern = r"^第([一二三四五六七八九十\d]+)章"
    
    # 设置输出目录
    if output_dir is None:
        output_path = input_path / "sub"
    else:
        output_path = Path(output_dir)
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"正在读取文件: {txt_file}")
    print(f"使用正则表达式: {pattern}")
    print(f"输出目录: {output_path}")
    
    # 读取文件内容
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"错误: 无法读取文件: {e}")
        sys.exit(1)
    
    # 按行分割，保留行号信息
    lines = content.split('\n')
    
    # 查找所有章节位置
    chapter_positions = []
    chapter_pattern = re.compile(pattern)
    
    for i, line in enumerate(lines):
        match = chapter_pattern.search(line)
        if match:
            # 进一步验证：确保不是正文中的引用
            line_stripped = line.strip()
            chapter_match_text = match.group(0)  # 如"第一章"
            
            # 如果行以"第x章"开头，且后面不是引号，则认为是真正的章节标题
            # 正文中的引用通常是："第二章"投标人须知"前附表..."（有引号）
            if line_stripped.startswith(chapter_match_text):
                # 检查"第x章"后面是否有引号（中文或英文引号）
                after_chapter = line_stripped[len(chapter_match_text):].strip()
                # 如果后面是引号开头，则跳过（这是正文中的引用）
                # 检查中文引号（"、"）和英文引号（"、"）
                # Unicode: " (8220), " (8221), " (8222), " (8223)
                if after_chapter and (after_chapter[0] in ['"', '"', '"', '"', '"', '"'] or ord(after_chapter[0]) in [8220, 8221, 8222, 8223]):
                    continue
                
                chapter_num = parse_chapter_number(match)
                chapter_title = chapter_match_text
                chapter_positions.append({
                    'line': i,
                    'title': chapter_title,
                    'number': chapter_num,
                    'full_line': line
                })
    
    if not chapter_positions:
        print(f"警告: 未找到匹配的章节标记（模式: {pattern}）")
        sys.exit(1)
    
    print(f"找到 {len(chapter_positions)} 个章节:")
    for pos in chapter_positions:
        print(f"  - {pos['title']} (行 {pos['line'] + 1})")
    
    # 合并相邻或相近的重复章节
    # 如果两个相同章节号的行号相差小于等于阈值，则合并
    merged_positions = []
    skip_indices = set()
    
    for idx, pos in enumerate(chapter_positions):
        if idx in skip_indices:
            continue
        
        # 检查后续是否有相邻的重复章节
        current_number = pos['number']
        current_line = pos['line']
        
        # 查找后续相邻的重复章节
        merged_lines = [current_line]
        next_idx = idx + 1
        
        while next_idx < len(chapter_positions):
            next_pos = chapter_positions[next_idx]
            next_number = next_pos['number']
            next_line = next_pos['line']
            
            # 如果是相同的章节号，且行号相近（相差小于等于阈值）
            if next_number == current_number and (next_line - current_line) <= merge_threshold:
                merged_lines.append(next_line)
                skip_indices.add(next_idx)
                print(f"  合并: {pos['title']} (行 {next_line + 1}) 到 (行 {current_line + 1})")
                next_idx += 1
            else:
                break
        
        # 使用第一个位置作为章节起始位置
        merged_positions.append(pos)
    
    print(f"\n合并后剩余 {len(merged_positions)} 个章节")
    
    # 检查第一个章节之前是否有内容，如果有则作为第0个文件
    first_chapter_line = merged_positions[0]['line'] if merged_positions else len(lines)
    file_count = 0
    
    # 如果第一个章节之前有内容，保存为第0个文件
    if first_chapter_line > 0:
        chapter_lines = lines[0:first_chapter_line]
        chapter_content = '\n'.join(chapter_lines)
        filename = "0.txt"
        output_file = output_path / filename
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(chapter_content)
            print(f"已保存: {output_file} (行 1-{first_chapter_line})")
            file_count += 1
        except Exception as e:
            print(f"错误: 无法写入文件 {output_file}: {e}")
    
    # 分割文件
    for idx, pos in enumerate(merged_positions):
        start_line = pos['line']
        
        # 确定结束行（下一个章节的开始，或文件末尾）
        if idx + 1 < len(merged_positions):
            end_line = merged_positions[idx + 1]['line']
        else:
            end_line = len(lines)
        
        # 提取章节内容
        chapter_lines = lines[start_line:end_line]
        chapter_content = '\n'.join(chapter_lines)
        
        # 生成文件名：使用序号，从0开始（如果前面有第0个文件，则从1开始）
        file_index = file_count
        filename = f"{file_index}.txt"
        
        output_file = output_path / filename
        
        # 写入文件
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(chapter_content)
            print(f"已保存: {output_file} (行 {start_line + 1}-{end_line})")
            file_count += 1
        except Exception as e:
            print(f"错误: 无法写入文件 {output_file}: {e}")
    
    print(f"\n完成! 共分割为 {file_count} 个文件，保存在: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='按章节分割TXT文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python src/split_by_chapter.py data/1
  python src/split_by_chapter.py data/1 -p "^第[一二三四五六七八九十\\d]+章"
  python src/split_by_chapter.py data/1 -o output/chapters
        """
    )
    
    parser.add_argument(
        'input_dir',
        type=str,
        help='输入目录路径，例如 data/1'
    )
    
    parser.add_argument(
        '-p', '--pattern',
        type=str,
        default=None,
        help='正则表达式模式，默认为"^第[一二三四五六七八九十\\d]+章"（匹配行首）'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出目录，如果未指定则在输入目录下创建sub文件夹'
    )
    
    parser.add_argument(
        '-m', '--merge-threshold',
        type=int,
        default=3,
        help='合并重复章节的行号阈值，如果两个相同章节号的行号相差小于等于此值，则合并（默认3行）'
    )
    
    args = parser.parse_args()
    
    split_by_chapter(args.input_dir, args.pattern, args.output, args.merge_threshold)


if __name__ == '__main__':
    main()

