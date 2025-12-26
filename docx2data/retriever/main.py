"""
Anti-RAG检索器主入口
提供命令行接口进行文档检索
"""

import sys
import argparse
import logging
import re
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from retriever.lib.anti_rag_retriever import AntiRAGRetriever
from retriever.lib.formatter import format_result_for_log
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_relevant_snippets(content: str, keywords: list, context_lines: int = 3, max_length: int = 500) -> str:
    """
    从证据内容中提取直接相关的片段，包含少量上下文，保持原文格式
    
    Args:
        content: 证据内容
        keywords: 关键词列表
        context_lines: 每个匹配行前后包含的行数（默认3行）
        max_length: 最大片段长度（字符数，默认500）
        
    Returns:
        提取的相关片段字符串（保持原文换行格式）
    """
    if not keywords or not content:
        # 如果没有关键词，返回前max_length个字符，保持换行
        if len(content) > max_length:
            # 在换行处截断
            truncated = content[:max_length]
            last_newline = truncated.rfind('\n')
            if last_newline > max_length * 0.8:  # 如果最后换行位置不太靠前
                return truncated[:last_newline] + "\n..."
            return truncated + "..."
        return content
    
    # 按行分割，保持换行符信息
    lines = content.split('\n')
    
    if not lines:
        return content[:max_length] + "..." if len(content) > max_length else content
    
    # 找到包含关键词的行索引
    relevant_indices = set()
    for i, line in enumerate(lines):
        for keyword in keywords:
            if keyword in line:
                relevant_indices.add(i)
                break
    
    if not relevant_indices:
        # 如果没有找到匹配的行，返回前max_length个字符，保持换行
        result_lines = []
        total_length = 0
        for line in lines:
            line_with_newline = line + '\n'
            if total_length + len(line_with_newline) > max_length:
                break
            result_lines.append(line)
            total_length += len(line_with_newline)
        result = '\n'.join(result_lines)
        if len(content) > max_length:
            result += "\n..."
        return result
    
    # 收集相关行（包含上下文）
    snippet_indices = set()
    for idx in relevant_indices:
        # 添加上下文范围
        start = max(0, idx - context_lines)
        end = min(len(lines), idx + context_lines + 1)
        snippet_indices.update(range(start, end))
    
    # 按顺序提取行，保持原有换行
    snippet_lines = [lines[i] for i in sorted(snippet_indices)]
    snippet_text = '\n'.join(snippet_lines)
    
    # 如果片段太长，在行边界处截断
    if len(snippet_text) > max_length:
        truncated = snippet_text[:max_length]
        last_newline = truncated.rfind('\n')
        if last_newline > max_length * 0.7:  # 如果最后换行位置不太靠前
            snippet_text = truncated[:last_newline] + "\n..."
        else:
            snippet_text = truncated + "..."
    
    return snippet_text


def format_result(result) -> str:
    """
    格式化检索结果（使用统一格式化工具）
    
    Args:
        result: 检索结果对象
        
    Returns:
        格式化后的字符串
    """
    return format_result_for_log(result)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Anti-RAG检索器 - 基于Anti-RAG范式进行文档检索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 在所有文档中搜索
  python -m retriever.main "投标保证金要求是什么？"
  
  # 在指定文档中搜索
  python -m retriever.main "评标办法" -d 13
  
  # 保存结果到文件
  python -m retriever.main "技术标准要求" -o results.txt
  
  # 显示详细日志
  python -m retriever.main "投标保证金" -v
        """
    )
    
    parser.add_argument(
        "query",
        type=str,
        help="查询内容（自然语言）"
    )
    
    parser.add_argument(
        "-d", "--doc-id",
        type=str,
        default=None,
        help="文档ID（可选）"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="输出文件路径（可选）"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )
    
    parser.add_argument(
        "-m", "--max-results",
        type=int,
        default=200,
        help="最大返回结果数（默认: 200）"
    )
    
    parser.add_argument(
        "-s", "--stage",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="检索阶段: 1=仅原文, 2=原文+分词, 3=全流程(含扩展)，默认3"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("已启用详细日志模式（DEBUG级别）")
    
    try:
        # 创建检索器
        retriever = AntiRAGRetriever()
        
        # 执行检索
        logger.info(f"开始检索: {args.query}")
        result = retriever.retrieve(
            query=args.query,
            max_results=args.max_results,
            doc_id=args.doc_id,
            stage=args.stage
        )
        
        # 格式化结果
        formatted_result = format_result(result)
        
        # 输出结果
        print("\n" + formatted_result)
        
        # 如果指定了输出文件，保存结果
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_result)
            
            logger.info(f"结果已保存到: {output_path}")
        
    except Exception as e:
        logger.error(f"检索失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

