import { ApiError, logError, getErrorMessage } from './errorUtils';
import { requestManager } from './requestManager';

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

const DEFAULT_TIMEOUT = 30000;
const CHAT_TIMEOUT = 120000;
const DECOMPOSE_TIMEOUT = 60000;
const SLIDE_TIMEOUT = 45000;
const RENDER_TIMEOUT = 180000;

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

export interface PreviewSlide {
  slide_num: number;
  title: string;
  content_preview: string;
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
    templateId: templateId,
    sampleSlide: normalizedSlides[0]
  });

  try {
    const response = await requestManager.fetchWithTimeout(
      `${BASE_URL}/coursewares/preview`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body)
      },
      { timeout: RENDER_TIMEOUT }
    );

    if (!response.ok) {
      throw await ApiError.fromResponse(response);
    }

    const result = await response.json();
    console.log('[previewRenderedPptx] 预览成功:', result);
    return result;
  } catch (error: any) {
    logError('previewRenderedPptx', error);
    
    if (error.name === 'AbortError' || error.message.includes('超时')) {
      throw new Error(`PPT预览渲染超时（超过${RENDER_TIMEOUT / 1000}秒），请稍后重试`);
    }
    
    throw error;
  }
}

export async function renderPptxFromServer(
  slides: any[],
  title: string,
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
    lesson_plan: lessonPlan || null,
    interaction: interaction || null
  };

  console.log('[renderPptxFromServer] 发送渲染请求:', {
    slideCount: normalizedSlides.length,
    title: body.title
  });

  try {
    const response = await requestManager.fetchWithTimeout(
      `${BASE_URL}/coursewares/render`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body)
      },
      { timeout: RENDER_TIMEOUT }
    );

    if (!response.ok) {
      throw await ApiError.fromResponse(response);
    }

    const result = await response.json();
    console.log('[renderPptxFromServer] 渲染成功:', result);
    return result;
  } catch (error: any) {
    logError('renderPptxFromServer', error);
    throw error;
  }
}

export { getErrorMessage, logError, ApiError };
