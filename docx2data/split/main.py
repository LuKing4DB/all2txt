"""
使用正则表达式分割TXT文件脚本
给定一个文件路径和正则表达式，在匹配的位置分割文件
输出文件命名为：0.txt, 1.txt, 2.txt 等（从0开始自增）
"""

import argparse
import sys
from pathlib import Path

# 添加src/split目录到路径，以便导入lib模块
sys.path.insert(0, str(Path(__file__).parent))
from lib.regex_splitter import split_by_regex


def main():
    parser = argparse.ArgumentParser(
        description='使用正则表达式分割TXT文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Linux/Mac/Cmd (使用双引号，需要转义)
  python src/split/main.py data/1/sub/1.txt -p "^第([一二三四五六七八九十\\d]+)章"
  python src/split/main.py data/1/sub/1.txt -p "^\\d+\\.招标" -o output
  
  # PowerShell (推荐使用单引号，避免转义问题)
  python src/split/main.py data/1/sub/1.txt -p '^第([一二三四五六七八九十\d]+)章'
  python src/split/main.py data/1/sub/1.txt -p '^\d+\.招标' -o output
  
  # PowerShell (使用双引号时，\d 在字符类中建议改为 0-9)
  python src/split/main.py data/1/sub/1.txt -p "^第([一二三四五六七八九十0-9]+)章"
  
  # 禁用序号校验
  python src/split/main.py data/1/sub/1.txt -p "^\\d+\\.(?!\\d)" -n
        """
    )
    
    parser.add_argument(
        'file_path',
        type=str,
        help='输入文件路径，例如 data/1/sub/1.txt'
    )
    
    parser.add_argument(
        '-p', '--pattern',
        type=str,
        required=True,
        help='正则表达式模式，用于匹配分割点'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出目录，如果未指定则在输入文件同级目录下创建 文件名_split 文件夹'
    )
    
    parser.add_argument(
        '-n', '--no-validate',
        action='store_true',
        help='禁用序号自增校验（默认启用）。启用时会验证匹配的序号是否按顺序递增（例如：1, 2, 3, 4...）'
    )
    
    args = parser.parse_args()
    
    split_by_regex(args.file_path, args.pattern, args.output, validate_sequence=not args.no_validate)


if __name__ == '__main__':
    main()

