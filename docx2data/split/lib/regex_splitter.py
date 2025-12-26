"""
正则表达式分割器模块
使用正则表达式按行分割TXT文件的核心逻辑
"""

import re
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
# 添加split/lib目录到路径，以便支持直接导入
split_lib_dir = Path(__file__).parent
if str(split_lib_dir) not in sys.path:
    sys.path.insert(0, str(split_lib_dir))

# 尝试相对导入，如果失败则使用绝对导入
try:
    from .number_extractor import extract_number_from_match
    from .toc_detector import detect_toc_region_by_keyword
    from .ordered_list_detector import detect_ordered_list_regions
except ImportError:
    # 如果相对导入失败，使用绝对导入
    from number_extractor import extract_number_from_match
    from toc_detector import detect_toc_region_by_keyword
    from ordered_list_detector import detect_ordered_list_regions

from utils.logger import get_logger

logger = get_logger(__name__)


class RegexSplitter:
    """
    正则表达式分割器类
    使用正则表达式按行分割TXT文件
    """
    
    def __init__(self, file_path: str, pattern: str, output_dir: str = None, validate_sequence: bool = True, create_output_dir: bool = True, detect_title_region: bool = True):
        """
        初始化正则表达式分割器
        
        Args:
            file_path: 输入文件路径，例如 data/1/sub/1.txt
            pattern: 正则表达式模式，用于匹配分割点（^匹配行首）
            output_dir: 输出目录，如果为None则在输入文件同级目录下创建 文件名_split 文件夹
            validate_sequence: 如果为True，验证匹配的序号是否按顺序递增
            create_output_dir: 是否创建输出目录（默认True，如果只是用于提取样本可以设为False）
            detect_title_region: 是否检测标题区域（默认True，在递归的最外层可以设为False）
        """
        self.file_path = file_path
        self.pattern = pattern
        self.output_dir = output_dir
        self.validate_sequence = validate_sequence
        self.detect_title_region = detect_title_region
        
        # 验证文件路径
        self.input_path = Path(file_path)
        if not self.input_path.exists():
            logger.error(f"文件不存在: {file_path}")
            sys.exit(1)
        
        if not self.input_path.is_file():
            logger.error(f"不是文件: {file_path}")
            sys.exit(1)
        
        # 设置输出目录
        file_stem = self.input_path.stem
        if output_dir is None:
            # 默认输出到同级目录下的 文件名_split 文件夹
            self.output_path = self.input_path.parent / f"{file_stem}_split"
        else:
            self.output_path = Path(output_dir)
        
        # 只有在需要时才创建输出目录
        if create_output_dir:
            self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 读取文件内容
        try:
            with open(self.input_path, 'r', encoding='utf-8') as f:
                self.lines = f.readlines()
        except Exception as e:
            logger.error(f"无法读取文件: {e}")
            sys.exit(1)
        
        # 编译正则表达式（使用MULTILINE标志，使^匹配每行开头）
        try:
            self.regex = re.compile(pattern, re.MULTILINE)
        except re.error as e:
            logger.error(f"无效的正则表达式: {e}")
            sys.exit(1)
        
        # 初始化区域属性
        self.title_regions = set()  # 标题区域（第一行及与第一行全等/全包含/被全包含的行）
        self.toc_regions = set()  # 基于关键字的目录区域
        self.ordered_list_regions = set()  # 有序列表区域（排除目录区域后检测）
        self.skip_regions = set()  # 所有需要跳过的区域
        self.skip_reasons = {}  # 跳过原因映射
        
        # 检测区域
        self._detect_regions()
    
    def _detect_regions(self):
        """
        检测标题区域、目录区域和有序列表区域
        先检测标题区域，再检测目录区域，最后检测有序列表区域
        """
        # 第一步：检测标题区域（第一行及与第一行全等/全包含/被全包含的行，最多检测3行）
        # 如果 detect_title_region 为 False，则跳过标题区域检测
        if self.detect_title_region:
            if len(self.lines) > 0:
                first_line = self.lines[0].strip()
                if first_line:
                    # 默认跳过第一行
                    self.title_regions.add(0)
                    
                    # 检测全等、全包含或被全包含，最多检测3行（第2、3、4行）
                    max_check_lines = min(3, len(self.lines) - 1)
                    for i in range(1, 1 + max_check_lines):
                        if i >= len(self.lines):
                            break
                        
                        current_line = self.lines[i].strip()
                        
                        # 检测全等、全包含或被全包含
                        if current_line:
                            # 全等：当前行完全等于第一行
                            if current_line == first_line:
                                self.title_regions.add(i)
                            # 全包含：当前行完全包含第一行的所有内容
                            elif first_line in current_line:
                                self.title_regions.add(i)
                            # 被全包含：第一行完全包含当前行的所有内容
                            elif current_line in first_line:
                                self.title_regions.add(i)
            
            if self.title_regions:
                logger.info(f"检测到标题区域，共 {len(self.title_regions)} 行将被跳过")
        else:
            logger.info("跳过标题区域检测（递归最外层）")
        
        # 第二步：检测基于关键字的目录区域（排除标题区域后检测）
        self.toc_regions = detect_toc_region_by_keyword(self.lines, self.pattern)
        if self.toc_regions:
            logger.info(f"检测到目录区域（基于关键字），共 {len(self.toc_regions)} 行将被跳过")
        
        # 第三步：在排除标题区域和目录区域后，检测剩余文本中的有序列表区域
        exclude_regions = self.title_regions | self.toc_regions
        self.ordered_list_regions = detect_ordered_list_regions(
            self.lines, 
            min_consecutive=2, 
            exclude_toc_regions=exclude_regions
        )
        if self.ordered_list_regions:
            logger.info(f"检测到有序列表区域，共 {len(self.ordered_list_regions)} 行将被跳过")
        
        # 第四步：合并所有需要跳过的区域
        self.skip_regions = self.title_regions | self.toc_regions | self.ordered_list_regions
        
        # 创建跳过原因映射，用于调试日志
        # 注意：一行可能同时属于多个类别，我们按优先级显示（标题区域 > 目录区域 > 有序列表）
        # 先标记有序列表（优先级最低）
        for line_num in self.ordered_list_regions:
            self.skip_reasons[line_num] = "有序列表"
        # 再标记目录区域（优先级中等）
        for line_num in self.toc_regions:
            self.skip_reasons[line_num] = "目录区域"
        # 最后标记标题区域（优先级最高，会覆盖前面的）
        for line_num in self.title_regions:
            self.skip_reasons[line_num] = "标题区域"
    
    def get_sample_text(self, chars: int) -> str:
        """
        获取样例文本，跳过跳过区域（包括标题区域、目录区域和有序列表区域）
        
        Args:
            chars: 需要获取的字符长度
            
        Returns:
            跳过跳过区域后的文本开头指定字符数的内容
        """
        text, _ = self.get_sample_text_with_line_numbers(chars)
        return text
    
    def get_first_line(self) -> tuple[str, int]:
        """
        获取第一行（从目录区域之后开始的第一行）
        
        Returns:
            元组 (第一行内容, 行号)，行号从1开始
        """
        # 确定起始行：从目录区域之后开始
        start_line = 0
        if self.toc_regions:
            # 如果存在目录区域，从目录区域结束后的第一行开始
            start_line = max(self.toc_regions) + 1
        elif self.title_regions:
            # 如果没有目录区域，但有标题区域，从标题区域之后开始
            start_line = max(self.title_regions) + 1
        
        # 如果起始行超出文件范围，返回空
        if start_line >= len(self.lines):
            return '', 0
        
        # 从起始行开始查找第一行（跳过标题区域和有序列表区域）
        for i in range(start_line, len(self.lines)):
            # 如果当前行在跳过区域中（标题区域、有序列表区域），跳过该行
            if i in self.title_regions or i in self.ordered_list_regions:
                continue
            
            line = self.lines[i]
            return line, i + 1
        
        return '', 0
    
    def get_sample_text_with_line_numbers(self, chars: int) -> tuple[str, list[int]]:
        """
        获取样例文本和对应的行号映射，从目录区域之后开始提取
        
        Args:
            chars: 需要获取的字符长度
            
        Returns:
            元组 (文本内容, 行号列表)，行号列表中的每个元素对应文本中每一行的原始文件行号（从1开始）
        """
        if chars <= 0:
            return '', []
        
        if len(self.lines) <= 1:
            return '', []
        
        # 确定起始行：从目录区域之后开始
        start_line = 0
        if self.toc_regions:
            # 如果存在目录区域，从目录区域结束后的第一行开始
            start_line = max(self.toc_regions) + 1
        elif self.title_regions:
            # 如果没有目录区域，但有标题区域，从标题区域之后开始
            start_line = max(self.title_regions) + 1
        
        # 如果起始行超出文件范围，返回空
        if start_line >= len(self.lines):
            return '', []
        
        # 从起始行开始提取样本
        result = []
        line_numbers = []  # 记录每一行对应的原始文件行号（从1开始）
        current_length = 0
        
        for i in range(start_line, len(self.lines)):
            # 如果已经达到或超过目标长度，停止
            if current_length >= chars:
                break
            
            # 如果当前行在跳过区域中（标题区域、有序列表区域），跳过该行
            # 注意：目录区域已经在start_line中处理，这里不再跳过
            if i in self.title_regions or i in self.ordered_list_regions:
                continue
            
            line = self.lines[i]
            
            # 计算当前行的字符数
            line_length = len(line)
            
            # 如果加上当前行会超过目标长度，只取需要的部分
            if current_length + line_length > chars:
                remaining_chars = chars - current_length
                if remaining_chars > 0:
                    result.append(line[:remaining_chars])
                    line_numbers.append(i + 1)  # 原始文件行号（从1开始）
                break
            
            # 添加整行
            result.append(line)
            line_numbers.append(i + 1)  # 原始文件行号（从1开始）
            current_length += line_length
        
        return ''.join(result), line_numbers
    
    def split(self):
        """
        执行文件分割操作
        """
        logger.info(f"正在读取文件: {self.input_path}")
        logger.info(f"使用正则表达式: {self.pattern}")
        logger.info(f"序号校验: {'启用' if self.validate_sequence else '禁用'}")
        logger.info(f"输出目录: {self.output_path}")
        
        # 确保输出目录存在（可能在初始化时没有创建）
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 如果检测到目录区域，单独导出 toc.txt，便于后续使用
        if self.toc_regions:
            toc_lines_sorted = sorted(self.toc_regions)
            toc_content = ''.join(self.lines[i] for i in toc_lines_sorted).rstrip()
            toc_file = self.output_path / "toc.txt"
            try:
                with open(toc_file, 'w', encoding='utf-8') as f:
                    f.write(toc_content)
                logger.info(f"已保存目录区域: {toc_file} (共 {len(toc_lines_sorted)} 行)")
            except Exception as e:
                logger.error(f"无法写入目录文件 {toc_file}: {e}")
        
        # 使用实例属性中的区域信息（已在初始化时检测）
        matching_lines = []
        matched_numbers = []  # 存储匹配的序号，用于校验
        matched_line_info = []  # 存储匹配行的信息（行号、序号、文本），用于处理重复序号
        
        for i, line in enumerate(self.lines):
            # 如果当前行在跳过区域中（包括标题区域、目录区域、有序列表区域），跳过（不作为分割点）
            if i in self.skip_regions:
                continue
            
            # 如果不是目录或列表，再检测是否匹配分割点
            # 去除前导空格后检查是否匹配行首
            # 确保只匹配从行首第一个字符开始的模式
            stripped_line = line.lstrip()
            
            if stripped_line and self.regex.search(stripped_line):
                # 验证匹配位置是否在去除前导空格后的行首（即原行的第一个非空白字符）
                match = self.regex.search(stripped_line)
                if match and match.start() == 0:
                    matched_text = match.group(0)
                    
                    # 如果启用序号校验，提取并验证序号
                    if self.validate_sequence:
                        # 优先从捕获组中提取数字（如果有捕获组）
                        if match.groups():
                            # 使用第一个捕获组的内容
                            captured_text = match.group(1)
                            number = extract_number_from_match(captured_text)
                        else:
                            # 没有捕获组，从整个匹配文本中提取
                            number = extract_number_from_match(matched_text)
                        
                        if number is None:
                            # 无法提取序号，跳过（可能是非数字格式的标题）
                            continue
                        
                        # 检查序号是否按顺序递增
                        if matched_numbers:
                            expected_number = matched_numbers[-1] + 1
                            if number != expected_number:
                                # 如果序号不连续，检查是否与已匹配的序号相同
                                if number in matched_numbers:
                                    # 找到具有相同序号的行
                                    duplicate_idx = matched_numbers.index(number)
                                    duplicate_line_info = matched_line_info[duplicate_idx]
                                    duplicate_line_num = duplicate_line_info['line_num']
                                    
                                    # 优先保留第一个匹配的行（更可能是真正的标题）
                                    logger.warning(f"行 {i+1} 和行 {duplicate_line_num+1} 序号相同（{number}）。保留第一个匹配的行 {duplicate_line_num+1} (文本: {duplicate_line_info['text'].strip()})")
                                    # 跳过当前行的处理
                                    continue
                                else:
                                    # 序号不连续且不重复，跳过这个匹配
                                    logger.warning(f"行 {i+1} 序号不连续。期望: {expected_number}, 实际: {number} (文本: {matched_text.strip()})")
                                    continue
                        
                        matched_numbers.append(number)
                        matched_line_info.append({
                            'line_num': i,
                            'number': number,
                            'text': stripped_line
                        })
                    
                    matching_lines.append(i)
        
        if not matching_lines:
            logger.warning(f"未找到匹配的行（模式: {self.pattern}）")
            # 检查所有行，统计匹配情况
            total_matched = 0
            total_skipped = 0
            matched_but_skipped = []
            skip_reason_count = {"标题区域": 0, "目录区域": 0, "有序列表": 0}
            
            for i, line in enumerate(self.lines):
                stripped = line.lstrip()
                if stripped:
                    match = self.regex.search(stripped)
                    is_match = match is not None and match.start() == 0
                    in_skip = i in self.skip_regions
                    
                    if is_match:
                        total_matched += 1
                        if in_skip:
                            total_skipped += 1
                            reason = self.skip_reasons.get(i, "未知")
                            matched_but_skipped.append((i + 1, stripped[:50], reason))
                            if reason in skip_reason_count:
                                skip_reason_count[reason] += 1
            
            logger.info(f"匹配统计（共 {len(self.lines)} 行）:")
            logger.info(f"  找到 {total_matched} 行匹配正则表达式")
            logger.info(f"  其中 {total_skipped} 行被跳过:")
            logger.info(f"    - 标题区域: {skip_reason_count['标题区域']} 行")
            logger.info(f"    - 目录区域: {skip_reason_count['目录区域']} 行")
            logger.info(f"    - 有序列表: {skip_reason_count['有序列表']} 行")
            
            if matched_but_skipped:
                logger.info(f"  被跳过的匹配行示例（前10行）:")
                for item in matched_but_skipped[:10]:
                    if len(item) == 3:
                        line_num, text, reason = item
                        logger.info(f"    行{line_num}: {text} [跳过原因: {reason}]")
                    else:
                        # 兼容旧格式
                        line_num, text = item
                        reason = self.skip_reasons.get(line_num - 1, "未知")
                        logger.info(f"    行{line_num}: {text} [跳过原因: {reason}]")
                if len(matched_but_skipped) > 10:
                    logger.info(f"    ... (还有 {len(matched_but_skipped) - 10} 行被跳过)")
            
            # 输出前100行作为详细调试信息
            logger.info(f"前100行详细检查:")
            display_count = min(100, len(self.lines))
            for i, line in enumerate(self.lines[:display_count]):
                stripped = line.lstrip()
                if stripped:
                    match = self.regex.search(stripped)
                    is_match = match is not None and match.start() == 0
                    in_skip = i in self.skip_regions
                    skip_reason = self.skip_reasons.get(i, "") if in_skip else ""
                    skip_info = f", 跳过原因: {skip_reason}" if skip_reason else ""
                    logger.info(f"  行{i+1}: {stripped[:50]:50s} [匹配: {is_match}, 跳过: {in_skip}{skip_info}]")
            if len(self.lines) > display_count:
                logger.info(f"  ... (还有 {len(self.lines) - display_count} 行未显示)")
            sys.exit(1)
        
        logger.info(f"找到 {len(matching_lines)} 个匹配行")
        if self.validate_sequence and matched_numbers:
            logger.debug(f"序号序列: {matched_numbers}")
        
        # 分割文件
        file_count = 0
        
        # 处理第一个匹配之前的内容（如果有）
        first_match_line = matching_lines[0]
        if first_match_line > 0:
            # 提取第一个匹配点之前的内容（包括跳过区域）
            # 需求：0.txt 不包含目录区域
            segment_lines = [
                self.lines[i]
                for i in range(first_match_line)
                if i not in self.toc_regions
            ]
            segment_content = ''.join(segment_lines).rstrip()
            # 即使内容为空也保存文件（第一个匹配点之前的内容）
            filename = f"{file_count}.txt"
            output_file = self.output_path / filename
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(segment_content)
                logger.info(f"已保存: {output_file} (行 1-{first_match_line}，第一个匹配点之前的内容，包括跳过区域)")
                file_count += 1
            except Exception as e:
                logger.error(f"无法写入文件 {output_file}: {e}")
        else:
            # 如果第一个匹配就在第一行，则跳过0.txt，直接从1.txt开始命名
            file_count = 1
        
        # 处理每个匹配之间的内容
        for idx in range(len(matching_lines)):
            start_line = matching_lines[idx]
            
            # 确定结束行（下一个匹配的行，或文件末尾）
            if idx + 1 < len(matching_lines):
                end_line = matching_lines[idx + 1]
            else:
                end_line = len(self.lines)
            
            # 提取内容（包含所有跳过区域）
            # 注意：跳过区域只是不作为分割点，但在切分后的文件中应该包含这些内容
            segment_lines = []
            for i in range(start_line, end_line):
                # 包含所有内容，包括跳过区域
                segment_lines.append(self.lines[i])
            segment_content = ''.join(segment_lines).rstrip()
            
            if segment_content:  # 如果内容不为空
                filename = f"{file_count}.txt"
                output_file = self.output_path / filename
                
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(segment_content)
                    logger.info(f"已保存: {output_file} (行 {start_line + 1}-{end_line})")
                    file_count += 1
                except Exception as e:
                    logger.error(f"无法写入文件 {output_file}: {e}")
        
        logger.info(f"\n完成! 共分割为 {file_count} 个文件，保存在: {self.output_path}")


def split_by_regex(file_path: str, pattern: str, output_dir: str = None, validate_sequence: bool = True):
    """
    使用正则表达式按行分割文件（便捷函数，向后兼容）
    
    Args:
        file_path: 输入文件路径，例如 data/1/sub/1.txt
        pattern: 正则表达式模式，用于匹配分割点（^匹配行首）
        output_dir: 输出目录，如果为None则在输入文件同级目录下创建 文件名_split 文件夹
        validate_sequence: 如果为True，验证匹配的序号是否按顺序递增
    """
    splitter = RegexSplitter(file_path, pattern, output_dir, validate_sequence)
    splitter.split()

