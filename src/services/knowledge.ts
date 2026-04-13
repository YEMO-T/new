/**
 * 知识库管理 API - 支持上传、向量化、搜索
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

// ============================================================
// 知识库管理接口
// ============================================================

/**
 * 获取用户的知识库列表
 */
export async function getKnowledgeList() {
  try {
    const response = await fetch(`${BASE_URL}/knowledge`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) return [];
    return response.json();
  } catch (error) {
    console.error('获取知识库列表失败:', error);
    return [];
  }
}

/**
 * 上传知识库文件并自动触发向量化
 * @param file 文件对象
 * @param name 资源名称
 * @param grade 年级
 * @param subject 学科
 */
export async function uploadKnowledgeFile(
  file: File,
  name?: string,
  grade?: string,
  subject?: string
) {
  try {
    // 1. 读取文件内容
    const content = await file.text();
    
    if (!content.trim()) {
      throw new Error('文件内容为空');
    }

    // 2. 上传知识库条目
    const uploadData = {
      name: name || file.name.replace(/\.[^/.]+$/, ''),
      type: 'txt',
      size: `${(file.size / 1024).toFixed(2)} KB`,
      tags: [grade || '未分类', subject || '通用'],
      content: content,
      grade_level: grade,
      subject: subject
    };

    const uploadResponse = await fetch(`${BASE_URL}/knowledge/upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(uploadData)
    });

    if (!uploadResponse.ok) {
      throw new Error('上传失败');
    }

    const uploadResult = await uploadResponse.json();
    const itemId = uploadResult.data?.[0]?.id;

    if (!itemId) {
      throw new Error('获取条目ID失败');
    }

    console.log('✅ 知识库条目上传成功:', itemId);

    // 3. 自动触发向量化
    return await vectorizeKnowledgeItem(itemId);

  } catch (error) {
    console.error('上传知识库失败:', error);
    throw error;
  }
}

/**
 * 手动触发单个条目的向量化
 * @param itemId 知识库条目ID
 */
export async function vectorizeKnowledgeItem(itemId: string) {
  try {
    const response = await fetch(`${BASE_URL}/knowledge/vectorize-item?item_id=${itemId}`, {
      method: 'POST',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('向量化失败');
    }

    const result = await response.json();
    console.log('✅ 向量化完成:', result);
    return result;

  } catch (error) {
    console.error('向量化失败:', error);
    throw error;
  }
}

/**
 * 获取条目的向量化状态
 * @param itemId 知识库条目ID
 */
export async function getVectorizationStatus(itemId: string) {
  try {
    const response = await fetch(`${BASE_URL}/knowledge/vectorization-status/${itemId}`, {
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('获取状态失败');
    }

    return response.json();

  } catch (error) {
    console.error('获取向量化状态失败:', error);
    throw error;
  }
}

/**
 * 执行RAG搜索
 * @param query 查询文本
 * @param grade 年级（可选）
 * @param subject 学科（可选）
 * @param topK 返回结果数
 * @param minConfidence 最小置信度
 */
export async function searchRAG(
  query: string,
  grade?: string,
  subject?: string,
  topK: number = 5,
  minConfidence: number = 0.5
) {
  try {
    const params = new URLSearchParams({
      query,
      top_k: topK.toString(),
      min_confidence: minConfidence.toString()
    });

    if (grade) params.append('grade', grade);
    if (subject) params.append('subject', subject);

    const response = await fetch(`${BASE_URL}/knowledge/search-rag?${params}`, {
      method: 'POST',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('搜索失败');
    }

    return response.json();

  } catch (error) {
    console.error('RAG搜索失败:', error);
    throw error;
  }
}

/**
 * 删除知识库条目
 * @param itemId 知识库条目ID
 */
export async function deleteKnowledgeItem(itemId: string) {
  try {
    const response = await fetch(`${BASE_URL}/knowledge/${itemId}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('删除失败');
    }

    return response.json();

  } catch (error) {
    console.error('删除知识库失败:', error);
    throw error;
  }
}

/**
 * 获取搜索历史
 * @param limit 返回记录数
 */
export async function getSearchHistory(limit: number = 20) {
  try {
    const response = await fetch(`${BASE_URL}/knowledge/search-history?limit=${limit}`, {
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('获取搜索历史失败');
    }

    return response.json();

  } catch (error) {
    console.error('获取搜索历史失败:', error);
    throw error;
  }
}

/**
 * 获取公开教学资源
 * @param grade 年级
 * @param subject 学科
 * @param resourceType 资源类型
 */
export async function getTeachingResources(
  grade?: string,
  subject?: string,
  resourceType?: string
) {
  try {
    const params = new URLSearchParams();
    if (grade) params.append('grade', grade);
    if (subject) params.append('subject', subject);
    if (resourceType) params.append('resource_type', resourceType);

    const response = await fetch(`${BASE_URL}/knowledge/resources?${params}`, {
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('获取资源失败');
    }

    return response.json();

  } catch (error) {
    console.error('获取教学资源失败:', error);
    throw error;
  }
}

/**
 * 获取知识库文件的下载链接
 * @param itemId 知识库条目ID
 */
export async function getKnowledgeDownloadUrl(itemId: string) {
  try {
    const response = await fetch(`${BASE_URL}/knowledge/${itemId}/download`, {
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('获取下载链接失败');
    }

    return response.json();
  } catch (error) {
    console.error('获取下载链接失败:', error);
    throw error;
  }
}

/**
 * 上传知识库文件 (使用 FormData，支持原始文件存储)
 * @param file 文件对象
 * @param metadata 元数据
 */
export async function uploadKnowledgeFileV2(
  file: File,
  metadata: {
    name?: string;
    visibility?: string;
    grade_level?: string;
    subject?: string;
    description?: string;
    education_level?: string;
    resource_type?: string;
    difficulty?: string;
    semester?: string;
    chapter?: string;
    tags?: string;
  }
) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    if (metadata.name) formData.append('name', metadata.name);
    if (metadata.visibility) formData.append('visibility', metadata.visibility);
    if (metadata.grade_level) formData.append('grade_level', metadata.grade_level);
    if (metadata.subject) formData.append('subject', metadata.subject);
    if (metadata.description) formData.append('description', metadata.description);
    if (metadata.education_level) formData.append('education_level', metadata.education_level);
    if (metadata.resource_type) formData.append('resource_type', metadata.resource_type);
    if (metadata.difficulty) formData.append('difficulty', metadata.difficulty);
    if (metadata.semester) formData.append('semester', metadata.semester);
    if (metadata.chapter) formData.append('chapter', metadata.chapter);
    if (metadata.tags) formData.append('tags', metadata.tags);

    const response = await fetch(`${BASE_URL}/knowledge/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      },
      body: formData
    });

    if (!response.ok) {
      throw new Error('上传失败');
    }

    return response.json();
  } catch (error) {
    console.error('上传知识库失败:', error);
    throw error;
  }
}
