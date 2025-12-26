"""
样本提取器模块
用于从文本中提取样本内容
"""


def extract_sample(text: str, max_chars: int = 500) -> str:
    """
    从文本中提取前N个字符作为样本
    
    逻辑：
    1. 默认跳过第一行
    2. 逐行检测第2、3、4行（最多3行）
    3. 如果这些行与第一行全等、全包含或被全包含，则一起跳过
    
    Args:
        text: 原始文本内容
        max_chars: 最大字符数，默认500
        
    Returns:
        提取的样本文本（保留换行符）
    """
    if not text:
        return ""
    
    # 按行分割文本
    lines = text.split('\n')
    
    if len(lines) <= 1:
        # 如果只有一行或没有内容，返回空字符串
        return ""
    
    # 获取第一行内容（用于检测）
    first_line = lines[0].strip()
    
    # 默认跳过第一行，从第二行开始
    skip_count = 1
    
    # 检查第2、3、4行（索引1、2、3）是否包含第一行内容
    # 最多检查3行
    max_check_lines = min(3, len(lines) - 1)
    
    for i in range(1, 1 + max_check_lines):
        if i >= len(lines):
            break
        
        current_line = lines[i].strip()
        
        # 检测全等、全包含或被全包含
        if first_line and current_line:
            # 全等：当前行完全等于第一行
            if current_line == first_line:
                skip_count = i + 1  # 跳过到当前行的下一行
            # 全包含：当前行完全包含第一行的所有内容
            elif first_line in current_line:
                skip_count = i + 1  # 跳过到当前行的下一行
            # 被全包含：第一行完全包含当前行的所有内容
            elif current_line in first_line:
                skip_count = i + 1  # 跳过到当前行的下一行
    
    # 从跳过的行之后开始提取
    if skip_count >= len(lines):
        return ""
    
    # 重新组合剩余的行
    remaining_lines = lines[skip_count:]
    remaining_text = '\n'.join(remaining_lines)
    
    if not remaining_text:
        return ""
    
    # 保留换行符，因为标题格式需要按行分析
    if len(remaining_text) <= max_chars:
        return remaining_text
    
    # 找到最后一个完整行的位置
    sample = remaining_text[:max_chars]
    # 如果截断位置不在行尾，找到最后一个换行符
    last_newline = sample.rfind('\n')
    if last_newline > max_chars * 0.8:  # 如果最后一个换行符在80%之后，使用它
        return remaining_text[:last_newline + 1]
    return sample

