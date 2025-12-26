"""
运行 split 模块的单元测试
"""

import sys
import unittest
from pathlib import Path

# 添加路径
test_dir = Path(__file__).parent
split_dir = test_dir.parent
src_dir = split_dir.parent

sys.path.insert(0, str(split_dir))  # 用于导入 lib 模块
sys.path.insert(0, str(src_dir))    # 用于导入 utils 模块

if __name__ == '__main__':
    print("=" * 60)
    print("运行 split 模块单元测试")
    print("=" * 60)
    print()
    
    # 加载测试套件
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir), pattern='test_*.py')
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 60)
    if result.wasSuccessful():
        print("✓ 所有测试通过！")
    else:
        print(f"✗ 测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
    print("=" * 60)
    
    # 返回退出码
    sys.exit(0 if result.wasSuccessful() else 1)

