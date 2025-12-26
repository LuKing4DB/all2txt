#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：测试 all2txt 作为库引入时的同步和异步调用

使用方法：
1. 确保已安装依赖: pip install -r requirements.txt
2. 运行测试: python test_library_usage.py
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入 all2txt 库
# 策略：先尝试已安装的包，如果没有 aconvert_document 则从源码补充
try:
    # 先尝试从已安装的包导入
    import all2txt
    
    # 检查是否有 aconvert_document
    if not hasattr(all2txt, 'aconvert_document'):
        print("⚠️  已安装的包版本较旧，缺少 aconvert_document 函数")
        print("   尝试从源码补充导入...")
        try:
            # 从源码补充导入
            from src.main import aconvert_document
            all2txt.aconvert_document = aconvert_document
            print("   ✅ 已从源码补充导入 aconvert_document")
        except ImportError as e:
            print(f"   ❌ 从源码导入失败: {e}")
            print("   建议重新安装包: pip install -e .")
            sys.exit(1)
    else:
        print("ℹ️  使用已安装的包版本")
except ImportError:
    # 如果包未安装，从源码导入
    try:
        from src.main import convert_document, aconvert_document, detect_file_type
        
        # 创建模拟的 all2txt 模块
        class MockAll2txt:
            __version__ = "0.1.0"
            convert_document = convert_document
            aconvert_document = aconvert_document
            detect_file_type = detect_file_type
        
        all2txt = MockAll2txt()
        print("ℹ️  使用源码模式（未安装包）")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请确保已安装依赖: pip install -r requirements.txt")
        sys.exit(1)


def test_sync_convert():
    """测试同步转换"""
    print("=" * 60)
    print("测试1: 同步转换（阻塞）")
    print("=" * 60)
    
    file_path = Path("doc/投标-方案/sz1.pdf")
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        print(f"   当前工作目录: {Path.cwd()}")
        print(f"   请确保在项目根目录运行此脚本")
        return False
    
    print(f"📄 输入文件: {file_path}")
    file_size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"📁 文件大小: {file_size_mb:.2f} MB")
    
    try:
        start_time = time.time()
        
        # 同步转换
        print("⏳ 开始转换...")
        all2txt.convert_document(
            str(file_path),
            output=None,  # 使用默认输出目录
            debug=False,  # 关闭详细日志
            extract_images=False,
            extract_tables=False,
        )
        
        elapsed = time.time() - start_time
        
        # 检查输出文件
        output_dir = file_path.parent / file_path.stem
        text_file = output_dir / "text.txt"
        
        if text_file.exists():
            text_lines = len(text_file.read_text(encoding='utf-8').splitlines())
            print(f"✅ 转换成功！")
            print(f"   耗时: {elapsed:.2f} 秒")
            print(f"   输出目录: {output_dir}")
            print(f"   文本文件: {text_file}")
            print(f"   文本行数: {text_lines}")
            return True
        else:
            print(f"❌ 输出文件不存在: {text_file}")
            return False
            
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e}")
        return False
    except ValueError as e:
        print(f"❌ 文件类型错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_async_convert():
    """测试异步转换"""
    print("\n" + "=" * 60)
    print("测试2: 异步转换（支持 await）")
    print("=" * 60)
    
    file_path = Path("doc/投标-方案/sz1.pdf")
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"📄 输入文件: {file_path}")
    
    try:
        start_time = time.time()
        
        # 异步转换
        print("⏳ 开始转换（异步）...")
        result = await all2txt.aconvert_document(
            str(file_path),
            output=None,  # 使用默认输出目录
            debug=False,
            extract_images=False,
            extract_tables=False,
        )
        
        elapsed = time.time() - start_time
        
        if result['success']:
            print(f"✅ 转换成功！")
            print(f"   耗时: {elapsed:.2f} 秒")
            print(f"   输出目录: {result['output']}")
            
            # 检查输出文件
            output_dir = Path(result['output'])
            text_file = output_dir / "text.txt"
            
            if text_file.exists():
                text_lines = len(text_file.read_text(encoding='utf-8').splitlines())
                print(f"   文本文件: {text_file}")
                print(f"   文本行数: {text_lines}")
                return True
            else:
                print(f"❌ 输出文件不存在: {text_file}")
                return False
        else:
            print(f"❌ 转换失败: {result['error']}")
            return False
            
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e}")
        return False
    except ValueError as e:
        print(f"❌ 文件类型错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_async_concurrent():
    """测试异步并发转换"""
    print("\n" + "=" * 60)
    print("测试3: 异步并发转换（多个任务）")
    print("=" * 60)
    
    file_path = Path("doc/投标-方案/sz1.pdf")
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"📄 使用同一个文件进行并发测试: {file_path}")
    print("   注意：实际场景中应该使用不同的文件")
    
    try:
        start_time = time.time()
        
        # 并发转换（使用同一个文件，但输出到不同目录）
        print("⏳ 启动 3 个并发任务...")
        tasks = [
            all2txt.aconvert_document(
                str(file_path),
                output=f"./test_output/concurrent_{i}",
                debug=False,
            )
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        
        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        
        print(f"✅ 并发转换完成！")
        print(f"   总耗时: {elapsed:.2f} 秒")
        print(f"   成功: {success_count}/{len(results)}")
        print(f"   失败: {failed_count}/{len(results)}")
        
        for i, result in enumerate(results):
            if result['success']:
                print(f"   任务 {i+1}: ✅ {result['output']}")
            else:
                print(f"   任务 {i+1}: ❌ {result['error']}")
        
        return success_count == len(results)
        
    except Exception as e:
        print(f"❌ 并发转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_type_detection():
    """测试文件类型检测"""
    print("\n" + "=" * 60)
    print("测试4: 文件类型检测")
    print("=" * 60)
    
    file_path = Path("doc/投标-方案/sz1.pdf")
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    file_type = all2txt.detect_file_type(str(file_path))
    print(f"📄 文件: {file_path}")
    print(f"   检测类型: {file_type}")
    
    expected_type = "pdf"
    if file_type == expected_type:
        print(f"✅ 类型检测正确")
        return True
    else:
        print(f"❌ 类型检测错误，期望: {expected_type}, 实际: {file_type}")
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("all2txt 库调用测试")
    print("=" * 60)
    print(f"📦 版本: {all2txt.__version__}")
    print(f"📁 工作目录: {Path.cwd()}")
    print()
    
    results = []
    
    # 测试1: 同步转换
    results.append(("同步转换", test_sync_convert()))
    
    # 测试2: 异步转换
    results.append(("异步转换", await test_async_convert()))
    
    # 测试3: 异步并发
    results.append(("异步并发", await test_async_concurrent()))
    
    # 测试4: 文件类型检测
    results.append(("文件类型检测", test_file_type_detection()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
