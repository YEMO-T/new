const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

import { UserInfo, AuthResult } from '../types';

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
    // Token 过期或无效，清除 token 并重定向到登录页
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
 */
export async function chatWithGeminiStream(
  prompt: string,
  history: any[],
  onChunk: (token: string) => void,
  onDone: () => void,
  onError?: (error: string) => void,
  userId: string = "default_user"
): Promise<void> {
  try {
    const token = getAuthToken();
    console.log('🔐 发送对话请求，Token:', token ? token.substring(0, 20) + '...' : '❌ 无 Token');
    
    const response = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ prompt, history, user_id: userId })
    });

    console.log('📡 对话响应状态:', response.status);

    if (!response.ok) {
      const errorData = await response.text();
      console.error('❌ 对话接口错误:', response.status, errorData);
      throw new Error('对话接口响应异常: ' + response.status);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('无法读取流响应');

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();

        if (data === '[DONE]') {
          onDone();
          return;
        }

        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            onError?.(parsed.error);
            return;
          }
          if (parsed.token) {
            onChunk(parsed.token);
          }
        } catch {
          // 忽略解析失败的行
        }
      }
    }
    onDone();
  } catch (error) {
    console.error('Stream Chat Error:', error);
    onError?.('抱歉，连接出了点问题，请检查后端服务是否正常运行。');
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
  const response = await fetch(`${BASE_URL}/coursewares/decompose`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ prompt, grade, subject, template_id: templateId })
  });
  if (!response.ok) throw new Error('拆解大纲失败');
  return response.json();
}

export async function generateSlide(
  task: any,
  context: string,
  userId: string,
  templateId?: string
): Promise<any> {
  const response = await fetch(`${BASE_URL}/coursewares/generate/slide`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ task, context, user_id: userId, template_id: templateId })
  });
  if (!response.ok) throw new Error(`生成第${task.page}页失败`);
  return response.json();
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

export async function renderPptxFromServer(slides: any[], title: string, templateId?: string) {
  const body: any = { slides, title };
  if (templateId) {
    body.template_id = templateId;
  }
  
  const response = await fetch(`${BASE_URL}/coursewares/render`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'PPT 远程渲染失败');
  }
  return response.json();
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

export async function getTemplateCategories() {
  const response = await fetch(`${BASE_URL}/templates/categories`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) return [];
  const data = await response.json();
  return data.categories || [];
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
