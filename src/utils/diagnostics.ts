import { getAuthToken } from '../services/api';

interface DiagnosticResult {
  category: string;
  status: 'success' | 'warning' | 'error';
  message: string;
  details?: any;
}

export async function runDiagnostics(): Promise<DiagnosticResult[]> {
  const results: DiagnosticResult[] = [];

  // 1. 检查认证状态
  const token = getAuthToken();
  results.push({
    category: '认证',
    status: token ? 'success' : 'error',
    message: token ? '已登录' : '未登录或token已过期',
    details: token ? { tokenPrefix: token.substring(0, 10) + '...' } : null
  });

  // 2. 检查后端连接
  try {
    const response = await fetch('http://localhost:8000/api/health', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    results.push({
      category: '后端连接',
      status: response.ok ? 'success' : 'error',
      message: response.ok ? '后端服务正常' : `后端服务异常 (${response.status})`,
      details: { status: response.status }
    });
  } catch (error: any) {
    results.push({
      category: '后端连接',
      status: 'error',
      message: '无法连接到后端服务',
      details: { error: error.message }
    });
  }

  // 3. 检查幻灯片数据
  const slides = (window as any).slides;
  if (slides && Array.isArray(slides)) {
    const validSlides = slides.filter(s => s && (s.title || s.content));
    results.push({
      category: '幻灯片数据',
      status: validSlides.length > 0 ? 'success' : 'warning',
      message: `找到 ${slides.length} 张幻灯片，${validSlides.length} 张有效`,
      details: {
        total: slides.length,
        valid: validSlides.length,
        sample: validSlides[0] ? {
          title: validSlides[0].title,
          contentType: typeof validSlides[0].content,
          isArray: Array.isArray(validSlides[0].content)
        } : null
      }
    });
  } else {
    results.push({
      category: '幻灯片数据',
      status: 'warning',
      message: '未找到幻灯片数据'
    });
  }

  // 4. 检查网络请求
  try {
    const start = Date.now();
    const response = await fetch('http://localhost:8000/api/health');
    const duration = Date.now() - start;
    
    results.push({
      category: '网络延迟',
      status: duration < 1000 ? 'success' : duration < 3000 ? 'warning' : 'error',
      message: `响应时间: ${duration}ms`,
      details: { duration }
    });
  } catch (error: any) {
    results.push({
      category: '网络延迟',
      status: 'error',
      message: '网络请求失败',
      details: { error: error.message }
    });
  }

  // 5. 检查浏览器环境
  results.push({
    category: '浏览器环境',
    status: 'success',
    message: '浏览器信息',
    details: {
      userAgent: navigator.userAgent,
      language: navigator.language,
      cookiesEnabled: navigator.cookieEnabled
    }
  });

  return results;
}

export async function testPPTRender(): Promise<DiagnosticResult> {
  const token = getAuthToken();
  const slides = (window as any).slides;

  if (!token) {
    return {
      category: 'PPT渲染测试',
      status: 'error',
      message: '请先登录'
    };
  }

  if (!slides || slides.length === 0) {
    return {
      category: 'PPT渲染测试',
      status: 'error',
      message: '没有可渲染的幻灯片'
    };
  }

  try {
    const testSlide = slides[0];
    const response = await fetch('http://localhost:8000/api/coursewares/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        slides: [{
          title: testSlide.title || '测试幻灯片',
          content: Array.isArray(testSlide.content) ? testSlide.content : [testSlide.content],
          page_type: 'content',
          type: 'content',
          layout_suggestion: 'bullet_points'
        }],
        title: '测试渲染',
        template_id: null
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      return {
        category: 'PPT渲染测试',
        status: 'error',
        message: `渲染失败 (${response.status})`,
        details: errorData
      };
    }

    const result = await response.json();
    return {
      category: 'PPT渲染测试',
      status: 'success',
      message: '渲染成功',
      details: {
        slideCount: result.slides?.length,
        renderTime: result.render_time
      }
    };
  } catch (error: any) {
    return {
      category: 'PPT渲染测试',
      status: 'error',
      message: `渲染测试失败: ${error.message}`,
      details: { error: error.message }
    };
  }
}

export function printDiagnostics(results: DiagnosticResult[]) {
  console.log('\n=== PPT渲染诊断报告 ===\n');
  
  results.forEach(result => {
    const icon = result.status === 'success' ? '✅' : result.status === 'warning' ? '⚠️' : '❌';
    console.log(`${icon} [${result.category}] ${result.message}`);
    if (result.details) {
      console.log('   详情:', result.details);
    }
  });
  
  console.log('\n======================\n');
}

(window as any).runDiagnostics = async () => {
  const results = await runDiagnostics();
  printDiagnostics(results);
  return results;
};

(window as any).testPPTRender = async () => {
  const result = await testPPTRender();
  console.log('\n=== PPT渲染测试结果 ===\n');
  const icon = result.status === 'success' ? '✅' : result.status === 'warning' ? '⚠️' : '❌';
  console.log(`${icon} ${result.message}`);
  if (result.details) {
    console.log('详情:', result.details);
  }
  console.log('\n======================\n');
  return result;
};

console.log('🔍 诊断工具已加载！');
console.log('在控制台运行以下命令：');
console.log('  - runDiagnostics()  // 运行完整诊断');
console.log('  - testPPTRender()   // 测试PPT渲染');
