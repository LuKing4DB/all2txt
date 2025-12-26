"""
Anti-RAG检索模块MVP测试脚本
"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from retriever.lib.anti_rag_retriever import AntiRAGRetriever
from utils.logger import get_logger

logger = get_logger(__name__)


def test_anti_rag():
    """测试Anti-RAG检索功能"""
    
    print("=" * 80)
    print("Anti-RAG检索模块MVP测试")
    print("=" * 80)
    print()
    
    # 创建检索器
    print("初始化Anti-RAG检索器...")
    retriever = AntiRAGRetriever()
    print("✓ 检索器初始化完成")
    print()
    
    # 测试查询列表
    test_queries = [
        "投标保证金要求是什么？",
        "评标办法是什么？",
        "合同价格如何确定？",
        "什么是天气？",  # 这个应该不需要检索
    ]
    
    # 执行测试
    for i, query in enumerate(test_queries, 1):
        print("=" * 80)
        print(f"测试 {i}/{len(test_queries)}: {query}")
        print("=" * 80)
        print()
        
        try:
            # 执行检索
            result = retriever.retrieve(query, max_results=5)
            
            # 显示结果摘要
            print(f"路由决策: {'需要检索' if result.needs_retrieval else '不需要检索'}")
            print(f"决策推理: {result.reasoning}")
            
            if result.needs_retrieval:
                print(f"找到证据数: {len(result.evidences)}")
                print(f"引用数: {len(result.citations)}")
                
                if result.evidences:
                    print("\n前3个证据摘要:")
                    for j, ev in enumerate(result.evidences[:3], 1):
                        section_text = f"章节: {ev.section} | " if ev.section else ""
                        print(f"  {j}. [{ev.relevance_score:.2f}] {section_text}文件: {ev.file_path}")
                        # 使用 Evidence 的展示方法
                        content_preview = ev.get_display_content(max_length=100)
                        print(f"     内容: {content_preview}")
                        print()
                
                if result.citations:
                    print("\n引用列表:")
                    for j, citation in enumerate(result.citations[:3], 1):
                        print(f"  {j}. {citation.doc_id} - {citation.section_title or citation.file_path}")
            
            print()
            print("-" * 80)
            print()
            
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_anti_rag()

