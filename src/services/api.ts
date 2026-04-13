const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

import { UserInfo, AuthResult } from '../types';

// ---- 超时配置 ----
const DEFAULT_TIMEOUT = 30000;
const CHAT_TIMEOUT = 180000;  // 3分钟（增加到180秒）
const DECOMPOSE_TIMEOUT = 60000;
const SLIDE_TIMEOUT = 45000;
const RENDER_TIMEOUT = 180000;

// ---- 请求锁机制（防止重复请求）----
const pendingRequests = new Map<string, Promise<any>>();

function createRequestKey(url: string, body?: any): string {
  return `${url}:${JSON.stringify(body || {})}`;
}

function withRequestLock<T>(key: string, requestFn: () => Promise<T>): Promise<T> {
  if (pendingRequests.has(key)) {
    console.log(`[请求锁] 检测到重复请求，复用现有请求: ${key.substring(0, 50)}...`);
    return pendingRequests.get(key)!;
  }
  
  const promise = requestFn().finally(() => {
    pendingRequests.delete(key);
  });
  
  pendingRequests.set(key, promise);
  return promise;
}

// ---- 超时 Fetch 封装 ----
async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout: number = DEFAULT_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error(`请求超时（${timeout / 1000}秒），请检查网络或稍后重试`);
    }
    throw error;
  }
}

// ---- 认证 Token 管理 ----
const TOKEN_KEY = 'auth_token';

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function getAuthHeaders(): HeadersInit {
  const token = getAuthToken();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// ---- 全局 Fetch 包装器处理 401 错误 ----
async function handleFetchResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearAuthToken();
    window.location.href = '/';
    throw new Error('Token已过期，请重新登录');
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${response.status}: 请求失败`);
  }

  return response.json();
}

export interface MultimodalPart {
  inlineData?: {
    data: string;
    mimeType: string;
  };
  text?: string;
}

// ---- 认证接口 ----

/**
 * 用户登录
 * @param email 用户邮箱
 * @param password 明文密码（HTTPS 下传输安全）
 * @returns AuthResult 含 token 和用户基础信息
 */
export async function loginUser(email: string, password: string): Promise<AuthResult> {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    const data = await response.json();
    // NOTE: 直接抛出后端返回的中文错误信息
    throw new Error(data.detail || '登录失败，请重试');
  }

  const result = await response.json();
  // 保存 token 到 localStorage
  if (result.token) {
    setAuthToken(result.token);
    console.log('✅ Token 已保存:', result.token.substring(0, 20) + '...');
  }
  return result;
}

/**
 * 新用户注册
 * @param username 用户昵称
 * @param email 用户邮箱
 * @param password 明文密码
 * @returns AuthResult 含 token 和用户基础信息
 */
export async function registerUser(username: string, email: string, password: string): Promise<AuthResult> {
  const response = await fetch(`${BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password })
  });

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || '注册失败，请重试');
  }

  const result = await response.json();
  // 保存 token 到 localStorage
  if (result.token) {
    setAuthToken(result.token);
  }
  return result;
}

// ---- 对话接口（流式 SSE）----

/**
 * 与 AI 进行流式对话，逐 token 回调
 * @param prompt 当前用户输入
 * @param history 对话历史
 * @param onChunk 每收到一个 token 时的回调
 * @param onDone 流结束时的回调
 * @param onError 错误回调
 * @param userId 用户ID
 */
export async function chatWithGeminiStream(
  prompt: string,
  history: any[],
  onChunk: (token: string) => void,
  onDone: () => void,
  onError?: (error: string) => void,
  userId: string = "default_user"
): Promise<void> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
    onError?.(`对话超时（${CHAT_TIMEOUT / 1000}秒），请简化问题或稍后重试`);
  }, CHAT_TIMEOUT);

  try {
    const token = getAuthToken();
    console.log('🔐 发送对话请求，Token:', token ? token.substring(0, 20) + '...' : '❌ 无 Token');
    
    const response = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ prompt, history, user_id: userId }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    console.log('📡 对话响应状态:', response.status);

    if (!response.ok) {
      const errorData = await response.text();
      console.error('❌ 对话接口错误:', response.status, errorData);
      
      if (response.status === 429) {
        throw new Error('请求过于频繁，请稍后重试（建议等待10-30秒）');
      }
      throw new Error('对话接口响应异常: ' + response.status);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('无法读取流响应');

    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let lastActivity = Date.now();
    const streamTimeout = 90000;  // 流超时90秒

    const activityCheck = setInterval(() => {
      if (Date.now() - lastActivity > streamTimeout) {
        clearInterval(activityCheck);
        controller.abort();
        onError?.('流响应长时间无数据，连接已断开，请重试');
      }
    }, 10000);  // 每10秒检查一次

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        clearInterval(activityCheck);
        break;
      }

      lastActivity = Date.now();
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ') && !line.startsWith(': ')) continue;
        
        // 处理心跳注释
        if (line.startsWith(': ')) {
          console.debug('[SSE] 收到心跳');
          continue;
        }
        
        const data = line.slice(6).trim();

        if (data === '[DONE]') {
          clearInterval(activityCheck);
          clearTimeout(timeoutId);
          onDone();
          return;
        }

        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            clearInterval(activityCheck);
            clearTimeout(timeoutId);
            onError?.(parsed.error);
            return;
          }
          if (parsed.token) {
            onChunk(parsed.token);
          }
        } catch {
          // 忽略解析失败的行（可能是心跳或其他非JSON数据）
        }
      }
    }
    clearInterval(activityCheck);
    clearTimeout(timeoutId);
    onDone();
  } catch (error: any) {
    clearTimeout(timeoutId);
    console.error('Stream Chat Error:', error);
    
    if (error.name === 'AbortError') {
      if (error.message.includes('timeout') || error.message.includes('超时')) {
        onError?.(error.message || `对话超时（${CHAT_TIMEOUT / 1000}秒），请简化问题或稍后重试`);
      } else {
        onError?.('连接被中断，可能是网络波动或页面刷新导致，请点击发送按钮重试');
      }
    } else if (error.message.includes('fetch')) {
      onError?.('网络连接失败，请检查网络或后端服务是否正常运行');
    } else {
      onError?.(error.message || '抱歉，连接出了点问题，请检查后端服务是否正常运行');
    }
  }
}

/**
 * 非流式对话（兼容备用）
 */
export async function chatWithGemini(prompt: string, history: any[] = []): Promise<string> {
  try {
    const response = await fetch(`${BASE_URL}/chat/simple`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ prompt, history })
    });

    if (!response.ok) throw new Error('后端接口响应异常');
    const data = await response.json();
    return data.message || '抱歉，我无法生成回复。';
  } catch (error) {
    console.error('Chat API Error:', error);
    return '抱歉，网络连接出了点问题，请检查后端是否在 http://localhost:8000 启动。';
  }
}

/**
 * 获取指定用户的历史对话记录
 */
export async function getChatHistory(userId?: string): Promise<any[]> {
  try {
    // 实际项目中可附带 userId 参数，当前后端从 jwt token 解析即可，所以不放入 query params
    const response = await fetch(`${BASE_URL}/chat/history`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('获取历史对话失败');
    const data = await response.json();
    return data.messages || [];
  } catch (error) {
    console.error('Get Chat History Error:', error);
    return [];
  }
}

// ---- 课件生成接口 ----

export async function decomposeTopic(
  prompt: string,
  grade: string,
  subject: string,
  templateId?: string
): Promise<{ tasks: any[] }> {
  const body = { prompt, grade, subject, template_id: templateId };
  const key = createRequestKey(`${BASE_URL}/coursewares/decompose`, body);
  
  return withRequestLock(key, async () => {
    console.log('[decomposeTopic] 开始拆解大纲...');
    const response = await fetchWithTimeout(
      `${BASE_URL}/coursewares/decompose`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body)
      },
      DECOMPOSE_TIMEOUT
    );
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '拆解大纲失败');
    }
    
    const result = await response.json();
    console.log('[decomposeTopic] 大纲拆解完成，任务数:', result.tasks?.length || 0);
    return result;
  });
}

export async function generateSlide(
  task: any,
  context: string,
  userId: string,
  templateId?: string
): Promise<any> {
  const body = { task, context, user_id: userId, template_id: templateId };
  const key = createRequestKey(`${BASE_URL}/coursewares/generate/slide`, { page: task.page, topic: task.topic });
  
  return withRequestLock(key, async () => {
    console.log(`[generateSlide] 开始生成第 ${task.page} 页: ${task.topic}`);
    const response = await fetchWithTimeout(
      `${BASE_URL}/coursewares/generate/slide`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body)
      },
      SLIDE_TIMEOUT
    );
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `生成第${task.page}页失败`);
    }
    
    const result = await response.json();
    console.log(`[generateSlide] 第 ${task.page} 页生成完成`);
    return result;
  });
}

export async function analyzeSketch(base64Image: string, mimeType: string) {
  // HACK: 草图识别接口待后端实现专用端点，暂时返回空
  console.warn('Analyze sketch placeholder called.');
  return [];
}

// ---- 知识库接口 ----

export async function getKnowledgeItems() {
  const response = await fetch(`${BASE_URL}/knowledge`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  return response.json();
}

export async function uploadKnowledge(data: { name: string, type: string, size: string, tags?: string[], content?: string }) {
  const response = await fetch(`${BASE_URL}/knowledge/upload`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });
  return response.json();
}

export async function deleteKnowledgeItem(itemId: string) {
  const response = await fetch(`${BASE_URL}/knowledge/${itemId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });
  if (!response.ok) throw new Error('删除失败');
  return response.json();
}

export async function updateKnowledgeItem(
  itemId: string,
  data: { name?: string; tags?: string[]; content?: string; type?: string; size?: string } = {}
) {
  const response = await fetch(`${BASE_URL}/knowledge/${itemId}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error('更新失败');
  return response.json();
}

// ---- 模板库接口 ----

export async function getTemplates() {
  const response = await fetch(`${BASE_URL}/templates`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  return response.json();
}

// ---- 导出记录接口 ----

export async function getExports() {
  const response = await fetch(`${BASE_URL}/exports`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  return response.json();
}

export async function logExport(data: { title: string, format: string, size: string, file_url?: string }) {
  const response = await fetch(`${BASE_URL}/exports`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });
  return response.json();
}

export async function deleteExport(exportId: string) {
  const response = await fetch(`${BASE_URL}/exports/${exportId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });
  if (!response.ok) throw new Error('删除记录失败');
  return response.json();
}
// ---- 远程渲染接口 ----

export async function renderPptxFromServer(
  slides: any[], 
  title: string, 
  templateId?: string, 
  lessonPlan?: any, 
  interaction?: any
): Promise<{ status: string; courseware_id: string; file_url: string; title: string }> {
  const normalizedSlides = slides.map((s, index) => {
    let content = s.content;
    if (typeof content === 'string') {
      content = content.trim() ? [content.trim()] : [];
    } else if (Array.isArray(content)) {
      content = content.map(c => String(c || '').trim()).filter(c => c);
    } else {
      content = [];
    }

    const normalizedTables = (s.tables || []).map((t: any) => ({
      name: String(t.name || `表格${index + 1}`),
      headers: Array.isArray(t.headers) ? t.headers.map((h: any) => String(h || '')) : [],
      rows: Array.isArray(t.rows) ? t.rows.map((row: any) => 
        Array.isArray(row) ? row.map((cell: any) => cell ?? '') : []
      ) : []
    }));

    const normalizedCharts = (s.charts || []).map((c: any) => ({
      name: String(c.name || `图表${index + 1}`),
      chart_type: c.chart_type || 'column_clustered',
      categories: Array.isArray(c.categories) ? c.categories.map((cat: any) => String(cat || '')) : [],
      series: Array.isArray(c.series) ? c.series.map((s: any) => ({
        name: String(s.name || '系列'),
        values: Array.isArray(s.values) ? s.values.map((v: any) => Number(v) || 0) : []
      })) : []
    }));

    return {
      title: String(s.title || `第${index + 1}页`).trim(),
      content,
      page_type: String(s.page_type || s.type || 'content'),
      type: String(s.type || s.page_type || 'content'),
      layout_suggestion: String(s.layout_suggestion || 'bullet_points'),
      imagePrompt: s.imagePrompt ? String(s.imagePrompt) : null,
      variables: s.variables && typeof s.variables === 'object' ? s.variables : {},
      images: Array.isArray(s.images) ? s.images : [],
      tables: normalizedTables,
      charts: normalizedCharts
    };
  });

  const body = { 
    slides: normalizedSlides,
    title: String(title || '未命名课件').trim(),
    template_id: templateId || null,
    lesson_plan: lessonPlan || null,
    interaction: interaction || null
  };
  
  console.log('[renderPptxFromServer] 发送渲染请求:', { 
    slideCount: normalizedSlides.length, 
    title: body.title,
    templateId: templateId 
  });

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), RENDER_TIMEOUT);

  try {
    const response = await fetch(`${BASE_URL}/coursewares/render`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `渲染失败 (${response.status})`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = response.statusText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log('[renderPptxFromServer] 渲染成功:', result);
    return result;
  } catch (error: any) {
    clearTimeout(timeoutId);
    
    if (error.name === 'AbortError') {
      throw new Error(`PPT渲染超时（超过${RENDER_TIMEOUT / 1000}秒），请稍后重试`);
    }
    
    console.error('[renderPptxFromServer] 渲染失败:', error);
    throw error;
  }
}

export async function renderDocxFromServer(title: string, lessonPlan: any) {
  const response = await fetch(`${BASE_URL}/coursewares/render/docx`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ title, lesson_plan: lessonPlan })
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '教案远程渲染失败');
  }
  return response.json();
}

export interface PreviewSlide {
  slide_num: number;
  title: string;
  content_preview?: string;
  image: string | null;
}

export interface PreviewResult {
  status: string;
  title: string;
  total_slides: number;
  slides: PreviewSlide[];
  render_time: number;
}

export async function previewRenderedPptx(
  slides: any[], 
  title: string, 
  templateId?: string
): Promise<PreviewResult> {
  const normalizedSlides = slides.map((s, index) => {
    let content = s.content;
    if (typeof content === 'string') {
      content = content.trim() ? [content.trim()] : [];
    } else if (Array.isArray(content)) {
      content = content.map(c => String(c || '').trim()).filter(c => c);
    } else {
      content = [];
    }

    return {
      title: String(s.title || `第${index + 1}页`),
      content,
      page_type: String(s.page_type || s.type || 'content'),
      type: String(s.type || s.page_type || 'content'),
      layout_suggestion: String(s.layout_suggestion || 'bullet_points'),
      imagePrompt: s.imagePrompt ? String(s.imagePrompt) : null,
      variables: s.variables && typeof s.variables === 'object' ? s.variables : {},
      images: Array.isArray(s.images) ? s.images : [],
      tables: Array.isArray(s.tables) ? s.tables : [],
      charts: Array.isArray(s.charts) ? s.charts : []
    };
  });

  const body = { 
    slides: normalizedSlides,
    title: String(title || '未命名课件').trim(),
    template_id: templateId || null
  };
  
  console.log('[previewRenderedPptx] 发送预览请求:', { 
    slideCount: normalizedSlides.length, 
    title: body.title,
    templateId: templateId 
  });

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), RENDER_TIMEOUT);

  try {
    const response = await fetch(`${BASE_URL}/coursewares/preview`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `预览渲染失败 (${response.status})`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = response.statusText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log('[previewRenderedPptx] 预览成功:', result);
    return result;
  } catch (error: any) {
    clearTimeout(timeoutId);
    
    if (error.name === 'AbortError') {
      throw new Error(`PPT预览渲染超时（超过${RENDER_TIMEOUT / 1000}秒），请稍后重试`);
    }
    
    console.error('[previewRenderedPptx] 预览失败:', error);
    throw error;
  }
}

// ---- PPT模板库API (v2) ----

export async function getMyTemplates(category?: string, skip: number = 0, limit: number = 50) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  params.append('skip', skip.toString());
  params.append('limit', limit.toString());
  
  const response = await fetch(`${BASE_URL}/templates/my-templates?${params}`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  const data = await response.json();
  return data.templates || [];
}

export async function getPublicTemplates(category?: string, skip: number = 0, limit: number = 50) {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  params.append('skip', skip.toString());
  params.append('limit', limit.toString());
  
  const response = await fetch(`${BASE_URL}/templates/public?${params}`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  const data = await response.json();
  return data.templates || [];
}

export async function getTemplateById(templateId: string) {
  const response = await fetch(`${BASE_URL}/templates/${templateId}`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data.template || null;
}

export async function uploadTemplate(
  formData: FormData
): Promise<any> {
  const response = await fetch(`${BASE_URL}/templates/upload`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: formData
  });
  if (!response.ok) throw new Error('Upload failed');
  const data = await response.json();
  return data.template;
}

export async function saveCoursewareAsTemplate(
  coursewareId: string,
  title: string,
  description: string,
  visibility: 'private' | 'public'
) {
  const formData = new URLSearchParams();
  formData.append('courseware_id', coursewareId);
  formData.append('title', title);
  formData.append('description', description);
  formData.append('category', '');
  formData.append('visibility', visibility);
  
  const response = await fetch(`${BASE_URL}/templates/save-courseware`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: formData
  });
  if (!response.ok) throw new Error('Save failed');
  const data = await response.json();
  return data.template;
}

export async function copyTemplate(templateId: string) {
  const response = await fetch(`${BASE_URL}/templates/${templateId}/copy`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  if (!response.ok) throw new Error('Copy failed');
  const data = await response.json();
  return data.template;
}

export async function deleteTemplate(templateId: string) {
  const response = await fetch(`${BASE_URL}/templates/${templateId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });
  if (!response.ok) throw new Error('Delete failed');
}

export async function getTemplateDownloadUrl(templateId: string) {
  const response = await fetch(`${BASE_URL}/templates/${templateId}/download`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '获取下载链接失败');
  }
  return response.json();
}

export async function getTemplateCategories() {
  const response = await fetch(`${BASE_URL}/templates/categories`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  const data = await response.json();
  return data.categories || [];
}


// ---- PPT模板库API (新接口) ----

export async function getPptTemplateList(
  templateType: 'personal' | 'public' = 'personal',
  page: number = 1,
  pageSize: number = 20
): Promise<{ templates: any[]; total: number }> {
  const params = new URLSearchParams();
  params.append('template_type', templateType);
  params.append('page', page.toString());
  params.append('page_size', pageSize.toString());
  
  const response = await fetch(`${BASE_URL}/ppt-templates?${params}`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '获取模板列表失败');
  }
  const data = await response.json();
  return {
    templates: data.templates || [],
    total: data.total || 0
  };
}

export async function getPptTemplateById(templateId: string) {
  const response = await fetch(`${BASE_URL}/ppt-templates/${templateId}`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data.template || null;
}

export async function getTemplateThumbnailUrl(templateId: string, expiresIn: number = 3600): Promise<string | null> {
  try {
    const response = await fetch(
      `${BASE_URL}/ppt-templates/${templateId}/thumbnail-url?expires_in=${expiresIn}`,
      { headers: getAuthHeaders() }
    );
    if (!response.ok) return null;
    const data = await response.json();
    return data.signed_url || null;
  } catch {
    return null;
  }
}

export async function previewPptTemplate(templateId: string): Promise<string> {
  const token = getAuthToken();
  return `${BASE_URL}/ppt-templates/${templateId}/preview?token=${token}`;
}

export async function downloadPptTemplate(templateId: string): Promise<{ download_url: string; file_name: string }> {
  const response = await fetch(`${BASE_URL}/templates/${templateId}/download`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '获取下载链接失败');
  }
  const data = await response.json();
  return {
    download_url: data.download_url,
    file_name: data.file_name
  };
}

export async function deletePptTemplate(templateId: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${BASE_URL}/ppt-templates/${templateId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '删除失败');
  }
  return response.json();
}

export async function copyPptTemplate(templateId: string): Promise<{ success: boolean; template: any }> {
  const response = await fetch(`${BASE_URL}/ppt-templates/${templateId}/copy`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '复制失败');
  }
  return response.json();
}

export async function clearChatHistory(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/chat/history`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    return response.ok;
  } catch (error) {
    console.error('Clear history error:', error);
    return false;
  }
}
