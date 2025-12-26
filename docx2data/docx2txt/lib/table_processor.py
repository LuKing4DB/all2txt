"""
表格处理模块
提供表格检测和处理等功能
"""


def process_table(element, element_index=None):
    """
    处理表格元素
    
    Args:
        element: 表格XML元素
        element_index: 元素在文档中的原始索引
        
    Returns:
        内容项列表，格式为 [('table', '{{table_索引}}', index)]
    """
    if element_index is not None:
        return [('table', f'{{{{table_{element_index}}}}}', element_index)]
    else:
        return [('table', '{{table}}', element_index)]

