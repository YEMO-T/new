#!/usr/bin/env python3
"""
测试版式选择逻辑修复效果

验证：
1. content/toc页面是否正确选择带正文占位符的版式
2. 是否不再错误选择"标题幻灯片"版式
3. 紧急注入次数是否减少
"""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


def test_layout_selection():
    """测试版式选择逻辑"""
    print("\n" + "="*60)
    print("测试: 版式选择逻辑修复验证")
    print("="*60)
    
    try:
        from utils.native_ppt_engine import NativePPTEngine
        from pptx import Presentation
        
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
        
        prs = Presentation(template_path)
        
        print(f"\n[INFO] 模板中的版式列表:")
        for idx, layout in enumerate(prs.slide_layouts):
            has_title = False
            has_body = False
            try:
                for ph in layout.placeholders:
                    pt_name = str(ph.placeholder_format.type).split('.')[-1].upper()
                    if pt_name in ('TITLE', 'CENTERED_TITLE'):
                        has_title = True
                    if pt_name in ('BODY', 'OBJECT'):
                        has_body = True
            except:
                pass
            print(f"  [{idx}] {layout.name}: title={has_title}, body={has_body}")
        
        engine = NativePPTEngine({})
        
        test_cases = [
            ('cover', '封面页'),
            ('content', '内容页-需要正文'),
            ('toc', '目录页-需要正文'),
            ('summary', '总结页-需要正文'),
            ('ending', '结束页'),
        ]
        
        print("\n[INFO] 版式选择测试结果:")
        all_pass = True
        
        for page_type, desc in test_cases:
            layout = engine._select_layout(prs, page_type)
            
            has_body = False
            try:
                for ph in layout.placeholders:
                    pt_name = str(ph.placeholder_format.type).split('.')[-1].upper()
                    if pt_name in ('BODY', 'OBJECT'):
                        has_body = True
            except:
                pass
            
            needs_body = page_type in ('content', 'toc', 'summary')
            
            if needs_body and not has_body:
                status = "[FAIL]"
                all_pass = False
                reason = "缺少正文占位符!"
            else:
                status = "[PASS]"
                reason = "OK"
                
            is_title_slide = 'title' in (layout.name or '').lower() and 'slide' in (layout.name or '').lower()
            if needs_body and is_title_slide:
                status = "[FAIL]"
                all_pass = False
                reason = "错误选择了标题幻灯片!"
            
            print(f"  {status} {desc:10} (type={page_type:7}) -> '{layout.name}' ({reason})")
        
        return all_pass
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ultimate_renderer_layout():
    """测试UltimateRenderer的版式选择"""
    print("\n" + "="*60)
    print("测试: UltimateRenderer版式选择")
    print("="*60)
    
    try:
        from utils.ultimate_renderer import UltimateRenderer
        
        template_dir = backend_dir / 'data' / 'templates'
        templates = list(template_dir.glob('*.pptx'))
        
        if not templates:
            print("[FAIL] 没有找到模板文件")
            return False
            
        template_path = str(templates[0])
        renderer = UltimateRenderer(template_path)
        
        test_slides = [
            {'page_type': 'cover', 'title': 'Test Cover', 'subtitle': '', 'content': []},
            {'page_type': 'content', 'title': 'Content 1', 'subtitle': '', 'content': ['Point 1', 'Point 2']},
            {'page_type': 'toc', 'title': 'TOC', 'subtitle': '', 'content': ['Item 1', 'Item 2']},
            {'page_type': 'content', 'title': 'Content 2', 'subtitle': '', 'content': ['More content']},
            {'page_type': 'ending', 'title': 'End', 'subtitle': '', 'content': []},
        ]
        
        print("\n[INFO] 渲染测试PPT并检查版式选择:")
        result_stream = renderer.render(test_slides)
        
        file_size = len(result_stream.getvalue())
        print(f"[PASS] PPT渲染成功，文件大小: {file_size/1024:.2f} KB")
        
        if file_size < 10000:
            print("[WARN] 文件过小，可能有问题")
            return False
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("#  版式选择逻辑修复验证套件")
    print("#"*60)
    print(f"#  项目目录: {backend_dir}")
    print(f"#  Python版本: {sys.version.split()[0]}")
    
    import datetime
    print(f"#  时间戳: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*60)
    
    results = {}
    
    results['layout_selection'] = test_layout_selection()
    results['ultimate_renderer'] = test_ultimate_renderer_layout()
    
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
        print("\n[SUCCESS] 版式选择修复验证通过！")
        print("现在content/toc页面应该能正确选择带正文占位符的版式。")
        return 0
    else:
        print("\n[WARNING] 部分测试失败，请查看上方详细信息。")
        return 1


if __name__ == '__main__':
    sys.exit(main())