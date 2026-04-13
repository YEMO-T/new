/**
 * RAG知识库 API 接口封装
 */

import { getAuthToken } from './api';

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

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

export interface KnowledgeItem {
  id: string;
  name: string;
  type: string;
  size: string;
  tags: string[];
  visibility: 'private' | 'public';
  grade_level?: string;
  subject?: string;
  description?: string;
  vector_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
  created_at: string;
  updated_at: string;
  user_id: string;
  is_owner: boolean;
  content?: string;
}

export interface RAGSearchResult {
  id: string;
  knowledge_item_id: string;
  chunk_text: string;
  chunk_index: number;
  source_resource: string;
  page_number: number;
  similarity: number;
  item_name: string;
  item_visibility: string;
  item_grade: string;
  item_subject: string;
}

export interface RAGConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface RAGMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: RAGSource[];
  created_at: string;
}

export interface RAGSource {
  knowledge_item_id: string;
  chunk_text: string;
  source_resource: string;
  similarity: number;
  grade?: string;
  subject?: string;
}

export interface KnowledgeStats {
  private_count: number;
  public_count: number;
  vectorized_count: number;
  pending_count: number;
}

export async function getKnowledgeList(params?: {
  visibility?: 'private' | 'public';
  grade?: string;
  subject?: string;
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: KnowledgeItem[]; total: number; page: number; page_size: number; total_pages: number }> {
  const searchParams = new URLSearchParams();
  if (params?.visibility) searchParams.append('visibility', params.visibility);
  if (params?.grade) searchParams.append('grade', params.grade);
  if (params?.subject) searchParams.append('subject', params.subject);
  if (params?.search) searchParams.append('search', params.search);
  if (params?.page) searchParams.append('page', params.page.toString());
  if (params?.page_size) searchParams.append('page_size', params.page_size.toString());

  const response = await fetch(`${BASE_URL}/knowledge/list?${searchParams}`, {
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '获取知识库列表失败');
  }
  return data.data;
}

export async function uploadKnowledgeFile(
  file: File,
  options?: {
    name?: string;
    visibility?: 'private' | 'public';
    grade_level?: string;
    subject?: string;
    description?: string;
    tags?: string[];
    education_level?: string;
    resource_type?: string;
    difficulty?: string;
    semester?: string;
    chapter?: string;
  }
): Promise<KnowledgeItem> {
  const formData = new FormData();
  formData.append('file', file);
  if (options?.name) formData.append('name', options.name);
  formData.append('visibility', options?.visibility || 'private');
  if (options?.grade_level) formData.append('grade_level', options.grade_level);
  if (options?.subject) formData.append('subject', options.subject);
  if (options?.description) formData.append('description', options.description);
  if (options?.tags) formData.append('tags', options.tags.join(','));
  if (options?.education_level) formData.append('education_level', options.education_level);
  if (options?.resource_type) formData.append('resource_type', options.resource_type);
  if (options?.difficulty) formData.append('difficulty', options.difficulty);
  if (options?.semester) formData.append('semester', options.semester);
  if (options?.chapter) formData.append('chapter', options.chapter);

  const token = getAuthToken();
  const response = await fetch(`${BASE_URL}/knowledge/upload`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '上传失败');
  }
  return data.data;
}

export async function createKnowledge(data: {
  name: string;
  content: string;
  type?: string;
  visibility?: 'private' | 'public';
  grade_level?: string;
  subject?: string;
  description?: string;
  tags?: string[];
}): Promise<KnowledgeItem> {
  const response = await fetch(`${BASE_URL}/knowledge/create`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  const result = await response.json();
  if (result.code !== 200) {
    throw new Error(result.message || '创建失败');
  }
  return result.data;
}

export async function getKnowledgeDetail(itemId: string): Promise<KnowledgeItem> {
  const response = await fetch(`${BASE_URL}/knowledge/${itemId}`, {
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '获取详情失败');
  }
  return data.data;
}

export async function updateKnowledge(
  itemId: string,
  data: {
    name?: string;
    tags?: string[];
    content?: string;
    visibility?: 'private' | 'public';
    grade_level?: string;
    subject?: string;
    description?: string;
  }
): Promise<KnowledgeItem> {
  const response = await fetch(`${BASE_URL}/knowledge/${itemId}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  const result = await response.json();
  if (result.code !== 200) {
    throw new Error(result.message || '更新失败');
  }
  return result.data;
}

export async function deleteKnowledge(itemId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/knowledge/${itemId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '删除失败');
  }
}

export async function searchKnowledge(params: {
  query: string;
  grade?: string;
  subject?: string;
  top_k?: number;
  min_confidence?: number;
}): Promise<RAGSearchResult[]> {
  const response = await fetch(`${BASE_URL}/knowledge/search`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(params)
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '搜索失败');
  }
  return data.data;
}

export async function vectorizeKnowledge(itemId: string): Promise<{ success: boolean; chunk_count: number }> {
  const response = await fetch(`${BASE_URL}/knowledge/vectorize/${itemId}`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '向量化失败');
  }
  return data.data;
}

export async function getKnowledgeStats(): Promise<KnowledgeStats> {
  const response = await fetch(`${BASE_URL}/knowledge/stats`, {
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '获取统计失败');
  }
  return data.data;
}

export async function askRAGQuestion(params: {
  question: string;
  conversation_id?: string;
  grade?: string;
  subject?: string;
  top_k?: number;
  min_confidence?: number;
  stream?: boolean;
}): Promise<{ answer: string; sources: RAGSource[]; conversation_id: string }> {
  const response = await fetch(`${BASE_URL}/rag/ask`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ ...params, stream: false })
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '问答失败');
  }
  return data.data;
}

export async function askRAGQuestionStream(
  params: {
    question: string;
    conversation_id?: string;
    grade?: string;
    subject?: string;
    top_k?: number;
    min_confidence?: number;
  },
  onToken: (token: string) => void,
  onDone: (conversationId: string) => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const response = await fetch(`${BASE_URL}/rag/ask`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ ...params, stream: true })
    });

    const conversationId = response.headers.get('X-Conversation-Id') || '';

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

        if (data === '{"done":true}') {
          onDone(conversationId);
          return;
        }

        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            onError(parsed.error);
            return;
          }
          if (parsed.token) {
            onToken(parsed.token);
          }
        } catch {
          // 忽略解析失败的行
        }
      }
    }
    onDone(conversationId);
  } catch (error) {
    onError(error instanceof Error ? error.message : '未知错误');
  }
}

export async function getRAGConversations(params?: {
  page?: number;
  page_size?: number;
}): Promise<{ conversations: RAGConversation[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append('page', params.page.toString());
  if (params?.page_size) searchParams.append('page_size', params.page_size.toString());

  const response = await fetch(`${BASE_URL}/rag/conversations?${searchParams}`, {
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '获取对话列表失败');
  }
  return data.data;
}

export async function getRAGConversation(conversationId: string): Promise<{
  conversation: RAGConversation;
  messages: RAGMessage[];
}> {
  const response = await fetch(`${BASE_URL}/rag/conversations/${conversationId}`, {
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '获取对话详情失败');
  }
  return data.data;
}

export async function deleteRAGConversation(conversationId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/rag/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '删除对话失败');
  }
}

export async function quickSearch(params: {
  question: string;
  grade?: string;
  subject?: string;
  top_k?: number;
  min_confidence?: number;
}): Promise<RAGSearchResult[]> {
  const response = await fetch(`${BASE_URL}/rag/quick-search`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(params)
  });

  const data = await response.json();
  if (data.code !== 200) {
    throw new Error(data.message || '快速搜索失败');
  }
  return data.data;
}
