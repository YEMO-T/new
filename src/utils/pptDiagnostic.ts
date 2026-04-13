console.log('🔧 加载PPT诊断工具...');

(window as any).quickFix = async function() {
  console.log('\n=== 开始快速诊断和修复 ===\n');
  
  // 1. 检查认证
  console.log('1️⃣ 检查认证状态...');
  const token = localStorage.getItem('auth_token');
  if (!token) {
    console.error('❌ 未找到认证token，请重新登录');
    console.log('💡 解决方案: 请在界面上重新登录');
    return;
  }
  console.log('✅ Token存在:', token.substring(0, 10) + '...');
  
  // 2. 检查后端
  console.log('\n2️⃣ 检查后端连接...');
  try {
    const response = await fetch('http://localhost:8000/api/health', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (response.ok) {
      console.log('✅ 后端服务正常');
    } else {
      console.error(`❌ 后端服务异常: ${response.status}`);
      console.log('💡 解决方案: 检查后端服务是否正常运行');
      return;
    }
  } catch (error: any) {
    console.error('❌ 无法连接到后端服务:', error.message);
    console.log('💡 解决方案: 启动后端服务');
    console.log('   cd backend && python main.py');
    return;
  }
  
  // 3. 检查幻灯片数据
  console.log('\n3️⃣ 检查幻灯片数据...');
  const slides = (window as any).slides;
  if (!slides || !Array.isArray(slides) || slides.length === 0) {
    console.log('❌ 未找到幻灯片数据');
    console.log('💡 解决方案: 先生成幻灯片内容');
    return;
  }
  console.log(`✅ 找到 ${slides.length} 张幻灯片`);
  
  // 4. 测试预览API
  console.log('\n4️⃣ 测试预览API...');
  try {
    const testSlide = slides[0];
    const body = {
      slides: [{
        title: testSlide.title || '测试幻灯片',
        content: Array.isArray(testSlide.content) 
          ? testSlide.content 
          : typeof testSlide.content === 'string' 
            ? [testSlide.content] 
            : [],
        page_type: 'content',
        type: 'content',
        layout_suggestion: 'bullet_points'
      }],
      title: '测试渲染',
      template_id: null
    };
    
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
      console.log('💡 解决方案: 检查请求体格式');
      return;
    }
    
    const result = await response.json();
    console.log('✅ PPT渲染测试成功！');
    console.log('📊 渲染结果:', {
      slideCount: result.slides?.length,
      renderTime: result.render_time
    });
    
    console.log('\n✅ 所有检查通过！PPT渲染功能正常');
  } catch (error: any) {
    console.error('❌ PPT渲染测试失败:', error.message);
  }
};

(window as any).runDiagnostics = async function() {
  console.log('\n=== PPT渲染诊断报告 ===\n');
  
  const results = [];
  
  // 1. 认证检查
  const token = localStorage.getItem('auth_token');
  results.push({
    category: '认证',
    status: token ? '✅' : '❌',
    message: token ? '已登录' : '未登录或token已过期'
  });
  
  // 2. 后端连接检查
  try {
    const response = await fetch('http://localhost:8000/api/health');
    results.push({
      category: '后端连接',
      status: response.ok ? '✅' : '❌',
      message: response.ok ? '后端服务正常' : `后端服务异常 (${response.status})`
    });
  } catch (error) {
    results.push({
      category: '后端连接',
      status: '❌',
      message: '无法连接到后端服务'
    });
  }
  
  // 3. 幻灯片数据检查
  const slides = (window as any).slides;
  if (slides && Array.isArray(slides) && slides.length > 0) {
    results.push({
      category: '幻灯片数据',
      status: '✅',
      message: `找到 ${slides.length} 张幻灯片`
    });
  } else {
    results.push({
      category: '幻灯片数据',
      status: '⚠️',
      message: '未找到幻灯片数据'
    });
  }
  
  // 打印结果
  results.forEach(result => {
    console.log(`${result.status} [${result.category}] ${result.message}`);
  });
  
  console.log('\n======================\n');
  return results;
};

(window as any).testPPTRender = async function() {
  console.log('\n=== 测试PPT渲染 ===\n');
  
  const token = localStorage.getItem('auth_token');
  const slides = (window as any).slides;
  
  if (!token) {
    console.error('❌ 请先登录');
    return;
  }
  
  if (!slides || slides.length === 0) {
    console.error('❌ 没有可渲染的幻灯片');
    return;
  }
  
  try {
    const body = {
      slides: slides.slice(0, 1).map((s: any) => ({
        title: s.title || '测试',
        content: Array.isArray(s.content) ? s.content : [s.content].filter(Boolean),
        page_type: 'content',
        type: 'content',
        layout_suggestion: 'bullet_points'
      })),
      title: '测试渲染',
      template_id: null
    };
    
    console.log('📤 发送测试请求...');
    const response = await fetch('http://localhost:8000/api/coursewares/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      const error = await response.json();
      console.error('❌ 渲染失败:', error);
      return;
    }
    
    const result = await response.json();
    console.log('✅ 渲染成功！');
    console.log('📊 结果:', result);
  } catch (error: any) {
    console.error('❌ 测试失败:', error.message);
  }
};

(window as any).testBackend = async function() {
  console.log('测试后端连接...');
  try {
    const response = await fetch('http://localhost:8000/api/health');
    console.log(response.ok ? '✅ 后端正常' : '❌ 后端异常');
    return response.ok;
  } catch (error) {
    console.error('❌ 无法连接到后端');
    return false;
  }
};

(window as any).fixSlideData = function(slides: any[]) {
  if (!Array.isArray(slides)) {
    console.error('❌ 幻灯片数据不是数组');
    return [];
  }
  
  const fixed = slides.map((slide, index) => ({
    title: String(slide.title || `第${index + 1}页`),
    content: Array.isArray(slide.content) 
      ? slide.content.filter(c => c) 
      : typeof slide.content === 'string' 
        ? [slide.content] 
        : [],
    page_type: 'content',
    type: 'content',
    layout_suggestion: 'bullet_points'
  }));
  
  console.log(`✅ 修复了 ${fixed.length} 张幻灯片`);
  return fixed;
};

console.log('✅ PPT诊断工具加载完成！');
console.log('可用命令:');
console.log('  - quickFix()         // 快速修复');
console.log('  - runDiagnostics()   // 运行诊断');
console.log('  - testPPTRender()    // 测试渲染');
console.log('  - testBackend()      // 测试后端');
console.log('  - fixSlideData(slides) // 修复数据');
