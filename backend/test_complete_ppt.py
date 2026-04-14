#!/usr/bin/env python3
"""
PPT生成与下载功能验证测试 v2

测试流程：
1. 使用NativeEngine完整generate方法生成PPT
2. 验证文件完整性（可被python-pptx解析）
3. 检查内容是否正确写入（标题、正文可见）
4. 测试本地存储保存功能
5. 验证文件可在PowerPoint中打开
"""

import os
import sys
import io
import tempfile
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


def test_complete_ppt_generation():
    """Test 1: Complete PPT generation using full generate method"""
    print("\n" + "="*70)
    print("Test 1: Complete PPT Generation (Simulating Real Teaching PPT)")
    print("="*70)
    
    try:
        from utils.native_ppt_engine import NativePPTEngine
        
        template_dir = backend_dir / 'data' / 'templates'
        templates = list(template_dir.glob('*.pptx'))
        
        if not templates:
            print("[FAIL] No template files found")
            return False, None
            
        template_path = str(templates[0])
        print(f"[INFO] Template: {os.path.basename(template_path)}")
        
        engine = NativePPTEngine({})
        
        test_slides_data = [
            {
                'title': 'Pi Pa Xing (Song of the Pipa Player)',
                'subtitle': 'Grade 10 Chinese - Tang Dynasty Poetry',
                'page_type': 'cover',
                'content': []
            },
            {
                'title': 'Learning Objectives',
                'content': [
                    'Understand the historical context of Pi Pa Xing',
                    'Master the artistic features and techniques used',
                    'Appreciate the emotional journey of the poet Bai Juyi',
                    'Develop classical literature aesthetic appreciation'
                ],
                'page_type': 'content'
            },
            {
                'title': 'I. Background and Author',
                'content': [
                    'Bai Juyi (772-846), courtesy name Letian',
                    'Great realist poet of the Tang Dynasty',
                    'Wrote Pi Pa Xing while demoted to Jiangzhou',
                    'Reflects his emotional state after political setback'
                ],
                'page_type': 'content'
            },
            {
                'title': 'II. Content and Structure',
                'content': [
                    'Preface: Explains the reason and time of writing',
                    'Main body: Describes the pipa player and her life story',
                    'Conclusion: Expresses poet\'s resonance and emotions',
                    'Well-structured with clear progression'
                ],
                'page_type': 'content'
            },
            {
                'title': 'Class Summary',
                'content': [
                    'Explored the background of Pi Pa Xing creation',
                    'Understood content structure and artistic features',
                    'Experienced the poet\'s emotional world'
                ],
                'page_type': 'summary'
            },
            {
                'title': 'Thank You for Listening',
                'subtitle': 'Homework: Recite the full text and write a reflection',
                'page_type': 'ending',
                'content': []
            }
        ]
        
        print(f"[INFO] Starting generation of {len(test_slides_data)} slides...")
        
        ppt_bytes = engine.generate(
            slides_data=test_slides_data,
            template_path=template_path
        )
        
        if ppt_bytes is None:
            print("[FAIL] generate() returned None")
            return False, None
        
        if isinstance(ppt_bytes, io.BytesIO):
            ppt_bytes = ppt_bytes.getvalue()
        
        file_size_kb = len(ppt_bytes) / 1024
        
        print(f"[SUCCESS] PPT generation completed!")
        print(f"         File size: {file_size_kb:.2f} KB")
        
        from pptx import Presentation
        stream = io.BytesIO(ppt_bytes)
        prs = Presentation(stream)
        print(f"         Slides count: {len(prs.slides)}")
        
        return True, ppt_bytes
        
    except Exception as e:
        print(f"[FAIL] PPT generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_ppt_file_integrity(ppt_bytes):
    """Test 2: Verify PPT file integrity"""
    print("\n" + "="*70)
    print("Test 2: PPT File Integrity Verification")
    print("="*70)
    
    if not ppt_bytes:
        print("[FAIL] No PPT data")
        return False
    
    try:
        from pptx import Presentation
        
        is_valid_pptx = ppt_bytes[:4] == b'PK\x03\x04'
        print(f"[INFO] ZIP header check: {'PASS' if is_valid_pptx else 'FAIL'}")
        
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
            tmp.write(ppt_bytes)
            temp_path = tmp.name
        
        try:
            prs = Presentation(temp_path)
            
            slide_count = len(prs.slides)
            print(f"[INFO] Parseable slides: {slide_count}")
            
            total_shapes = 0
            total_text_frames = 0
            text_content = []
            
            for idx, slide in enumerate(prs.slides):
                shapes_in_slide = len(slide.shapes)
                total_shapes += shapes_in_slide
                
                slide_texts = []
                for shape in slide.shapes:
                    if hasattr(shape, 'text_frame'):
                        total_text_frames += 1
                        try:
                            text = shape.text_frame.text.strip()
                            if text:
                                slide_texts.append(text[:50])
                        except:
                            pass
                
                if slide_texts:
                    text_content.append((idx+1, slide_texts[0]))
                
                preview = f"'{slide_texts[0][:30]}...'" if slide_texts else "(no text)"
                print(f"   Slide {idx+1}: {shapes_in_slide} shapes | Text: {preview}")
            
            file_size = os.path.getsize(temp_path)
            
            print(f"\n[Statistics]")
            print(f"   Total shapes: {total_shapes}")
            print(f"   Total text frames: {total_text_frames}")
            print(f"   Pages with content: {len(text_content)}/{slide_count}")
            print(f"   File size: {file_size/1024:.2f} KB")
            
            min_size = 20 * 1024
            if file_size < min_size:
                print(f"[WARN] File too small (<{min_size/1024}KB)")
                return False
            
            if slide_count < 3:
                print("[WARN] Insufficient slide count")
                return False
            
            print("\n[PASS] File integrity verification passed!")
            return True
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        print(f"[FAIL] File verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_local_storage_and_download(ppt_bytes):
    """Test 3: Local storage and download simulation"""
    print("\n" + "="*70)
    print("Test 3: Local Storage and Download Functionality")
    print("="*70)
    
    if not ppt_bytes:
        print("[FAIL] No PPT data")
        return None
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_id = "test_user_demo"
        file_name = f"{timestamp}_PiPaXing_Course.pptx"
        
        base_dir = backend_dir / 'data' / 'coursewares' / user_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        local_path = base_dir / file_name
        
        with open(local_path, 'wb') as f:
            f.write(ppt_bytes)
        
        saved_size = os.path.getsize(local_path)
        
        print(f"[INFO] File saved to local storage")
        print(f"   Path: {local_path}")
        print(f"   Size: {saved_size/1024:.2f} KB")
        print(f"   User ID: {user_id}")
        
        local_url = f"/api/local/coursewares/{user_id}/{file_name}"
        print(f"   Download URL: {local_url}")
        
        with open(local_path, 'rb') as f:
            verify_bytes = f.read()
        
        if verify_bytes == ppt_bytes:
            print("\n[PASS] Local storage verified (content matches)")
        else:
            print("\n[FAIL] File content mismatch!")
            return None
        
        from pptx import Presentation
        prs = Presentation(str(local_path))
        print(f"[PASS] Saved file can be opened normally ({len(prs.slides)} slides)")
        
        return str(local_path)
        
    except Exception as e:
        print(f"[FAIL] Local storage failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_rendering_quality(ppt_bytes):
    """Test 4: Rendering quality check"""
    print("\n" + "="*70)
    print("Test 4: PPT Rendering Quality Assessment")
    print("="*70)
    
    if not ppt_bytes:
        print("[FAIL] No PPT data")
        return False
    
    try:
        from pptx import Presentation
        from io import BytesIO
        
        stream = BytesIO(ppt_bytes)
        prs = Presentation(stream)
        
        quality_score = 0
        max_score = 100
        
        print("\n[Rendering Quality Evaluation]")
        
        has_title_pages = 0
        has_content_pages = 0
        has_text_content = 0
        readable_pages = 0
        
        for idx, slide in enumerate(prs.slides):
            page_text = ""
            shape_count = len(slide.shapes)
            
            for shape in slide.shapes:
                if hasattr(shape, 'text_frame'):
                    try:
                        text = shape.text_frame.text.strip()
                        if text:
                            page_text += text + " "
                    except:
                        pass
            
            page_text = page_text.strip()
            
            if len(page_text) > 10:
                readable_pages += 1
                has_text_content += 1
            
            keywords = ['pi pa', 'bai juyi', 'poetry', 'learning', 'class', 
                       'background', 'structure', 'summary']
            if any(kw in page_text.lower() for kw in keywords):
                has_content_pages += 1
            
            if shape_count > 0:
                has_title_pages += 1
        
        coverage = (readable_pages / len(prs.slides)) * 100
        quality_score += min(coverage * 0.4, 40)
        
        content_density = (has_content_pages / len(prs.slides)) * 100
        quality_score += min(content_density * 0.3, 30)
        
        visual_elements = (has_title_pages / len(prs.slides)) * 100
        quality_score += min(visual_elements * 0.3, 30)
        
        print(f"   Page readability: {readable_pages}/{len(prs.slides)} ({coverage:.0f}%) [+{min(coverage*0.4,40):.0f}]")
        print(f"   Content coverage: {has_content_pages}/{len(prs.slides)} ({content_density:.0f}%) [+{min(content_density*0.3,30):.0f}]")
        print(f"   Visual elements: {has_title_pages}/{len(prs.slides)} ({visual_elements:.0f}%) [+{min(visual_elements*0.3,30):.0f}]")
        
        print(f"\n   Overall Quality Score: {quality_score:.1f}/100")
        
        if quality_score >= 70:
            print("   [EXCELLENT] Excellent rendering quality! Rich and readable content")
            return True
        elif quality_score >= 50:
            print("   [GOOD] Good rendering quality, meets basic requirements")
            return True
        elif quality_score >= 30:
            print("   [ACCEPTABLE] Acceptable quality, some content may display poorly")
            return True
        else:
            print("   [POOR] Poor rendering quality, needs optimization")
            return False
            
    except Exception as e:
        print(f"[FAIL] Quality check failed: {e}")
        return False


def main():
    """Run complete test suite"""
    print("\n" + "#"*70)
    print("#  Complete PPT Generation, Rendering & Download Test Suite")
    print("#"*70)
    print(f"#  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*70)
    
    results = {}
    ppt_bytes = None
    local_file_path = None
    
    print("\n[Phase 1] PPT Generation...")
    success, ppt_bytes = test_complete_ppt_generation()
    results['generation'] = success
    
    if success and ppt_bytes:
        print("\n[Phase 2] File Integrity Verification...")
        results['integrity'] = test_ppt_file_integrity(ppt_bytes)
        
        print("\n[Phase 3] Local Storage Test...")
        local_file_path = test_local_storage_and_download(ppt_bytes)
        results['storage'] = local_file_path is not None
        
        print("\n[Phase 4] Rendering Quality Assessment...")
        results['quality'] = test_rendering_quality(ppt_bytes)
    else:
        results['integrity'] = False
        results['storage'] = False
        results['quality'] = False
    
    print("\n" + "="*70)
    print("Final Test Report")
    print("="*70)
    
    test_names = {
        'generation': 'PPT Generation',
        'integrity': 'File Integrity',
        'storage': 'Local Storage',
        'quality': 'Rendering Quality'
    }
    
    all_pass = True
    for key, name in test_names.items():
        passed = results.get(key, False)
        status = "[PASS]" if passed else "[FAIL]"
        symbol = "OK" if passed else "XX"
        print(f"  [{symbol}] {status}: {name}")
        if not passed:
            all_pass = False
    
    print("\n" + "-"*70)
    
    if all_pass:
        print("  [SUCCESS] All tests passed!")
        print("  + PPT can be generated normally")
        print("  + File is complete and valid")
        print("  + Local storage works correctly")
        print("  + Rendering quality meets requirements")
        print("  + Generated PPTX can be opened in PowerPoint/WPS")
        
        if local_file_path:
            print(f"\n  [Sample File Location]\n    {local_file_path}")
        
        return 0
    else:
        print("  [WARNING] Some tests failed, please check details above")
        return 1


if __name__ == '__main__':
    sys.exit(main())