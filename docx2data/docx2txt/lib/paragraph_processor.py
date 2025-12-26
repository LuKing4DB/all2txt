"""
段落处理模块
提供段落文本提取和处理等功能
"""

import re
import sys
from pathlib import Path
from docx.oxml.ns import qn

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger

from .image_detector import (
    has_image,
    get_image_data_from_paragraph,
    has_stamp_features,
    get_image_info,
    has_image_in_run,
    get_image_data_from_run,
    has_stamp_features_in_run
)

logger = get_logger(__name__)


def is_page_number(text):
    """
    判断文本是否为页码
    
    页码特征：
    - 单行文本
    - 主要是数字或罗马数字，可能包含少量文字（如"第1页"、"Page 1"、"Page I"等）
    - 通常较短（不超过20个字符）
    - 可能包含常见的页码关键词
    
    Args:
        text: 文本内容（可能包含空格，会去除首尾空白）
        
    Returns:
        bool: 如果是页码返回True，否则返回False
    """
    if not text or len(text) > 20:
        return False
    
    # 去除首尾空白（保留中间空格）
    text_clean = text.strip()
    
    # 纯数字（1-9999之间的数字，常见页码范围）
    if re.match(r'^\d{1,4}$', text_clean):
        return True
    
    # 罗马数字模式（匹配常见的罗马数字，支持大小写）
    # 匹配：I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XIV, XV, XVI, XVII, XVIII, XIX, XX 等
    # 使用简化的罗马数字模式，匹配常见的页码范围（一般不超过XXX）
    roman_numeral_pattern = r'^[IVXLCDMivxlcdm]+$'
    if re.match(roman_numeral_pattern, text_clean):
        # 验证是否为有效的罗马数字格式（简单验证：只包含有效的罗马数字字符）
        # 这里不做严格的罗马数字有效性验证，因为页码中的罗马数字通常都是有效的
        if len(text_clean) <= 10:  # 页码中的罗马数字通常不会太长
            return True
    
    # 包含页码关键词的模式（支持阿拉伯数字和罗马数字）
    page_patterns = [
        r'^第\d+页$',  # 第1页
        r'^第\d+页/共\d+页$',  # 第1页/共10页
        r'^第[IVXLCDMivxlcdm]+页$',  # 第I页
        r'^Page\s*\d+$',  # Page 1
        r'^Page\s*[IVXLCDMivxlcdm]+$',  # Page I
        r'^P\.?\s*\d+$',  # P.1 或 P 1
        r'^P\.?\s*[IVXLCDMivxlcdm]+$',  # P.I 或 P I
        r'^\d+/\d+$',  # 1/100
        r'^-\s*\d+\s*-$',  # - 1 -
        r'^-\s*[IVXLCDMivxlcdm]+\s*-$',  # - I -
        r'^\d+\s*/\s*\d+$',  # 1 / 100
        r'^[IVXLCDMivxlcdm]+\s*/\s*[IVXLCDMivxlcdm]+$',  # I / X
    ]
    
    for pattern in page_patterns:
        if re.match(pattern, text_clean, re.IGNORECASE):
            return True
    
    # 检查是否主要是数字（数字占比超过70%）
    digit_count = sum(1 for c in text_clean if c.isdigit())
    if len(text_clean) > 0 and digit_count / len(text_clean) > 0.7:
        # 如果主要是数字且长度较短，可能是页码
        if len(text_clean) <= 10:
            return True
    
    # 检查是否主要是罗马数字字符（罗马数字字符占比超过70%）
    roman_chars = set('IVXLCDMivxlcdm')
    roman_count = sum(1 for c in text_clean if c in roman_chars)
    if len(text_clean) > 0 and roman_count / len(text_clean) > 0.7:
        # 如果主要是罗马数字字符且长度较短，可能是页码
        if len(text_clean) <= 10:
            return True
    
    return False


def split_mismerged_paragraph(p):
    """
    拆分误合并的段落
    
    根据规则拆分：标点符号 + 空格 + 序号
    支持的标点符号（统一考虑中文和英文）：。|.|；|;|！|!|？|?|：|:
    支持数字序号（如1., 1.2, 1.1.1、(1)、（2）、(1.2)、1)、2）、1）等）
    支持中文序号（如一、二、三、第一、第二、（一）、一）等）
    支持附件类型序号（如附件1、附件一、附件A、附件a、附件I、附件II、附1、附一、附A、附I、附录1、附录一、附录A、附录I）等
    注意：空格是必需的，原始文档中应该有空格（如"内容： 1.xxx"、"; 8.xxx"或" 附件1"），后处理时空格被去除了
    
    Args:
        p: 段落文本（原始文本，包含空格）
        
    Returns:
        拆分后的段落列表（保留空格，只去除首尾空白）
    """
    # 匹配模式：标点符号 + 空格 + 序号（数字序号或中文序号）
    # 支持的标点符号（统一考虑中文和英文）：
    #   - 句号：。|\.（英文句号需要转义）
    #   - 分号：；|;
    #   - 感叹号：！|!
    #   - 问号：？|\?（英文问号需要转义）
    #   - 冒号：：|:（常见于"内容： 1.xxx"这种格式）
    # 注意：空格是必需的（\s+），原始文档中应该有空格，后处理时空格被去除了
    # 数字序号格式：
    #   - 1. （单个数字加点）、1.2 （数字.数字）、1.1.1 （多级编号）等
    #   - (1)、(2)、(1.2)、(1.1.1) 等（全括号，支持英文和中文括号，支持纯数字和带点号）
    #   - 1)、2)、1.2)、1.1.1) 等（右括号，支持英文和中文括号，支持纯数字和带点号）
    # 中文序号格式：
    #   - 一、二、三、四、五、六、七、八、九、十、十一、十二...（带顿号）
    #   - 第一、第二、第三...（带"第"字和顿号）
    #   - （一）、（二）、（三）...（带括号和顿号）
    #   - 一）、二）、三）...（带右括号和顿号）
    #   - 第一章、第二章...（带"第"字、"章"字和顿号）
    #   - 第一节、第二节...（带"第"字、"节"字和顿号）
    # 附件类型序号格式：
    #   - 附件1、附件2、附件1.2 等（附件+数字序号）
    #   - 附件一、附件二 等（附件+中文序号）
    #   - 附件A、附件a、附件B、附件b 等（附件+字母，大小写都支持）
    #   - 附件I、附件II、附件III、附件i、附件ii 等（附件+罗马数字，大小写都支持）
    #   - 附1、附2、附一、附二、附A、附a、附I、附II 等（附+序号）
    #   - 附录1、附录2、附录一、附录二、附录A、附录a、附录I、附录II 等（附录+序号）
    
    # 中文数字：一、二、三、四、五、六、七、八、九、十、十一、十二、十三...（支持到百、千）
    chinese_num = r"[一二三四五六七八九十百千万]+"
    
    # 数字序号基础模式：
    #   - 带点号：\d+\.(?:\.\d+)* （如 1.、1.2、1.1.1）
    #   - 纯数字：\d+ （如 1、2、3）
    digital_base_with_dot = r"\d+\.(?:\.\d+)*"  # 带点号的格式
    digital_base_pure = r"\d+"  # 纯数字格式
    
    # 数字序号模式（支持多种格式）：
    #   1. 1.、1.2、1.1.1 等（点号格式）
    #   2. (1)、(2)、(1.2)、(1.1.1) 等（全括号，英文括号，支持纯数字和带点号）
    #   3. （1）、（2）、（1.2）、（1.1.1） 等（全括号，中文括号，支持纯数字和带点号）
    #   4. 1)、2)、1.2)、1.1.1) 等（右括号，英文括号，支持纯数字和带点号）
    #   5. 1）、2）、1.2）、1.1.1） 等（右括号，中文括号，支持纯数字和带点号）
    digital_patterns = [
        digital_base_with_dot,  # 1.、1.2、1.1.1 等（点号格式）
        rf"\({digital_base_pure}\)",  # (1)、(2) 等（英文括号，纯数字）
        rf"（{digital_base_pure}）",  # （1）、（2） 等（中文括号，纯数字）
        rf"\({digital_base_with_dot}\)",  # (1.2)、(1.1.1) 等（英文括号，带点号）
        rf"（{digital_base_with_dot}）",  # （1.2）、（1.1.1） 等（中文括号，带点号）
        rf"{digital_base_pure}\)",  # 1)、2) 等（英文右括号，纯数字）
        rf"{digital_base_pure}）",  # 1）、2） 等（中文右括号，纯数字）
        rf"{digital_base_with_dot}\)",  # 1.2)、1.1.1) 等（英文右括号，带点号）
        rf"{digital_base_with_dot}）",  # 1.2）、1.1.1） 等（中文右括号，带点号）
    ]
    
    # 中文序号模式：
    #   1. 一、二、三...（纯中文数字+顿号）
    #   2. 第一、第二...（第+中文数字+顿号）
    #   3. （一）、（二）...（括号+中文数字，后面可能有顿号）
    #   4. 一）、二）...（中文数字+右括号，后面可能有顿号）
    #   5. 第一章、第二章...（第+中文数字+章，后面可能有顿号）
    #   6. 第一节、第二节...（第+中文数字+节，后面可能有顿号）
    # 注意：顿号是可选的，因为有些格式后面可能直接跟内容
    chinese_patterns = [
        rf"{chinese_num}、?",  # 一、二、三...（顿号可选）
        rf"第{chinese_num}、?",  # 第一、第二...（顿号可选）
        rf"（{chinese_num}）、?",  # （一）、（二）...（顿号可选）
        rf"{chinese_num}）、?",  # 一）、二）...（顿号可选）
        rf"第{chinese_num}章、?",  # 第一章、第二章...（顿号可选）
        rf"第{chinese_num}节、?",  # 第一节、第二节...（顿号可选）
    ]
    
    # 附件/附/附录 + 序号模式（支持数字序号、中文序号、字母和罗马数字）
    # 例如：附件1、附件一、附件A、附件a、附件I、附件II、附1、附一、附A、附I、附录1、附录一、附录A、附录I
    attachment_keywords = r"(附件|附|附录)"
    
    # 字母模式（单个字母，大小写都支持）
    letter_pattern = r"[A-Za-z]"
    
    # 罗马数字模式（支持大小写）
    roman_numeral_pattern = r"[IVXLCDMivxlcdm]+"
    
    attachment_patterns = [
        rf"{attachment_keywords}{digital_base_pure}",  # 附件1、附1、附录1 等（纯数字）
        rf"{attachment_keywords}{digital_base_with_dot}",  # 附件1.2、附1.2、附录1.2 等（带点号）
        rf"{attachment_keywords}{chinese_num}",  # 附件一、附一、附录一 等（中文数字）
        rf"{attachment_keywords}{letter_pattern}",  # 附件A、附件a、附A、附a、附录A、附录a 等（字母）
        rf"{attachment_keywords}{roman_numeral_pattern}",  # 附件I、附件II、附I、附II、附录I、附录II 等（罗马数字）
    ]
    
    # 组合所有序号模式
    all_patterns = digital_patterns + chinese_patterns + attachment_patterns
    # 使用非捕获组和交替匹配
    number_pattern = r"(?:" + r"|".join(all_patterns) + r")"
    
    # 完整模式：标点符号 + 空格 + 序号
    # 支持标点符号（统一考虑中文和英文）：
    #   - 句号：。|\.（英文句号需要转义）
    #   - 分号：；|;
    #   - 感叹号：！|!
    #   - 问号：？|\?（英文问号需要转义）
    #   - 冒号：：|:（常见于"内容： 1.xxx"这种格式）
    # 注意：空格是必需的（\s+），原始文档中应该有空格，后处理时空格被去除了
    pattern = r"(。|\.|；|;|！|!|？|\?|：|:)\s+(" + number_pattern + r")"
    
    # 找到所有匹配位置
    matches = list(re.finditer(pattern, p))
    
    if not matches:
        # 没有匹配，返回整个段落（保留空格，只去除首尾空白）
        return [p.strip()] if p.strip() else []
    
    result = []
    start = 0
    
    for match in matches:
        # 获取匹配位置
        match_start = match.start()  # 标点符号位置
        punct_end = match.start(2)  # 序号开始位置（第二个捕获组）
        
        # 提取当前段落（从上一个结束位置到当前标点符号）
        # 包含标点符号本身
        segment = p[start:match_start + 1]  # +1 包含标点符号
        if segment.strip():
            # 保留空格，只去除首尾空白
            result.append(segment.strip())
        
        # 更新起始位置（从序号开始，序号属于下一段）
        start = punct_end
    
    # 添加最后一段
    if start < len(p):
        segment = p[start:]
        if segment.strip():
            # 保留空格，只去除首尾空白
            result.append(segment.strip())
    
    return result if result else [p.strip()] if p.strip() else []


def extract_paragraph_text_raw(doc, element, element_to_para=None):
    """
    从段落XML元素中提取原始文本内容（保留空格）
    如果段落中的run存在分页符，则替换为换行符
    
    Args:
        doc: Document对象
        element: 段落XML元素
        element_to_para: 元素到Paragraph对象的映射字典（可选，用于性能优化）
        
    Returns:
        提取的原始文本字符串（保留空格，仅去除首尾空白）
    """
    # 直接解析XML以检测run中的分页符并替换为换行符
    # 注意：即使有element_to_para映射，也需要手动提取以处理分页符
    text_parts = []
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    
    for run in element.findall(f'.//{ns}r'):
        # 检查run中是否有分页符
        br_elem = run.find(qn('w:br'))
        has_page_break = False
        if br_elem is not None:
            br_type = br_elem.get(qn('w:type'))
            if br_type == 'page':
                has_page_break = True
        
        # 提取run中的文本
        for t in run.findall(f'{ns}t'):
            if t.text:
                text_parts.append(t.text)
        
        # 如果run中有分页符，在文本后添加换行符
        if has_page_break:
            text_parts.append('\n')
    
    text = ''.join(text_parts).strip()
    return text


def extract_paragraph_text(doc, element, element_to_para=None):
    """
    从段落XML元素中提取文本内容（优化版）
    
    Args:
        doc: Document对象
        element: 段落XML元素
        element_to_para: 元素到Paragraph对象的映射字典（可选，用于性能优化）
        
    Returns:
        提取的文本字符串（去除所有空格和制表符）
    """
    # 提取原始文本后去除空格
    raw_text = extract_paragraph_text_raw(doc, element, element_to_para)
    return raw_text.replace(' ', '').replace('\t', '')


def process_paragraph(doc, element, element_to_para=None, filter_stamps=True, element_index=None, debug=False):
    """
    处理段落元素（优化版，支持印章过滤，支持一个段落中多张图片）
    
    Args:
        doc: Document对象
        element: 段落XML元素
        element_to_para: 元素到Paragraph对象的映射字典（可选，用于性能优化）
        filter_stamps: 是否过滤印章图片，默认True
        element_index: 元素在文档中的原始索引
        debug: 是否启用debug模式，默认False
        
    Returns:
        内容项列表，格式为 [('text', text, index), ...] 或 [('image', '{{image_段落索引_run索引}}', index)]
        如果段落包含图片，先返回文本（如果有），然后返回图片标记（如果不是印章）
        如果段落不包含图片，返回文本
    """
    content_items = []
    
    # 先检查是否有图片（快速检查）
    if has_image(element):
        # 优化：先提取原始文本（在处理图片前，避免重复）
        raw_text = extract_paragraph_text_raw(doc, element, element_to_para)
        if raw_text:
            # 使用split_mismerged_paragraph拆分段落（基于原始文本，包含空格）
            split_texts = split_mismerged_paragraph(raw_text)
            for split_text in split_texts:
                if split_text:  # 只添加非空段落
                    # 去除文本中的空格和制表符
                    text_no_space = split_text.replace(' ', '').replace('\t', '')
                    # 检查是否为页码（使用去除空格前的文本进行判断，因为页码检测可能需要空格）
                    if is_page_number(split_text):
                        # 如果是页码，返回页码信息（去除空格）
                        content_items.append(('page_number', text_no_space, element_index))
                    else:
                        # 如果不是页码，正常添加文本（去除空格）
                        content_items.append(('text', text_no_space, element_index))
        
        # 获取段落对象
        if element_to_para is not None:
            para_obj = element_to_para.get(element)
        else:
            para_obj = None
            for para in doc.paragraphs:
                if para._element == element:
                    para_obj = para
                    break
        
        if para_obj is not None:
            # 遍历段落中的所有runs，查找包含图片的run
            for run_index, run in enumerate(para_obj.runs):
                # 检查run中是否有图片
                if has_image_in_run(run):
                    # 获取图片数据
                    image_data = get_image_data_from_run(doc, run)
                    
                    if debug:
                        logger.debug(f"\n[DEBUG] 元素索引 {element_index}, Run索引 {run_index} - 图片处理详情:")
                        if image_data is None:
                            logger.debug(f"  - 无法获取图片数据（可能是链接图片、损坏的图片等）")
                        else:
                            logger.debug(f"  - 成功获取图片数据，大小: {len(image_data[0])} 字节")
                    
                    if image_data is None:
                        # 无法获取图片数据（可能是链接图片、损坏的图片等），跳过
                        if debug:
                            logger.debug(f"  - 处理结果: 无法获取图片数据，跳过{{image_{element_index}_{run_index}}}标记")
                        continue
                    
                    # 能获取图片数据，继续判断是否为印章
                    will_output_image = False
                    if filter_stamps:
                        has_stamp, stamp_features = has_stamp_features_in_run(doc, run, 
                                                     check_square=True, check_red=True,
                                                     aspect_ratio_tolerance=0.03, red_threshold=0.3)
                        if debug:
                            logger.debug(f"  - 印章检测: 是否方形={stamp_features.get('is_square', False)}, "
                                  f"是否红色={stamp_features.get('is_red', False)}, "
                                  f"是否印章={has_stamp}")
                        if has_stamp:
                            # 是印章：不添加{{image_段落索引_run索引}}标记，直接跳过（过滤掉）
                            if debug:
                                logger.debug(f"  - 处理结果: 检测为印章，已过滤")
                            will_output_image = False
                        else:
                            # 不是印章：正常添加{{image_段落索引_run索引}}标记
                            if debug:
                                logger.debug(f"  - 处理结果: 正常图片，添加{{image_{element_index}_{run_index}}}标记")
                            content_items.append(('image', f'{{{{image_{element_index}_{run_index}}}}}', element_index))
                            will_output_image = True
                    else:
                        # 不过滤印章：所有能读取的图片都添加{{image_段落索引_run索引}}标记
                        if debug:
                            logger.debug(f"  - 处理结果: 不过滤印章，添加{{image_{element_index}_{run_index}}}标记")
                        content_items.append(('image', f'{{{{image_{element_index}_{run_index}}}}}', element_index))
                        will_output_image = True
                    
                    # Debug模式：最后明确标记是否输出了{{image_段落索引_run索引}}标记
                    if debug:
                        logger.debug(f"  - 最终输出{{image_{element_index}_{run_index}}}标记: {'是' if will_output_image else '否'}")
    else:
        # 普通段落，提取原始文本
        raw_text = extract_paragraph_text_raw(doc, element, element_to_para)
        if raw_text:  # 只添加非空段落
            # 使用split_mismerged_paragraph拆分段落（基于原始文本，包含空格）
            split_texts = split_mismerged_paragraph(raw_text)
            for split_text in split_texts:
                if split_text:  # 只添加非空段落
                    # 去除文本中的空格和制表符
                    text_no_space = split_text.replace(' ', '').replace('\t', '')
                    # 检查是否为页码（使用去除空格前的文本进行判断，因为页码检测可能需要空格）
                    if is_page_number(split_text):
                        # 如果是页码，返回页码信息（去除空格）
                        content_items.append(('page_number', text_no_space, element_index))
                    else:
                        # 如果不是页码，正常添加文本（去除空格）
                        content_items.append(('text', text_no_space, element_index))
    
    return content_items

