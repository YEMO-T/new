"""
PPT 模板风格克隆功能 - 集成测试脚本
验证基于模板生成风格一致 PPT 的完整流程
"""

import os
import sys
import io

# 修复 Windows 控制台编码
if sys.stdout:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ppt_template_style_cloner import (
    TemplateStyleCloner,
    SlideContentData,
    PageType,
    create_styled_ppt_from_template,
    render_with_template_style
)


def find_test_template():
    """查找可用的模板文件"""
    # 常见模板位置
    search_paths = [
        "data/templates",
        "../data/templates",
        "../../data/templates",
        ".",
        ".."
    ]
    
    template_extensions = ['.pptx', '.ppt']
    
    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue
        
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in template_extensions):
                    full_path = os.path.join(root, file)
                    print(f"[FOUND] 找到模板: {full_path}")
                    return full_path
    
    return None


def test_basic_cloning():
    """测试基础克隆功能"""
    print("\n" + "=" * 60)
    print("[TEST 1] 基础模板克隆功能")
    print("=" * 60)
    
    template_path = find_test_template()
    if not template_path:
        print("[SKIP] 未找到模板文件，跳过测试")
        return False
    
    try:
        cloner = TemplateStyleCloner(template_path)
        info = cloner.get_template_info()
        
        print(f"\n[INFO] 模板信息:")
        print(f"  路径: {info['template_path']}")
        print(f"  主字体: {info['theme'].get('major_font', 'N/A')}")
        print(f"  强调色: {info['theme'].get('accent1', 'N/A')}")
        print(f"  版式数: {len(info['layouts'])}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_style_clone_and_generate():
    """测试风格克隆和幻灯片生成"""
    print("\n" + "=" * 60)
    print("[TEST 2] 风格克隆与幻灯片生成")
    print("=" * 60)
    
    template_path = find_test_template()
    if not template_path:
        print("[SKIP] 未找到模板文件，跳过测试")
        return False
    
    try:
        cloner = TemplateStyleCloner(template_path)
        
        # 克隆风格
        new_prs = cloner.clone_style_to_new_presentation()
        
        # 添加各种类型的幻灯片
        test_slides = [
            SlideContentData(
                title="封面标题",
                subtitle="这是副标题",
                page_type=PageType.COVER
            ),
            SlideContentData(
                title="目录",
                content=[
                    "1. 项目背景",
                    "2. 技术方案", 
                    "3. 实施计划",
                    "4. 预期成果"
                ],
                page_type=PageType.TOC
            ),
            SlideContentData(
                title="内容页示例",
                content=[
                    "第一个要点：使用 python-pptx 库操作 PPT",
                    "第二个要点：通过 XML 级别复制实现样式继承",
                    "第三个要点：智能版式匹配算法选择最佳布局",
                    "第四个要点：占位符文本替换保持原始格式"
                ],
                page_type=PageType.CONTENT
            ),
            SlideContentData(
                title="总结",
                content=[
                    "✓ 功能一：完整样式克隆",
                    "✓ 功能二：智能版式选择",
                    "✓ 功能三：内容自动填充",
                    "✓ 功能四：零样式干预"
                ],
                page_type=PageType.SUMMARY
            ),
            SlideContentData(
                title="谢谢观看",
                page_type=PageType.ENDING
            ),
        ]
        
        for slide_data in test_slides:
            slide = cloner.add_styled_slide(slide_data)
            print(f"  [OK] 已添加: {slide_data.title} ({slide_data.page_type.value})")
        
        # 生成输出
        output_dir = os.path.dirname(template_path)
        output_path = os.path.join(output_dir, "test_style_output.pptx")
        result = cloner.generate_output(output_path)
        
        print(f"\n[SUCCESS] 生成成功!")
        print(f"  输出文件: {output_path}")
        print(f"  文件大小: {len(result.getvalue()) / 1024:.1f} KB")
        print(f"  幻灯片数: {len(new_prs.slides)}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dict_format_compatibility():
    """测试字典格式兼容性（模拟前端数据）"""
    print("\n" + "=" * 60)
    print("[TEST 3] 字典格式兼容性测试")
    print("=" * 60)
    
    template_path = find_test_template()
    if not template_path:
        print("[SKIP] 未找到模板文件，跳过测试")
        return False
    
    try:
        # 模拟前端发送的数据格式
        slides_data = [
            {
                "title": "字典格式测试",
                "subtitle": "兼容现有系统",
                "page_type": "cover",
                "content": []
            },
            {
                "title": "正文内容",
                "content": [
                    "支持字符串列表格式",
                    "也支持纯字符串格式",
                    "自动转换为列表处理"
                ],
                "page_type": "content"
            },
            {
                "title": "结束页",
                "content": [],
                "page_type": "ending"
            }
        ]
        
        output_dir = os.path.dirname(template_path)
        output_path = os.path.join(output_dir, "test_dict_output.pptx")
        
        result = render_with_template_style(template_path, slides_data, output_path)
        
        print(f"\n[SUCCESS] 字典格式渲染成功!")
        print(f"  输出文件: {output_path}")
        print(f"  文件大小: {len(result.getvalue()) / 1024:.1f} KB")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_layout_selection():
    """测试版式选择逻辑"""
    print("\n" + "=" * 60)
    print("[TEST 4] 版式选择逻辑测试")
    print("=" * 60)
    
    template_path = find_test_template()
    if not template_path:
        print("[SKIP] 未找到模板文件，跳过测试")
        return False
    
    try:
        cloner = TemplateStyleCloner(template_path)
        cloner.clone_style_to_new_presentation()
        
        test_cases = [
            (PageType.COVER, "封面"),
            (PageType.CONTENT, "内容"),
            (PageType.TOC, "目录"),
            (PageType.SUMMARY, "总结"),
            (PageType.ENDING, "结束"),
        ]
        
        print("\n[INFO] 版式选择结果:")
        for page_type, desc in test_cases:
            layout, gene = cloner.select_best_layout(page_type)
            print(f"  {desc}({page_type.value}): {layout.name}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("PPT 模板风格克隆器 - 集成测试套件")
    print("=" * 60)
    
    results = {
        'basic_cloning': test_basic_cloning(),
        'style_generate': test_style_clone_and_generate(),
        'dict_format': test_dict_format_compatibility(),
        'layout_select': test_layout_selection(),
    }
    
    print("\n" + "=" * 60)
    print("[SUMMARY] 测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "[OK]" if result else "[X]"
        print(f"  {symbol} {name}: {status}")
    
    print(f"\n[TOTAL] {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过! 模板风格克隆功能正常 ✓")
        return 0
    else:
        print("\n[WARNING] 部分测试未通过，请检查日志")
        return 1


if __name__ == "__main__":
    exit(main())
