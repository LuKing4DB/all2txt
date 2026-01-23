"""
从DOCX文件中提取目录（TOC - Table of Contents）的独立脚本
"""

import argparse
import json
import sys
from pathlib import Path

import zipfile
from lxml import etree

# 优先使用相对导入（推荐，作为包安装时使用）
try:
    from ..utils.logger import get_logger
except ImportError:
    # 如果相对导入失败，尝试包绝对导入（作为第三方依赖安装时）
    try:
        from all2txt.utils.logger import get_logger
    except ImportError:
        # 如果包导入也失败，使用路径导入（直接运行脚本时）
        # 添加src目录到路径
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.logger import get_logger

logger = get_logger(__name__)


def extract_toc_from_docx(docx_path, debug=False):
    """
    从DOCX文件中提取目录（TOC）
    
    Args:
        docx_path: DOCX文件路径
        debug: 是否启用调试模式
        
    Returns:
        list: 目录条目列表，每个条目包含 level, text, page 字段
    """
    # step 1: unzip and read document.xml
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml")

    root = etree.fromstring(xml)
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    }

    toc_entries = []
    inside_toc = False
    current_level = None
    found_toc_field = False

    # 先尝试方法1：查找TOC字段标记
    paragraphs = root.xpath(".//w:p", namespaces=ns)
    
    if debug:
        logger.debug(f"  总共找到 {len(paragraphs)} 个段落")
        # 检查是否有TOC字段
        all_instr_texts = []
        for p in paragraphs:
            instr_texts = p.xpath('.//w:instrText', namespaces=ns)
            for it in instr_texts:
                if it.text:
                    all_instr_texts.append(it.text)
        if all_instr_texts:
            logger.debug(f"  找到字段指令文本: {all_instr_texts[:5]}")  # 只显示前5个
        else:
            logger.debug(f"  未找到字段指令文本，可能是静态TOC")
        
        # 检查所有样式（用于调试）
        all_styles = set()
        for p in paragraphs:
            p_styles = p.xpath(".//w:pStyle", namespaces=ns)
            for ps in p_styles:
                style_val = ps.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "")
                if style_val:
                    all_styles.add(style_val)
        if all_styles:
            logger.debug(f"  找到的所有段落样式: {sorted(all_styles)}")
        
        # 检查TOC样式
        toc_styles = [s for s in all_styles if "TOC" in s.upper()]
        if toc_styles:
            logger.debug(f"  找到TOC相关样式: {toc_styles}")
        
        # 检查是否有包含"目录"、"Contents"等关键词的段落
        toc_keywords = []
        for i, p in enumerate(paragraphs[:20]):  # 只检查前20个段落
            texts = p.xpath(".//w:r/w:t/text()", namespaces=ns)
            text_content = "".join(texts).strip() if texts else ""
            if any(keyword in text_content for keyword in ["目录", "Contents", "CONTENTS", "目 录"]):
                toc_keywords.append((i, text_content[:50]))
        if toc_keywords:
            logger.debug(f"  找到可能包含目录标题的段落（前20个段落中）: {toc_keywords}")

    # iterate all paragraphs
    for p in paragraphs:
        # find TOC begin - 检查当前段落或前一个段落
        fld_begin = p.xpath('.//w:fldChar[@w:fldCharType="begin"]', namespaces=ns)
        instr_text = p.xpath('.//w:instrText', namespaces=ns)

        # 方法1：在同一段落中找到begin和instrText
        if fld_begin and instr_text:
            if instr_text[0].text and "TOC" in instr_text[0].text:
                inside_toc = True
                found_toc_field = True
                if debug:
                    logger.debug(f"  找到TOC字段开始（方法1）")
                continue

        # 方法2：字段标记可能分布在多个段落，尝试更宽松的匹配
        # 如果当前段落有instrText包含TOC，也认为找到了
        if instr_text and not inside_toc:
            for it in instr_text:
                if it.text and "TOC" in it.text:
                    # 如果当前段落有begin，或者前一个段落有begin
                    if fld_begin:
                        inside_toc = True
                        found_toc_field = True
                        if debug:
                            logger.debug(f"  找到TOC字段开始（方法2）")
                        break
                    # 检查前几个段落是否有begin标记（字段可能跨多个段落）
                    p_idx = paragraphs.index(p) if p in paragraphs else -1
                    if p_idx > 0:
                        for prev_p in paragraphs[max(0, p_idx-2):p_idx]:
                            prev_begin = prev_p.xpath('.//w:fldChar[@w:fldCharType="begin"]', namespaces=ns)
                            if prev_begin:
                                inside_toc = True
                                found_toc_field = True
                                if debug:
                                    logger.debug(f"  找到TOC字段开始（方法2，从前面段落）")
                                break
                        if inside_toc:
                            break

        # find TOC end
        fld_end = p.xpath('.//w:fldChar[@w:fldCharType="end"]', namespaces=ns)
        if fld_end and inside_toc:
            inside_toc = False
            if debug:
                logger.debug(f"  找到TOC字段结束，已提取 {len(toc_entries)} 个条目")
            break

        # extract content only when inside TOC
        if inside_toc:
            # Determine heading level by style (TOC1 / TOC2 ...)
            p_style = p.xpath(".//w:pStyle", namespaces=ns)
            if p_style:
                style_val = p_style[0].get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
                if style_val and style_val.startswith("TOC"):
                    try:
                        current_level = int(style_val.replace("TOC", ""))
                    except ValueError:
                        current_level = None

            # extract runs
            texts = p.xpath(".//w:r/w:t/text()", namespaces=ns)
            if not texts:
                continue

            # TOC format: text ... page_number
            if len(texts) >= 2:
                page = texts[-1]
                text = "".join(texts[:-1])
            else:
                text = texts[0]
                page = None

            toc_entries.append({
                "level": current_level,
                "text": text.strip(),
                "page": page.strip() if page else None
            })

    # 方法3：如果没找到TOC字段标记，或找到但提取了0个条目，尝试通过TOC样式直接提取（静态TOC）
    if (not found_toc_field or len(toc_entries) == 0) and not toc_entries:
        if debug:
            logger.debug(f"  未找到TOC字段标记，尝试通过TOC样式提取静态TOC...")
        
        for p in paragraphs:
            p_style = p.xpath(".//w:pStyle", namespaces=ns)
            if p_style:
                style_val = p_style[0].get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "")
                # 支持多种TOC样式格式：TOC1, TOC 1, toc1等
                style_upper = style_val.upper()
                if style_upper.startswith("TOC"):
                    try:
                        # 尝试提取数字（支持TOC1, TOC 1等格式）
                        level_str = style_val.replace("TOC", "").replace(" ", "").replace("toc", "")
                        if level_str.isdigit():
                            current_level = int(level_str)
                        else:
                            current_level = None
                    except (ValueError, AttributeError):
                        current_level = None
                    
                    # extract runs
                    texts = p.xpath(".//w:r/w:t/text()", namespaces=ns)
                    if texts:
                        # TOC format: text ... page_number
                        if len(texts) >= 2:
                            page = texts[-1]
                            text = "".join(texts[:-1])
                        else:
                            text = texts[0]
                            page = None
                        
                        toc_entries.append({
                            "level": current_level,
                            "text": text.strip(),
                            "page": page.strip() if page else None
                        })

    # 方法4：如果还没找到，或TOC字段提取失败（提取了0个条目），尝试基于内容模式识别手动目录（智能识别）
    if (not found_toc_field or len(toc_entries) == 0) and not toc_entries:
        if debug:
            logger.debug(f"  未找到TOC样式，尝试基于内容模式识别手动目录...")
        
        # 查找"目录"标题的位置
        toc_start_idx = -1
        for i, p in enumerate(paragraphs[:150]):  # 扩大搜索范围到150段
            texts = p.xpath(".//w:r/w:t/text()", namespaces=ns)
            text_content = "".join(texts).strip() if texts else ""
            # 支持更多目录标题格式：目录、目 录、目  录等（包含空格）
            if text_content and ("目录" in text_content or "Contents" in text_content or "CONTENTS" in text_content):
                # 检查是否确实是目录标题（去除空格后只包含目录相关文字）
                cleaned = text_content.replace(' ', '').replace('　', '').replace('\t', '')
                if cleaned == "目录" or cleaned == "Contents" or cleaned == "CONTENTS" or cleaned.startswith("目录"):
                    toc_start_idx = i + 1  # 从下一段开始
                    if debug:
                        logger.debug(f"  找到目录标题在第 {i} 段（{repr(text_content)}），从第 {toc_start_idx} 段开始提取...")
                    break
        
        # 如果还没找到，尝试直接搜索目录条目格式（如"第一章"、"第二章"等）
        if toc_start_idx < 0:
            if debug:
                logger.debug(f"  未找到目录标题，尝试直接搜索目录条目格式...")
            import re
            for i, p in enumerate(paragraphs[:200]):
                texts = p.xpath(".//w:r/w:t/text()", namespaces=ns)
                text_content = "".join(texts).strip() if texts else ""
                # 检查是否是目录条目格式：第X章 + 文本 + 页码
                if text_content and (re.match(r'^第[一二三四五六七八九十\d]+章.*?\d+', text_content) or \
                    re.match(r'^第[一二三四五六七八九十\d]+[卷章].*?\d+', text_content) or \
                    re.match(r'^\d+\.\s*[^.]+\d+$', text_content)):
                    # 找到可能的目录条目，从这一条开始
                    # 但往前找一下，看是否有"目录"标题
                    for j in range(max(0, i-5), i):
                        prev_texts = paragraphs[j].xpath(".//w:r/w:t/text()", namespaces=ns)
                        prev_content = "".join(prev_texts).strip() if prev_texts else ""
                        if prev_content and "目录" in prev_content:
                            toc_start_idx = j + 1
                            if debug:
                                logger.debug(f"  找到目录标题在第 {j} 段（{repr(prev_content)}），从第 {toc_start_idx} 段开始提取...")
                            break
                    
                    # 如果没找到标题，就从第一条目录条目开始
                    if toc_start_idx < 0:
                        toc_start_idx = i
                        if debug:
                            logger.debug(f"  未找到目录标题，但找到目录条目在第 {i} 段（{text_content[:50]}），从此段开始提取...")
                    break
        
        # 如果找到目录标题或条目，尝试提取后续段落
        if toc_start_idx >= 0:
            import re
            # 目录通常有特定的模式：标题...页码 或 标题 页码
            # 页码通常是数字，可能有点线连接符（..或...）
            
            # 连续不符合目录模式的段落计数
            consecutive_non_toc = 0
            max_consecutive_non_toc = 10  # 连续10个段落都不像目录才停止
            
            for i in range(toc_start_idx, min(toc_start_idx + 600, len(paragraphs))):  # 增加到600段，确保覆盖所有目录
                p = paragraphs[i]
                texts = p.xpath(".//w:r/w:t/text()", namespaces=ns)
                if not texts:
                    consecutive_non_toc += 1
                    # 如果连续太多空段落，可能目录结束了
                    if consecutive_non_toc >= max_consecutive_non_toc and len(toc_entries) > 0:
                        if debug:
                            logger.debug(f"  检测到连续 {consecutive_non_toc} 个空段落，目录可能结束在第 {i} 段（已提取 {len(toc_entries)} 条）")
                        break
                    continue
                
                text_content = "".join(texts).strip()
                
                # 检查是否可能是目录条目：
                # 1. 包含数字（可能是页码）
                # 2. 可能有多个空格或点线连接符
                # 3. 不是空行或只有空白字符
                if not text_content or len(text_content) < 2:
                    consecutive_non_toc += 1
                    if consecutive_non_toc >= max_consecutive_non_toc and len(toc_entries) > 0:
                        if debug:
                            logger.debug(f"  检测到连续 {consecutive_non_toc} 个非目录段落，目录可能结束在第 {i} 段（已提取 {len(toc_entries)} 条）")
                        break
                    continue
                
                # 尝试在一行中提取多个目录条目（如：4.15...2254.16...226）
                # 改进的模式：更精确地匹配数字编号开头的目录条目
                # 匹配格式：数字编号 + 非数字文本 + ..或... + 页码 + （可选的下一个编号开始位置）
                
                # 首先尝试匹配所有可能的目录条目模式
                # 模式：数字编号（可选小数点）+ 文本内容（非点线） + 点线连接符（..或...） + 页码数字
                # 关键：页码后面如果紧跟新的数字编号（如4.16），说明有下一个条目
                toc_pattern = r'(\d+(?:\.\d+)*[^\d\.]+?)(?:\.{2,}|\s+)(\d+)(?=(?:\d+(?:\.\d+)*|$))'
                
                # 查找所有匹配项
                all_matches = []
                for match in re.finditer(toc_pattern, text_content):
                    # 检查页码后面是否紧跟新的编号（如：2254.16）
                    page_num = match.group(2)
                    match_end = match.end()
                    # 如果后面紧跟数字开头的新编号，需要调整页码
                    if match_end < len(text_content):
                        after_match = text_content[match_end:]
                        # 检查是否紧跟数字编号（如 4.16）
                        next_num_match = re.match(r'^\d+(?:\.\d+)*', after_match)
                        if next_num_match:
                            # 需要找到真正的页码边界
                            # 页码可能在点线后面，点线可能在页码前
                            # 重新匹配，确保页码完整
                            pass
                    
                    all_matches.append(match)
                
                # 改进的匹配：先找到所有页码位置（..数字 或 ...数字），然后向前查找对应的标题
                # 策略：先找到所有点线+页码的模式，然后检查页码是否完整
                # 页码后面如果紧跟数字编号（如4.16），说明页码可能被截断了
                
                # 先找到所有点线连接符+页码的位置
                page_dot_pattern = r'\.{2,}(\d+)'
                page_positions = []
                for page_match in re.finditer(page_dot_pattern, text_content):
                    page_num = page_match.group(1)
                    page_start = page_match.start()  # 点线开始位置
                    page_end = page_match.end()  # 页码结束位置
                    
                    # 检查页码后面是否紧跟新的数字编号（如：2254.16 中的 4.16）
                    # 如果是，说明页码不完整，需要扩展页码
                    after_page = text_content[page_end:]
                    if after_page:
                        # 检查是否紧跟数字（可能是新编号，也可能是页码的一部分）
                        next_char_match = re.match(r'^(\d+)', after_page)
                        if next_char_match:
                            # 检查这个数字是否是新编号的一部分（如 4.16）
                            # 如果后面跟着小数点，说明是新编号，页码就到此为止
                            # 如果后面跟着非数字非小数点，说明可能是页码的一部分（但不太可能）
                            # 最可能的情况：2254.16，页码应该是225，4.16是新编号
                            # 但有时也可能是：2254，页码是2254，后面没有新编号
                            # 我们需要判断：如果数字后面有小数点，肯定是新编号
                            if len(after_page) > len(next_char_match.group(1)) and after_page[len(next_char_match.group(1))] == '.':
                                # 小数点后还有数字，说明是新编号（如 4.16）
                                # 页码就到此为止，不需要扩展
                                pass
                            # 否则页码就是完整的
                    
                    page_positions.append({
                        'dot_start': page_start,
                        'page_num': page_num,
                        'page_end': page_end
                    })
                
                # 如果找到多个页码，说明一行中有多个目录条目
                if len(page_positions) > 1 or (len(page_positions) == 1 and len(text_content) > 50):
                    # 从后向前处理，这样更容易确定边界
                    for idx, pos_info in enumerate(page_positions):
                        dot_start = pos_info['dot_start']
                        page_num = pos_info['page_num']
                        page_end = pos_info['page_end']
                        
                        # 确定标题的开始位置
                        prev_end = page_positions[idx - 1]['page_end'] if idx > 0 else 0
                        title_start = prev_end
                        title_end = dot_start
                        
                        # 提取标题文本
                        title_text = text_content[title_start:title_end].strip()
                        
                        # 清理标题（移除可能的点线残留）
                        title_text = re.sub(r'\.{2,}$', '', title_text).strip()
                        
                        # 尝试推断层级
                        level_match = re.match(r'^(\d+(?:\.\d+)*)', title_text)
                        if level_match:
                            level_str = level_match.group(1)
                            current_level = len(level_str.split('.'))
                        else:
                            current_level = None
                        
                        if title_text:
                            toc_entries.append({
                                "level": current_level,
                                "text": title_text,
                                "page": page_num
                            })
                            consecutive_non_toc = 0
                    
                    # 如果成功提取了多个条目，继续下一段
                    if page_positions:
                        continue
                
                # 如果只有单个页码，尝试用原有模式匹配
                improved_pattern = r'(\d+(?:\.\d+)*[^\d]+?)(?:\.{2,}|\s+)(\d+)(?=(?:\d+(?:\.\d+)*|[\u4e00-\u9fff]|$))'
                matches = list(re.finditer(improved_pattern, text_content))
                
                # 如果一行中有多个目录条目，或者单个条目后面还有其他内容
                if len(matches) > 1 or (len(matches) == 1 and len(matches[0].group(0)) < len(text_content) * 0.9):
                    # 提取所有匹配的条目
                    for match in matches:
                        text = match.group(1).strip()
                        page = match.group(2).strip()
                        
                        # 清理文本（移除可能的点线残留）
                        text = re.sub(r'\.{2,}$', '', text).strip()
                        
                        # 尝试推断层级
                        level_match = re.match(r'^(\d+(?:\.\d+)*)', text)
                        if level_match:
                            level_str = level_match.group(1)
                            current_level = len(level_str.split('.'))
                        else:
                            current_level = None
                        
                        if text:
                            toc_entries.append({
                                "level": current_level,
                                "text": text,
                                "page": page
                            })
                            consecutive_non_toc = 0  # 重置计数
                    
                    # 如果匹配成功，继续下一段
                    if matches:
                        continue
                
                # 单行单个目录条目的处理（原有逻辑，但改进页码识别）
                # 支持 ..数字 和 ...数字 格式，也支持空格+数字格式（如"十、其他材料  319"）
                # 优先级：点线格式 > 空格+数字 > 末尾数字
                page_match = None
                # 先尝试点线格式
                page_match = re.search(r'\.{2,}(\d+)\s*$', text_content)
                if not page_match:
                    # 再尝试空格+数字格式（至少一个空格，然后是数字）
                    page_match = re.search(r'\s+(\d+)\s*$', text_content)
                if not page_match:
                    # 最后尝试末尾直接数字格式（文本后直接跟数字，如"第一章 招标公告（代投标邀请）1"）
                    # 但要确保不是编号的一部分，检查前面是否有中文字符
                    match = re.search(r'([^\d\s])(\d+)\s*$', text_content)
                    if match:
                        before_char = match.group(1)
                        page_num = match.group(2)
                        # 如果前面字符是中文、括号、点线等，且页码合理（1-10000），可能是页码
                        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', before_char))
                        is_special = before_char in ['）', ')', '、', '。', '.', '…', '…']
                        if (is_chinese or is_special) and page_num.isdigit() and 1 <= int(page_num) <= 10000:
                            # 创建一个匹配对象，页码在第二个组
                            page_match = match
                    
                    # 如果还是没找到，尝试更宽松的匹配：末尾数字（至少1位）
                    if not page_match:
                        match = re.search(r'(\d+)\s*$', text_content)
                        if match:
                            page_num = match.group(1)
                            before_num = text_content[:match.start(1)]
                            # 检查前面是否有中文字符或长度大于2，可能是页码
                            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', before_num))
                            if has_chinese and len(before_num) > 2 and page_num.isdigit() and 1 <= int(page_num) <= 10000:
                                page_match = match
                
                has_page = bool(page_match)
                
                # 提取页码（如果找到）
                if page_match:
                    if page_match.lastindex >= 2:
                        # 页码在第二个组
                        page = page_match.group(2)
                    elif page_match.lastindex >= 1:
                        # 页码在第一个组
                        page = page_match.group(1)
                    else:
                        page = page_match.group(0)
                else:
                    page = None
                
                # 查找点线连接符（..或...）
                has_dots = bool(re.search(r'\.{2,}', text_content))
                
                # 检查是否是中文编号格式（一、二、三...十等，如"十、其他材料"）
                chinese_num_pattern = r'^[一二三四五六七八九十]+、'
                has_chinese_num = bool(re.match(chinese_num_pattern, text_content))
                
                # 如果包含页码，或者看起来像目录条目，或者有中文编号
                if has_page or has_dots or has_chinese_num:
                    consecutive_non_toc = 0  # 重置计数
                    
                    # 尝试提取标题和页码
                    if has_page and page:
                        # 移除页码部分，保留标题（支持多种格式）
                        # 支持：..数字、...数字、空格+数字、直接数字
                        text = re.sub(r'\s*\.{2,}\d+\s*$|\s+\d+\s*$|\d+\s*$', '', text_content).strip()
                    else:
                        # 如果没有明确的页码，可能是标题行
                        text = text_content
                        page = None
                    
                    # 尝试推断层级（通过缩进或数字编号）
                    # 检查开头是否有数字编号（如1.1, 1.1.1等）
                    level_match = re.match(r'^(\d+(?:\.\d+)*)', text)
                    if level_match:
                        # 根据编号层级推断level
                        level_str = level_match.group(1)
                        current_level = len(level_str.split('.'))
                    elif has_chinese_num:
                        # 中文编号也视为一个层级
                        current_level = 1
                    else:
                        current_level = None
                    
                    # 如果文本不为空，添加到目录
                    if text:
                        toc_entries.append({
                            "level": current_level,
                            "text": text.strip(),
                            "page": page.strip() if page else None
                        })
                        
                        # 通用方法：检测目录结束
                        # 在提取条目后，检查下一个有效段落是否是重复的章节标题
                        # 如果遇到重复的"第一章"（已在目录中出现过），说明正文开始了，目录应该结束
                        should_stop = False
                        # 检查后续段落（跳过空段落），查找是否有重复章节标题
                        for j in range(i + 1, min(i + 10, len(paragraphs))):
                            next_p = paragraphs[j]
                            next_texts = next_p.xpath(".//w:r/w:t/text()", namespaces=ns)
                            next_content = "".join(next_texts).strip() if next_texts else ""
                            
                            if not next_content:
                                continue
                            
                            # 关键检测：如果遇到重复的章节标题（如"第一章"），且已在目录中出现过，说明正文开始了
                            if re.match(r'^第[一二三四五六七八九十\d]+章', next_content):
                                chapter_match = re.match(r'^(第[一二三四五六七八九十\d]+章)', next_content)
                                if chapter_match:
                                    chapter_title = chapter_match.group(1)
                                    # 检查目录中是否已经有这个章节
                                    if any(chapter_title in entry.get('text', '') for entry in toc_entries):
                                        should_stop = True
                                        if debug:
                                            logger.debug(f"  检测到重复章节标题在第 {j} 段（{next_content[:50]}），已在目录中出现过，目录结束")
                                        break
                            
                            # 如果后续段落看起来像目录条目（有页码），继续提取
                            # 检查是否有页码
                            next_has_page = bool(re.search(r'\.{2,}\d+\s*$|\s+\d+\s*$', next_content))
                            if not next_has_page:
                                # 检查是否是直接数字格式
                                match = re.search(r'([^\d\s])(\d+)\s*$', next_content)
                                if match:
                                    before_char = match.group(1)
                                    page_num = match.group(2)
                                    is_chinese = bool(re.search(r'[\u4e00-\u9fff]', before_char))
                                    is_special = before_char in ['）', ')', '、', '。', '.', '…', '…']
                                    if (is_chinese or is_special) and page_num.isdigit() and 1 <= int(page_num) <= 10000:
                                        next_has_page = True
                            
                            # 如果后续有目录条目，说明还不是正文开始，跳出检查循环，继续提取
                            if next_has_page:
                                break
                        
                        # 如果检测到重复章节标题，结束提取
                        if should_stop:
                            break
                else:
                    # 检查是否可能是非目录内容（如正文开始）
                    # 如果文本很长且没有页码，可能不是目录
                    if len(text_content) > 100:
                        consecutive_non_toc += 1
                    elif not any(char.isdigit() for char in text_content):
                        consecutive_non_toc += 1
                    else:
                        consecutive_non_toc = 0  # 包含数字，可能还是目录
                    
                    # 如果连续太多段落不像目录，停止提取
                    if consecutive_non_toc >= max_consecutive_non_toc and len(toc_entries) > 0:
                        if debug:
                            logger.debug(f"  检测到连续 {consecutive_non_toc} 个非目录段落，目录可能结束在第 {i} 段（已提取 {len(toc_entries)} 条）")
                        break

    if debug:
        logger.debug(f"  提取结果: 找到 {len(toc_entries)} 个目录条目")

    return toc_entries


def save_toc_json(toc_entries, output_path):
    """将目录条目保存为JSON格式"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(toc_entries, f, ensure_ascii=False, indent=2)


def save_toc_txt(toc_entries, output_path):
    """将目录条目保存为TXT格式"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in toc_entries:
            level = entry.get('level', '')
            text = entry.get('text', '')
            page = entry.get('page', '')
            
            # 根据层级缩进
            indent = '  ' * (level - 1) if level else ''
            
            if page:
                f.write(f"{indent}{text} ... {page}\n")
            else:
                f.write(f"{indent}{text}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='从DOCX文件中提取目录（TOC - Table of Contents）'
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
        help='输出文件路径（可选，默认在输入文件同目录下生成同名文件，格式根据扩展名自动判断）'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['json', 'txt', 'both'],
        default='both',
        help='输出格式：json（JSON格式）、txt（文本格式）、both（两种格式都输出，默认）'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式，输出详细的提取过程信息'
    )
    
    args = parser.parse_args()
    
    # 检查输入文件
    docx_file = Path(args.docx_path)
    if not docx_file.exists():
        logger.error(f"文件不存在: {args.docx_path}")
        sys.exit(1)
    
    if not docx_file.suffix.lower() == '.docx':
        logger.error(f"不是DOCX文件: {args.docx_path}")
        sys.exit(1)
    
    try:
        # 提取目录
        logger.info(f"正在提取目录: {docx_file.name}...")
        if args.debug:
            logger.debug(f"\n[调试模式]")
        toc_entries = extract_toc_from_docx(args.docx_path, debug=args.debug)
        
        if not toc_entries:
            logger.warning("未找到目录内容")
            sys.exit(0)
        
        # 确定输出路径
        if args.output:
            output_path = Path(args.output)
            # 如果指定了目录，则在目录下生成文件
            if output_path.is_dir() or not output_path.suffix:
                output_dir = output_path if output_path.is_dir() else output_path
                output_dir.mkdir(parents=True, exist_ok=True)
                base_name = docx_file.stem + '_toc'
            else:
                # 如果指定了文件，使用该文件
                output_dir = output_path.parent
                base_name = output_path.stem
        else:
            # 默认在输入文件同目录下生成
            output_dir = docx_file.parent
            base_name = docx_file.stem + '_toc'
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存文件
        saved_files = []
        
        if args.format in ['json', 'both']:
            json_path = output_dir / (base_name + '.json')
            save_toc_json(toc_entries, json_path)
            saved_files.append(json_path)
        
        if args.format in ['txt', 'both']:
            txt_path = output_dir / (base_name + '.txt')
            save_toc_txt(toc_entries, txt_path)
            saved_files.append(txt_path)
        
        # 输出结果
        logger.info(f"\n{'='*60}")
        logger.info(f"目录提取完成")
        logger.info(f"{'='*60}")
        logger.info(f"输入文件: {docx_file}")
        logger.info(f"找到 {len(toc_entries)} 个目录条目\n")
        
        logger.info(f"生成的文件:")
        for file_path in saved_files:
            logger.info(f"  ✓ {file_path.name}")
        
        logger.info(f"\n完整路径:")
        for file_path in saved_files:
            logger.info(f"  {file_path}")
        
        logger.info(f"\n目录预览（前10条）:")
        for i, entry in enumerate(toc_entries[:10], 1):
            level = entry.get('level', '')
            text = entry.get('text', '')
            page = entry.get('page', '')
            indent = '  ' * (level - 1) if level else ''
            if page:
                logger.info(f"  {i}. {indent}{text} ... {page}")
            else:
                logger.info(f"  {i}. {indent}{text}")
        
        if len(toc_entries) > 10:
            logger.info(f"  ... 还有 {len(toc_entries) - 10} 条")
        
        # 打印最后10条
        if len(toc_entries) > 10:
            logger.info(f"\n目录预览（最后10条）:")
            start_idx = max(0, len(toc_entries) - 10)
            for i, entry in enumerate(toc_entries[start_idx:], start_idx + 1):
                level = entry.get('level', '')
                text = entry.get('text', '')
                page = entry.get('page', '')
                indent = '  ' * (level - 1) if level else ''
                if page:
                    logger.info(f"  {i}. {indent}{text} ... {page}")
                else:
                    logger.info(f"  {i}. {indent}{text}")
        
        logger.info(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"处理文件时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

