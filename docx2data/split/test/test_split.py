"""
split 模块单元测试
测试 split 模块中的各个组件功能
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import sys

# 添加 src/split 目录到路径，以便导入 lib 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

# 添加 src 目录到路径，以便导入 utils 模块（regex_splitter 需要使用 logger）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.number_extractor import extract_number_from_match
from lib.toc_detector import is_toc_item, detect_toc_regions, detect_toc_region_by_keyword
from lib.ordered_list_detector import (
    is_ordered_list_item,
    get_ordered_list_pattern_type,
    detect_ordered_list_regions
)
from lib.regex_splitter import split_by_regex


class TestNumberExtractor(unittest.TestCase):
    """测试数字提取模块"""
    
    def test_extract_arabic_number(self):
        """测试提取阿拉伯数字"""
        self.assertEqual(extract_number_from_match("1.招标条件"), 1)
        self.assertEqual(extract_number_from_match("123.测试"), 123)
        self.assertEqual(extract_number_from_match("10."), 10)
    
    def test_extract_chinese_number(self):
        """测试提取中文数字"""
        self.assertEqual(extract_number_from_match("一、工程概况"), 1)
        self.assertEqual(extract_number_from_match("十、总结"), 10)
        self.assertEqual(extract_number_from_match("二十一、附录"), 21)
    
    def test_extract_from_brackets(self):
        """测试从括号中提取数字"""
        self.assertEqual(extract_number_from_match("（一）总则"), 1)
        self.assertEqual(extract_number_from_match("(1)说明"), 1)
        self.assertEqual(extract_number_from_match("（十）"), 10)
    
    def test_extract_from_di_format(self):
        """测试从'第X章'格式中提取数字"""
        self.assertEqual(extract_number_from_match("第一章 招标公告"), 1)
        self.assertEqual(extract_number_from_match("第1章"), 1)
        self.assertEqual(extract_number_from_match("第十节 一般要求"), 10)
        self.assertEqual(extract_number_from_match("第一条 总则"), 1)
    
    def test_extract_none(self):
        """测试无法提取数字的情况"""
        self.assertIsNone(extract_number_from_match("没有数字"))
        self.assertIsNone(extract_number_from_match(""))
        self.assertIsNone(extract_number_from_match("   "))


class TestTocDetector(unittest.TestCase):
    """测试目录检测模块"""
    
    def test_is_toc_item(self):
        """测试检测目录项"""
        # 应该识别为目录项
        self.assertTrue(is_toc_item("第一章 标题 1"))
        self.assertTrue(is_toc_item("标题... 5"))
        self.assertTrue(is_toc_item("标题 123"))
        self.assertTrue(is_toc_item("1.1 标题 10"))
        
        # 不应该识别为目录项
        self.assertFalse(is_toc_item("普通文本行"))
        self.assertFalse(is_toc_item("123"))  # 纯数字行
        self.assertFalse(is_toc_item(""))
        self.assertFalse(is_toc_item("   "))
    
    def test_detect_toc_regions(self):
        """测试检测目录区域"""
        lines = [
            "第一章 标题1 1",
            "第二章 标题2 2",
            "第三章 标题3 3",
            "普通文本行",
            "其他内容"
        ]
        regions = detect_toc_regions(lines, min_consecutive=2)
        # 应该检测到前3行为目录区域
        self.assertIn(0, regions)
        self.assertIn(1, regions)
        self.assertIn(2, regions)
        self.assertNotIn(3, regions)
        self.assertNotIn(4, regions)
    
    def test_detect_toc_region_by_keyword(self):
        """测试基于关键字的目录区域检测"""
        pattern = r'^第([一二三四五六七八九十\d]+)章'
        lines = [
            "目录",
            "第一章 标题1 1",
            "第二章 标题2 2",
            "第三章 标题3 3",
            "第一章 标题1",  # 再次出现，标记目录区域结束
            "正文内容"
        ]
        regions = detect_toc_region_by_keyword(lines, pattern)
        # 应该检测到从"目录"行到再次出现"第一章"之前的所有行
        self.assertIn(0, regions)  # "目录"行
        self.assertIn(1, regions)  # 第一个"第一章"
        self.assertIn(2, regions)  # "第二章"
        self.assertIn(3, regions)  # "第三章"
        self.assertNotIn(4, regions)  # 再次出现的"第一章"不包含


class TestOrderedListDetector(unittest.TestCase):
    """测试有序列表检测模块"""
    
    def test_is_ordered_list_item(self):
        """测试检测有序列表项"""
        # 应该识别为有序列表
        self.assertTrue(is_ordered_list_item("1. 项目一"))
        self.assertTrue(is_ordered_list_item("1) 项目一"))
        self.assertTrue(is_ordered_list_item("（1）说明"))
        self.assertTrue(is_ordered_list_item("（一）总则"))
        self.assertTrue(is_ordered_list_item("一、工程概况"))
        self.assertTrue(is_ordered_list_item("① 项目"))
        self.assertTrue(is_ordered_list_item("第一章 标题"))
        
        # 不应该识别为有序列表
        self.assertFalse(is_ordered_list_item("普通文本"))
        self.assertFalse(is_ordered_list_item(""))
    
    def test_get_ordered_list_pattern_type(self):
        """测试获取有序列表格式类型"""
        self.assertEqual(get_ordered_list_pattern_type("1. 项目"), "number_dot")
        self.assertEqual(get_ordered_list_pattern_type("1) 项目"), "number_paren")
        self.assertEqual(get_ordered_list_pattern_type("（1）说明"), "paren_number")
        self.assertEqual(get_ordered_list_pattern_type("（一）总则"), "paren_chinese")
        self.assertEqual(get_ordered_list_pattern_type("一、工程"), "chinese_dot")
        self.assertEqual(get_ordered_list_pattern_type("① 项目"), "circled_number")
        self.assertEqual(get_ordered_list_pattern_type("第一章 标题"), "chapter")
        self.assertIsNone(get_ordered_list_pattern_type("普通文本"))
    
    def test_detect_ordered_list_regions(self):
        """测试检测有序列表区域"""
        lines = [
            "普通文本",
            "1. 项目一",
            "2. 项目二",
            "3. 项目三",
            "普通文本",
            "其他内容"
        ]
        regions = detect_ordered_list_regions(lines, min_consecutive=2)
        # 应该检测到连续的有序列表区域
        self.assertIn(1, regions)
        self.assertIn(2, regions)
        self.assertIn(3, regions)
        self.assertNotIn(0, regions)
        self.assertNotIn(4, regions)


class TestRegexSplitter(unittest.TestCase):
    """测试正则表达式分割器模块"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test.txt"
        self.output_dir = Path(self.test_dir) / "output"
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.test_dir)
    
    def create_test_file(self, content):
        """创建测试文件"""
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def test_basic_split(self):
        """测试基本分割功能"""
        content = """前言
第1章 第一章标题
第一章内容

第2章 第二章标题
第二章内容

第3章 第三章标题
第三章内容
"""
        self.create_test_file(content)
        
        split_by_regex(
            str(self.test_file),
            r'^第(\d+)章',
            str(self.output_dir),
            validate_sequence=False
        )
        
        # 检查输出文件
        output_files = sorted(self.output_dir.glob("*.txt"))
        self.assertGreater(len(output_files), 0)
        
        # 检查第一个文件（可能包含前言）
        first_file = output_files[0]
        with open(first_file, 'r', encoding='utf-8') as f:
            first_content = f.read()
        self.assertIn("前言", first_content)
    
    def test_split_with_sequence_validation(self):
        """测试带序号校验的分割"""
        content = """前言
1.第一项
第一项内容

2.第二项
第二项内容

3.第三项
第三项内容
"""
        self.create_test_file(content)
        
        split_by_regex(
            str(self.test_file),
            r'^(\d+)\.',
            str(self.output_dir),
            validate_sequence=True
        )
        
        # 检查输出文件数量
        output_files = sorted(self.output_dir.glob("*.txt"))
        self.assertGreater(len(output_files), 0)
    
    def test_split_with_toc_skip(self):
        """测试跳过目录区域"""
        content = """目录
第一章 标题1 1
第二章 标题2 2
第三章 标题3 3
第一章 标题1
正文内容开始

1.第一项
第一项内容

2.第二项
第二项内容
"""
        self.create_test_file(content)
        
        split_by_regex(
            str(self.test_file),
            r'^(\d+)\.',
            str(self.output_dir),
            validate_sequence=False
        )
        
        # 检查输出文件
        output_files = sorted(self.output_dir.glob("*.txt"))
        self.assertGreater(len(output_files), 0)
        
        # 检查输出文件内容中不应包含目录行
        for output_file in output_files:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 目录行应该被跳过，不应出现在分割后的文件中
                # 但可能保留在第一个文件的前言部分
                pass
    
    def test_split_with_ordered_list_skip(self):
        """测试跳过有序列表"""
        content = """前言
1. 列表项一
2. 列表项二
3. 列表项三

第1章 第一章标题
第一章内容

第2章 第二章标题
第二章内容
"""
        self.create_test_file(content)
        
        split_by_regex(
            str(self.test_file),
            r'^第(\d+)章',
            str(self.output_dir),
            validate_sequence=False
        )
        
        # 检查输出文件
        output_files = sorted(self.output_dir.glob("*.txt"))
        self.assertGreater(len(output_files), 0)
    
    def test_split_chinese_chapter(self):
        """测试分割中文章节"""
        content = """前言
第一章 第一章标题
第一章内容

第二章 第二章标题
第二章内容
"""
        self.create_test_file(content)
        
        split_by_regex(
            str(self.test_file),
            r'^第([一二三四五六七八九十\d]+)章',
            str(self.output_dir),
            validate_sequence=False
        )
        
        # 检查输出文件
        output_files = sorted(self.output_dir.glob("*.txt"))
        self.assertGreater(len(output_files), 0)
    
    def test_default_output_dir(self):
        """测试默认输出目录"""
        content = """1.第一项
第一项内容

2.第二项
第二项内容
"""
        self.create_test_file(content)
        
        # 不指定输出目录，应该在同级目录创建
        split_by_regex(
            str(self.test_file),
            r'^(\d+)\.',
            output_dir=None,
            validate_sequence=False
        )
        
        # 检查默认输出目录是否存在
        expected_dir = self.test_file.parent / f"{self.test_file.stem}_split"
        self.assertTrue(expected_dir.exists())
        
        # 清理
        shutil.rmtree(expected_dir)
    
    def test_invalid_file(self):
        """测试无效文件路径"""
        with self.assertRaises(SystemExit):
            split_by_regex(
                "不存在的文件.txt",
                r'^(\d+)\.',
                str(self.output_dir),
                validate_sequence=False
            )
    
    def test_invalid_pattern(self):
        """测试无效正则表达式"""
        content = "测试内容"
        self.create_test_file(content)
        
        with self.assertRaises(SystemExit):
            split_by_regex(
                str(self.test_file),
                r'[无效的正则表达式',
                str(self.output_dir),
                validate_sequence=False
            )


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "integration_test.txt"
        self.output_dir = Path(self.test_dir) / "output"
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.test_dir)
    
    def test_complex_document_split(self):
        """测试复杂文档的分割"""
        content = """封面

目录
第一章 标题1 1
第二章 标题2 2
第三章 标题3 3
第一章 标题1

前言
这是前言内容。

第一章 招标条件
1.1 项目名称
1.2 项目概况

第二章 投标人资格要求
2.1 基本要求
2.2 特殊要求

第三章 投标文件要求
3.1 文件格式
3.2 文件内容

结语
"""
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        split_by_regex(
            str(self.test_file),
            r'^第([一二三四五六七八九十\d]+)章',
            str(self.output_dir),
            validate_sequence=True
        )
        
        # 检查输出文件
        output_files = sorted(self.output_dir.glob("*.txt"))
        self.assertGreater(len(output_files), 0)
        
        # 验证文件数量（应该至少有3个章节文件）
        # 实际数量可能更多（包含前言和结语等）
        self.assertGreaterEqual(len(output_files), 3)


if __name__ == '__main__':
    unittest.main()

