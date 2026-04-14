#!/usr/bin/env python3
"""
PPT生成和下载功能测试脚本

测试内容：
1. UltimateRenderer返回值类型验证
2. PPT文件完整性检查
3. 本地存储回退机制测试
4. 文件下载流程模拟
"""

import os
import sys
import io
import tempfile
from pathlib import Path

# 添加项目路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_ultimate_renderer_return_type():
    """测试1: 验证UltimateRenderer返回值类型"""
    print("\n" + "="*60)
    print("测试1: UltimateRenderer返回值类型验证")
    print("="*60)
    
    try:
        from utils.ultimate_renderer import UltimateRenderer
        
        # 查找可用的模板文件
        template_dir = backend_dir / 'data' / 'templates'
        if not template_dir.exists():
            print(f"[FAIL] 模板目录不存在: {template_dir}")
            return False
        
        templates = list(template_dir.glob('*.pptx'))
        if not templates:
            print("[FAIL] 没有找到模板文件")
            return False
        
        template_path = str(templates[0])
        print(f"[INFO] 使用模板: {template_path}")
        
        # 创建测试数据
        test_slides = [
            {
                'page_type': 'cover',
                'title': 'Test Cover',
                'subtitle': 'This is a test PPT',
                'content': []
            },
            {
                'page_type': 'content',
                'title': 'Content Page 1',
                'content': ['Point 1', 'Point 2', 'Point 3']
            }
        ]
        
        # 调用渲染器
        renderer = UltimateRenderer(template_path)
        result = renderer.render(test_slides)
        
        # 验证返回类型
        print(f"[INFO] 返回类型: {type(result)}")
        print(f"   - 是BytesIO对象: {isinstance(result, io.BytesIO)}")
        
        if isinstance(result, io.BytesIO):
            # 读取bytes数据
            result.seek(0)
            ppt_bytes = result.getvalue()
            
            print(f"[PASS] 可以通过getvalue()获取bytes")
            print(f"   - bytes长度: {len(ppt_bytes)} 字节")
            print(f"   - 文件大小: {len(ppt_bytes)/1024:.2f} KB")
            
            # 验证是否是有效的PPTX文件（检查ZIP头）
            is_valid_pptx = ppt_bytes[:4] == b'PK\x03\x04'
            print(f"   - 有效PPTX文件: {'YES' if is_valid_pptx else 'NO'}")
            
            return True and is_valid_pptx
        else:
            print(f"[FAIL] 返回类型错误，期望io.BytesIO，实际{type(result)}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ppt_file_integrity():
    """测试2: 验证生成的PPT文件完整性"""
    print("\n" + "="*60)
    print("测试2: PPT文件完整性检查")
    print("="*60)
    
    try:
        from utils.ultimate_renderer import UltimateRenderer
        from pptx import Presentation
        
        # 使用上一个测试的模板
        template_dir = backend_dir / 'data' / 'templates'
        templates = list(template_dir.glob('*.pptx'))
        
        if not templates:
            print("[FAIL] 没有可用模板")
            return False
            
        template_path = str(templates[0])
        
        # 生成测试PPT
        test_slides = [
            {
                'page_type': 'cover',
                'title': 'Integrity Test',
                'subtitle': 'Verify file can open normally',
                'content': []
            },
            {
                'page_type': 'content',
                'title': 'Content Page',
                'content': ['Test content', 'For verifying PPT integrity']
            }
        ]
        
        renderer = UltimateRenderer(template_path)
        result_stream = renderer.render(test_slides)
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
            tmp.write(result_stream.getvalue())
            temp_path = tmp.name
        
        print(f"[INFO] 临时文件已创建: {temp_path}")
        
        try:
            # 尝试用python-pptx打开并解析
            prs = Presentation(temp_path)
            
            slide_count = len(prs.slides)
            print(f"[PASS] PPT文件可以正常打开")
            print(f"   - 幻灯片数量: {slide_count}")
            
            # 检查每张幻灯片
            for idx, slide in enumerate(prs.slides):
                shapes_count = len(slide.shapes)
                has_title = any(shape.has_text_frame for shape in slide.shapes if shape.has_text_frame)
                print(f"   - 第{idx+1}页: {shapes_count}个形状, 有标题: {has_title}")
            
            # 检查文件大小
            file_size = os.path.getsize(temp_path)
            print(f"   - 文件大小: {file_size/1024:.2f} KB")
            
            # 最小合理大小检查（至少10KB）
            if file_size < 10240:
                print(f"[WARN] 文件过小，可能不完整")
                return False
            
            print("[PASS] 文件完整性验证通过")
            return True
            
        except Exception as e:
            print(f"[FAIL] 无法打开或解析PPT文件: {e}")
            return False
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                print("[INFO] 已清理临时文件")
                
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_local_storage_fallback():
    """测试3: 测试本地存储回退机制"""
    print("\n" + "="*60)
    print("测试3: 本地存储回退机制")
    print("="*60)
    
    try:
        from repository.supabase_client import upload_ppt_to_public_bucket
        
        # 创建测试数据
        test_data = b'Test PPT data ' * 1000  # ~14KB
        user_id = "test_user_123"
        file_name = "test_ppt.pptx"
        
        print(f"[INFO] 测试数据大小: {len(test_data)/1024:.2f} KB")
        print(f"[INFO] 用户ID: {user_id}")
        print(f"[INFO] 文件名: {file_name}")
        
        # 调用上传函数（应该会尝试云端，失败后回退到本地）
        result = upload_ppt_to_public_bucket(user_id, file_name, test_data)
        
        if not result:
            print("[FAIL] 上传函数返回None")
            return False
        
        print(f"\n[INFO] 上传结果:")
        print(f"   - success: {result.get('success')}")
        print(f"   - bucket: {result.get('bucket')}")
        print(f"   - url: {result.get('url')}")
        print(f"   - is_local: {result.get('is_local', False)}")
        
        # 如果是本地存储，验证文件是否存在
        if result.get('is_local') or result.get('bucket') == 'local':
            local_path = result.get('path')
            if local_path and os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                print(f"\n[PASS] 本地文件验证成功:")
                print(f"   - 路径: {local_path}")
                print(f"   - 大小: {file_size/1024:.2f} KB")
                
                # 验证文件内容
                with open(local_path, 'rb') as f:
                    saved_data = f.read()
                
                if saved_data == test_data:
                    print(f"   - 内容匹配: YES")
                    return True
                else:
                    print(f"   - 内容匹配: NO (原始{len(test_data)}字节 vs 保存{len(saved_data)}字节)")
                    return False
            else:
                print(f"[WARN] 本地文件不存在: {local_path}")
                return False
        else:
            print(f"[PASS] 云端存储成功 (bucket={result.get('bucket')})")
            return True
            
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bytes_conversion():
    """测试4: BytesIO到bytes转换"""
    print("\n" + "="*60)
    print("测试4: BytesIO到bytes转换")
    print("="*60)
    
    try:
        # 模拟UltimateRenderer的返回值
        original_data = b'Fake PPTX content ' * 100
        
        stream = io.BytesIO(original_data)
        stream.write(b'More data')
        stream.seek(0)
        
        print(f"[INFO] 原始数据大小: {len(original_data)} 字节")
        print(f"   BytesIO对象: {type(stream)}")
        
        # 方法1: getvalue() (推荐)
        method1_result = stream.getvalue()
        print(f"\n方法1 - getvalue():")
        print(f"   结果类型: {type(method1_result)}")
        print(f"   大小: {len(method1_result)} 字节")
        print(f"   是否是bytes: {isinstance(method1_result, bytes)}")
        
        # 方法2: read()
        stream.seek(0)
        method2_result = stream.read()
        print(f"\n方法2 - read():")
        print(f"   结果类型: {type(method2_result)}")
        print(f"   大小: {len(method2_result)} 字节")
        print(f"   是否是bytes: {isinstance(method2_result, bytes)}")
        
        # 验证两种方法结果一致
        if method1_result == method2_result == original_data + b'More data':
            print(f"\n[PASS] 转换正确，数据完整")
            return True
        else:
            print(f"\n[FAIL] 数据不一致")
            return False
            
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("#  PPT生成和下载功能测试套件")
    print("#"*60)
    print(f"#  项目目录: {backend_dir}")
    print(f"#  Python版本: {sys.version.split()[0]}")
    
    import datetime
    print(f"#  时间戳: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*60)
    
    results = {}
    
    # 运行测试
    results['return_type'] = test_ultimate_renderer_return_type()
    results['file_integrity'] = test_ppt_file_integrity()
    results['local_storage'] = test_local_storage_fallback()
    results['bytes_conversion'] = test_bytes_conversion()
    
    # 输出总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\n总计: {passed_tests}/{total_tests} 通过")
    
    if all(results.values()):
        print("\n[SUCCESS] 所有测试通过！PPT生成和下载功能正常。")
        return 0
    else:
        print("\n[WARNING] 部分测试失败，请查看上方详细信息。")
        return 1


if __name__ == '__main__':
    sys.exit(main())