import { getAuthToken, setAuthToken, clearAuthToken } from '../services/api';

export class PPTRenderFixer {
  
  static fixAuthIssue(): boolean {
    const token = getAuthToken();
    if (!token) {
      console.error('❌ 未找到认证token，请重新登录');
      return false;
    }
    
    if (token.length < 20) {
      console.warn('⚠️ Token格式可能不正确');
      return false;
    }
    
    console.log('✅ Token检查通过');
    return true;
  }

  static fixSlideData(slides: any[]): any[] {
    if (!Array.isArray(slides)) {
      console.error('❌ 幻灯片数据不是数组');
      return [];
    }

    const fixedSlides = slides.map((slide, index) => {
      const fixed: any = {
        title: String(slide.title || `第${index + 1}页`),
        page_type: String(slide.page_type || slide.type || 'content'),
        type: String(slide.type || slide.page_type || 'content'),
        layout_suggestion: String(slide.layout_suggestion || 'bullet_points'),
        variables: slide.variables && typeof slide.variables === 'object' ? slide.variables : {},
        images: Array.isArray(slide.images) ? slide.images : [],
        tables: Array.isArray(slide.tables) ? slide.tables : [],
        charts: Array.isArray(slide.charts) ? slide.charts : []
      };

      if (typeof slide.content === 'string') {
        fixed.content = slide.content.trim() ? [slide.content.trim()] : [];
      } else if (Array.isArray(slide.content)) {
        fixed.content = slide.content
          .map(c => String(c || '').trim())
          .filter(c => c.length > 0);
      } else {
        fixed.content = [];
      }

      if (slide.imagePrompt) {
        fixed.imagePrompt = String(slide.imagePrompt);
      }

      return fixed;
    });

    console.log(`✅ 修复了 ${fixedSlides.length} 张幻灯片`);
    return fixedSlides;
  }

  static async testBackendConnection(): Promise<boolean> {
    try {
      const response = await fetch('http://localhost:8000/api/health', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      });

      if (response.ok) {
        console.log('✅ 后端服务正常');
        return true;
      } else {
        console.error(`❌ 后端服务异常: ${response.status}`);
        return false;
      }
    } catch (error: any) {
      console.error('❌ 无法连接到后端服务:', error.message);
      return false;
    }
  }

  static async testPreviewAPI(slides: any[], title: string, templateId?: string): Promise<any> {
    const token = getAuthToken();
    if (!token) {
      throw new Error('请先登录');
    }

    const fixedSlides = this.fixSlideData(slides);

    const body = {
      slides: fixedSlides,
      title: String(title || '未命名课件').trim(),
      template_id: templateId || null
    };

    console.log('📤 发送预览请求:', {
      slideCount: fixedSlides.length,
      title: body.title,
      templateId: templateId
    });

    const response = await fetch('http://localhost:8000/api/coursewares/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('❌ 预览失败:', errorData);
      throw new Error(errorData.detail || `预览失败 (${response.status})`);
    }

    const result = await response.json();
    console.log('✅ 预览成功:', result);
    return result;
  }

  static async quickFix(): Promise<void> {
    console.log('🔧 开始快速修复...\n');

    // 1. 检查认证
    console.log('1️⃣ 检查认证状态...');
    const authOk = this.fixAuthIssue();
    if (!authOk) {
      console.log('💡 解决方案: 请重新登录');
      return;
    }

    // 2. 检查后端
    console.log('\n2️⃣ 检查后端连接...');
    const backendOk = await this.testBackendConnection();
    if (!backendOk) {
      console.log('💡 解决方案: 启动后端服务');
      console.log('   cd backend && python main.py');
      return;
    }

    // 3. 检查幻灯片数据
    console.log('\n3️⃣ 检查幻灯片数据...');
    const slides = (window as any).slides;
    if (!slides || slides.length === 0) {
      console.log('❌ 未找到幻灯片数据');
      console.log('💡 解决方案: 先生成幻灯片');
      return;
    }

    const fixedSlides = this.fixSlideData(slides);
    console.log(`✅ 找到 ${fixedSlides.length} 张有效幻灯片`);

    // 4. 测试预览API
    console.log('\n4️⃣ 测试预览API...');
    try {
      const result = await this.testPreviewAPI(
        fixedSlides,
        slides[0]?.title || '测试课件'
      );
      console.log('✅ PPT渲染测试成功！');
      console.log('📊 渲染结果:', {
        slideCount: result.slides?.length,
        renderTime: result.render_time
      });
    } catch (error: any) {
      console.error('❌ PPT渲染测试失败:', error.message);
      console.log('💡 请查看详细错误信息并参考文档修复');
    }
  }
}

(window as any).quickFix = () => PPTRenderFixer.quickFix();
(window as any).fixSlideData = (slides: any[]) => PPTRenderFixer.fixSlideData(slides);
(window as any).testBackend = () => PPTRenderFixer.testBackendConnection();
(window as any).testPreview = (slides: any[], title: string, templateId?: string) => 
  PPTRenderFixer.testPreviewAPI(slides, title, templateId);

console.log('🛠️ PPT渲染修复工具已加载！');
console.log('在控制台运行以下命令：');
console.log('  - quickFix()              // 快速修复');
console.log('  - fixSlideData(slides)    // 修复幻灯片数据');
console.log('  - testBackend()           // 测试后端连接');
console.log('  - testPreview(slides, title, templateId)  // 测试预览API');
