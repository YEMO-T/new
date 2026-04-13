import React, { useState, useEffect } from 'react';
import { PPTTemplate } from '../types';
import {
  getPptTemplateList,
  getPptTemplateById,
  deletePptTemplate,
  copyPptTemplate,
  uploadTemplate,
  getTemplateCategories
} from '../services/api';
import { PPTSlidePreview } from './PPTSlidePreview';
import { SupabaseImage } from './SupabaseImage';
import './TemplateLibraryPage.css';

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

export interface TemplateLibraryPageProps {
  onSelectTemplate?: (template: PPTTemplate) => void;
}

export const TemplateLibraryPage: React.FC<TemplateLibraryPageProps> = ({ onSelectTemplate }) => {
  const [activeTab, setActiveTab] = useState<'my' | 'public'>('my');
  const [templates, setTemplates] = useState<PPTTemplate[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortBy, setSortBy] = useState<'recent' | 'popular' | 'name'>('recent');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<PPTTemplate | null>(null);
  const [showSlidePreview, setShowSlidePreview] = useState(false);
  const [totalTemplates, setTotalTemplates] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [activeTab, currentPage]);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const loadCategories = async () => {
    try {
      const data = await getTemplateCategories();
      setCategories(data);
    } catch (error) {
      console.error('加载分类失败:', error);
    }
  };

  const [retryCount, setRetryCount] = useState(0);

  const loadTemplates = async (retryAttempt = 0) => {
    setLoading(true);
    try {
      const templateType = activeTab === 'my' ? 'personal' : 'public';
      const result = await getPptTemplateList(templateType, currentPage, 20);
      
      let data: PPTTemplate[] = result.templates.map((t: any) => ({
        id: t.id,
        user_id: t.user_id,
        title: t.title || '',
        description: t.description || '',
        category: t.category || '',
        visibility: t.visibility || 'private',
        thumbnail: t.thumbnail_url,
        usageCount: t.usage_count || 0,
        createdAt: t.created_at,
        updatedAt: t.updated_at,
        originalFileName: t.original_file_name,
        originalFileSize: t.original_file_size,
        templateData: {
          slidesStructure: t.slides_structure || [],
          themeColors: t.theme_colors || {},
          fonts: t.fonts || {},
          placeholders: t.placeholders || {},
        },
        themeColors: t.theme_colors,
        fonts: t.fonts,
        has_original_file: t.has_original_file || false,
        file_path: t.file_path,
        file_bucket: t.file_bucket,
      }));

      if (searchQuery) {
        data = data.filter(t =>
          t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.description.toLowerCase().includes(searchQuery.toLowerCase())
        );
      }

      if (sortBy === 'popular') {
        data.sort((a, b) => b.usageCount - a.usageCount);
      } else if (sortBy === 'name') {
        data.sort((a, b) => a.title.localeCompare(b.title));
      }

      setTemplates(data);
      setTotalTemplates(result.total);
      setRetryCount(0);
    } catch (error: any) {
      console.error('加载模板失败:', error);
      
      const isConnectionError = error?.message?.includes('10054') || 
                                error?.message?.includes('连接') ||
                                error?.message?.includes('timeout');
      
      if (isConnectionError && retryAttempt < 3) {
        showToast(`连接失败，正在重试 (${retryAttempt + 1}/3)...`, 'error');
        setTimeout(() => loadTemplates(retryAttempt + 1), 2000 * (retryAttempt + 1));
        return;
      }
      
      showToast('加载模板失败，请稍后重试', 'error');
      setRetryCount(retryAttempt + 1);
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file: File, title: string, description: string, visibility: 'private' | 'public') => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', title);
      formData.append('description', description);
      formData.append('category', '');
      formData.append('visibility', visibility);

      await uploadTemplate(formData);
      setShowUploadModal(false);
      showToast('模板上传成功！');
      loadTemplates();
    } catch (error) {
      console.error('上传失败:', error);
      showToast('上传失败: ' + (error instanceof Error ? error.message : '未知错误'), 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (templateId: string) => {
    if (deleteConfirm !== templateId) {
      setDeleteConfirm(templateId);
      setTimeout(() => setDeleteConfirm(null), 3000);
      return;
    }
    
    try {
      await deletePptTemplate(templateId);
      showToast('模板已删除');
      loadTemplates();
    } catch (error) {
      console.error('删除失败:', error);
      showToast('删除失败: ' + (error instanceof Error ? error.message : '未知错误'), 'error');
    }
    setDeleteConfirm(null);
  };

  const handleCopy = async (templateId: string) => {
    try {
      await copyPptTemplate(templateId);
      showToast('模板已复制到个人库');
    } catch (error) {
      console.error('复制失败:', error);
      showToast('复制失败: ' + (error instanceof Error ? error.message : '未知错误'), 'error');
    }
  };

  const handlePreview = async (templateId: string) => {
    try {
      const detail = await getPptTemplateById(templateId);
      if (detail) {
        const mapped: PPTTemplate = {
          ...detail,
          templateData: {
            slidesStructure: detail.slides_structure || [],
            themeColors: detail.theme_colors || {},
            fonts: detail.fonts || {},
            placeholders: detail.placeholders || {},
          }
        };
        setPreviewTemplate(mapped);
      }
    } catch (error) {
      console.error('获取模板详情失败:', error);
      showToast('无法加载模板预览', 'error');
    }
  };

  const handleDownload = (templateId: string, fileName: string) => {
    const token = localStorage.getItem('auth_token');
    const url = `${BASE_URL}/ppt-templates/${templateId}/download?token=${encodeURIComponent(token || '')}`;
    
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName || 'template.pptx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('开始下载...');
  };

  const handlePreviewFile = (template: PPTTemplate) => {
    setPreviewTemplate(template);
    setShowSlidePreview(true);
  };

  return (
    <div className="template-library-page">
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}

      <div className="library-header">
        <h1>📚 模板库</h1>
        {activeTab === 'my' && (
          <button className="btn-upload" onClick={() => setShowUploadModal(true)}>
            ➕ 上传PPT模板
          </button>
        )}
      </div>

      <div className="library-tabs">
        <button
          className={`tab-btn ${activeTab === 'my' ? 'active' : ''}`}
          onClick={() => { setActiveTab('my'); setCurrentPage(1); }}
        >
          我的模板 ({activeTab === 'my' ? totalTemplates : ''})
        </button>
        <button
          className={`tab-btn ${activeTab === 'public' ? 'active' : ''}`}
          onClick={() => { setActiveTab('public'); setCurrentPage(1); }}
        >
          公共模板 ({activeTab === 'public' ? totalTemplates : ''})
        </button>
      </div>

      <div className="library-controls">
        <div className="search-bar">
          <input
            type="text"
            placeholder="搜索模板..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && loadTemplates()}
            className="search-input"
          />
          <button className="search-btn" onClick={loadTemplates}>🔍</button>
        </div>

        <div className="filters">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="sort-select"
          >
            <option value="recent">最新</option>
            <option value="popular">最热</option>
            <option value="name">名称</option>
          </select>
        </div>
      </div>

      <div className="library-content">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>加载中...</p>
          </div>
        ) : templates.length > 0 ? (
          <>
            <div className="template-grid">
              {templates.map(template => (
                <div key={template.id} className="template-card-large">
                  <div className="thumbnail-container">
                    <SupabaseImage
                      src={template.thumbnail}
                      alt={template.title}
                      templateId={template.id}
                      className="template-thumbnail"
                      fallback={
                        <div className="placeholder">
                          <span>📄</span>
                          <span className="file-name">{template.originalFileName || 'PPT模板'}</span>
                        </div>
                      }
                    />
                    
                    <div className="card-overlay">
                      <div className="card-actions">
                        <button 
                          className="action-btn preview" 
                          title="预览PPT"
                          onClick={() => handlePreviewFile(template)}
                        >
                          👁️
                        </button>
                        <button 
                          className="action-btn download" 
                          title="下载PPT"
                          onClick={() => handleDownload(template.id, template.originalFileName || 'template.pptx')}
                        >
                          ⬇️
                        </button>
                        {activeTab === 'my' && (
                          <button 
                            className={`action-btn delete ${deleteConfirm === template.id ? 'confirm' : ''}`} 
                            title={deleteConfirm === template.id ? '再次确认删除' : '删除'}
                            onClick={() => handleDelete(template.id)}
                          >
                            🗑️
                          </button>
                        )}
                        {activeTab === 'public' && (
                          <button 
                            className="action-btn copy" 
                            title="复制到个人库"
                            onClick={() => handleCopy(template.id)}
                          >
                            📋
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="template-badges">
                      {template.category && (
                        <span className="badge-category">{template.category}</span>
                      )}
                      {template.visibility === 'public' && (
                        <span className="badge-public">公共</span>
                      )}
                    </div>
                  </div>

                  <div className="card-info">
                    <h3 title={template.title}>{template.title}</h3>
                    <p className="description" title={template.description}>{template.description || '暂无描述'}</p>
                    
                    <div className="card-meta">
                      <span className="usage">
                        {template.usageCount > 0 ? `${template.usageCount} 次使用` : '新模板'}
                      </span>
                      <span className="date">
                        {template.createdAt ? new Date(template.createdAt).toLocaleDateString('zh-CN') : ''}
                      </span>
                    </div>

                    {template.originalFileSize && (
                      <div className="file-size">
                        文件大小: {template.originalFileSize}
                      </div>
                    )}
                  </div>

                  <div className="card-footer">
                    <button 
                      className="btn-small btn-secondary"
                      onClick={() => handlePreviewFile(template)}
                    >
                      预览
                    </button>
                    <button 
                      className="btn-small btn-primary"
                      onClick={() => onSelectTemplate?.(template)}
                    >
                      使用模板
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {totalTemplates > 20 && (
              <div className="pagination">
                <button 
                  className="page-btn"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(p => p - 1)}
                >
                  上一页
                </button>
                <span className="page-info">
                  第 {currentPage} 页 / 共 {Math.ceil(totalTemplates / 20)} 页
                </span>
                <button 
                  className="page-btn"
                  disabled={currentPage * 20 >= totalTemplates}
                  onClick={() => setCurrentPage(p => p + 1)}
                >
                  下一页
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">
            <p className="empty-icon">📭</p>
            <p className="empty-text">
              {activeTab === 'my' ? '您还没有上传任何模板' : '暂无公共模板'}
            </p>
            {activeTab === 'my' && (
              <button 
                className="btn btn-primary"
                onClick={() => setShowUploadModal(true)}
              >
                上传你的第一个模板
              </button>
            )}
          </div>
        )}
      </div>

      {showUploadModal && (
        <UploadTemplateModal
          onClose={() => setShowUploadModal(false)}
          onUpload={handleUpload}
          loading={uploading}
        />
      )}

      {previewTemplate && (
        <TemplatePreviewModal
          template={previewTemplate}
          onClose={() => setPreviewTemplate(null)}
        />
      )}

      {showSlidePreview && previewTemplate && (
        <PPTSlidePreview
          templateId={previewTemplate.id}
          token={localStorage.getItem('auth_token') || ''}
          title={previewTemplate.title || previewTemplate.originalFileName || 'PPT预览'}
          templateData={{
            slidesStructure: previewTemplate.templateData?.slidesStructure || [],
            themeColors: previewTemplate.themeColors || previewTemplate.templateData?.themeColors || {},
            fonts: previewTemplate.fonts || previewTemplate.templateData?.fonts || {},
          }}
          onClose={() => {
            setShowSlidePreview(false);
            setPreviewTemplate(null);
          }}
        />
      )}
    </div>
  );
};

interface UploadTemplateModalProps {
  onClose: () => void;
  onUpload: (file: File, title: string, description: string, visibility: 'private' | 'public') => void;
  loading: boolean;
}

const UploadTemplateModal: React.FC<UploadTemplateModalProps> = ({
  onClose,
  onUpload,
  loading
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [visibility, setVisibility] = useState<'private' | 'public'>('private');
  const [dragOver, setDragOver] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) {
      alert('请填写所有必需字段');
      return;
    }
    onUpload(file, title, description, visibility);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.toLowerCase().endsWith('.pptx')) {
      setFile(droppedFile);
      if (!title) {
        setTitle(droppedFile.name.replace('.pptx', ''));
      }
    }
  };

  return (
    <div className="upload-modal-overlay" onClick={onClose}>
      <div className="upload-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>上传PPT模板</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="upload-form">
          <div className="form-group">
            <label>PPT文件 *</label>
            <div 
              className={`file-input-wrapper ${dragOver ? 'drag-over' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <input
                type="file"
                accept=".pptx"
                onChange={(e) => {
                  const selectedFile = e.target.files?.[0];
                  setFile(selectedFile || null);
                  if (selectedFile && !title) {
                    setTitle(selectedFile.name.replace('.pptx', ''));
                  }
                }}
                disabled={loading}
              />
              <span className="file-display">
                {file ? (
                  <>
                    <span className="file-icon">📄</span>
                    {file.name}
                    <span className="file-size">({(file.size / 1024).toFixed(1)} KB)</span>
                  </>
                ) : '点击或拖拽 .pptx 文件到此处'}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label>模板标题 *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="如：蓝色简约风格"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述这个模板的特点和适用场景"
              rows={3}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>可见范围</label>
            <div className="radio-group">
              <label className="radio-option">
                <input
                  type="radio"
                  value="private"
                  checked={visibility === 'private'}
                  onChange={(e) => setVisibility(e.target.value as any)}
                  disabled={loading}
                />
                <span>🔒 个人专用（仅自己可见）</span>
              </label>
              <label className="radio-option">
                <input
                  type="radio"
                  value="public"
                  checked={visibility === 'public'}
                  onChange={(e) => setVisibility(e.target.value as any)}
                  disabled={loading}
                />
                <span>🌐 公共模板（所有用户可见）</span>
              </label>
            </div>
          </div>

          <div className="form-actions">
            <button 
              type="button" 
              className="btn btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              取消
            </button>
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={loading || !file || !title}
            >
              {loading ? '上传中...' : '上传模板'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface TemplatePreviewModalProps {
  template: PPTTemplate;
  onClose: () => void;
}

const TemplatePreviewModal: React.FC<TemplatePreviewModalProps> = ({ template, onClose }) => {
  return (
    <div className="preview-modal-overlay" onClick={onClose}>
      <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{template.title}</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="preview-content">
          <div className="preview-info">
            <p><strong>描述：</strong>{template.description || '暂无描述'}</p>
            <p><strong>分类：</strong>{template.category || '未分类'}</p>
            <p><strong>使用次数：</strong>{template.usageCount || 0}</p>
            <p><strong>创建时间：</strong>{template.createdAt ? new Date(template.createdAt).toLocaleString('zh-CN') : ''}</p>
          </div>
          <div className="preview-actions">
            <button className="btn btn-secondary" onClick={onClose}>关闭</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TemplateLibraryPage;
