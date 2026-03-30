import React, { useState, useEffect } from 'react';
import { PPTTemplate } from '../types';
import {
  getMyTemplates,
  getPublicTemplates,
  getTemplateCategories,
  deleteTemplate,
  uploadTemplate,
  copyTemplate,
  getTemplateById
} from '../services/api';
import TemplatePreviewModal from './TemplatePreviewModal';
import { TemplateFullPreview } from './templates/TemplateFullPreview';
import './TemplateLibraryPage.css';

export interface TemplateLibraryPageProps {
  onSelectTemplate?: (template: PPTTemplate) => void;
}

export const TemplateLibraryPage: React.FC<TemplateLibraryPageProps> = ({ onSelectTemplate }) => {
  const [activeTab, setActiveTab] = useState<'my' | 'public' | 'favorites'>('my');
  const [templates, setTemplates] = useState<PPTTemplate[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortBy, setSortBy] = useState<'recent' | 'popular' | 'name'>('recent');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<PPTTemplate | null>(null);
  const [fullPreviewTemplate, setFullPreviewTemplate] = useState<PPTTemplate | null>(null);

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [activeTab, selectedCategory, sortBy]);

  const loadCategories = async () => {
    try {
      const data = await getTemplateCategories();
      setCategories(data);
    } catch (error) {
      console.error('加载分类失败:', error);
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      let data: PPTTemplate[] = [];
      
      if (activeTab === 'my') {
        data = await getMyTemplates(selectedCategory || undefined);
      } else if (activeTab === 'public') {
        data = await getPublicTemplates(selectedCategory || undefined);
      } else {
        // favorites - 待实现
        data = await getMyTemplates(selectedCategory || undefined);
      }

      // 应用搜索过滤
      if (searchQuery) {
        data = data.filter(t =>
          t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.description.toLowerCase().includes(searchQuery.toLowerCase())
        );
      }

      // 应用排序
      if (sortBy === 'popular') {
        data.sort((a, b) => b.usageCount - a.usageCount);
      } else if (sortBy === 'name') {
        data.sort((a, b) => a.title.localeCompare(b.title));
      } else {
        data.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      }

      setTemplates(data);
    } catch (error) {
      console.error('加载模板失败:', error);
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
      loadTemplates();
    } catch (error) {
      console.error('上传失败:', error);
      alert('上传失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (templateId: string) => {
    if (!confirm('确定要删除此模板吗？')) return;
    
    try {
      await deleteTemplate(templateId);
      loadTemplates();
    } catch (error) {
      console.error('删除失败:', error);
      alert('删除失败');
    }
  };

  const handleCopy = async (templateId: string) => {
    try {
      await copyTemplate(templateId);
      alert('模板已复制到个人库');
      if (activeTab === 'public') {
        loadTemplates();
      }
    } catch (error) {
      console.error('复制失败:', error);
      alert('复制失败');
    }
  };

  const handlePreview = async (templateId: string) => {
    try {
      const detail = await getTemplateById(templateId);
      if (detail) {
        // 将后端返回的数据结构映射为前端 PPTTemplate 包含 templateData
        const mapped: PPTTemplate = {
          ...detail,
          templateData: {
            slidesStructure: detail.slides_structure || [],
            themeColors: detail.theme_colors || {},
            fonts: detail.fonts || {},
            placeholders: detail.placeholders || {},
          }
        };
        setFullPreviewTemplate(mapped);
      }
    } catch (error) {
      console.error('获取模板详情失败:', error);
      alert('无法加载模板预览');
    }
  };

  const filteredTemplates = templates;

  return (
    <div className="template-library-page">
      {/* 顶部导航 */}
      <div className="library-header">
        <h1>📚 模板库</h1>
        {activeTab === 'my' && (
          <button className="btn-upload" onClick={() => setShowUploadModal(true)}>
            ➕ 上传PPT模板
          </button>
        )}
      </div>

      {/* Tab 导航 */}
      <div className="library-tabs">
        <button
          className={`tab-btn ${activeTab === 'my' ? 'active' : ''}`}
          onClick={() => setActiveTab('my')}
        >
          我的模板
        </button>
        <button
          className={`tab-btn ${activeTab === 'public' ? 'active' : ''}`}
          onClick={() => setActiveTab('public')}
        >
          公共模板
        </button>
        <button
          className={`tab-btn ${activeTab === 'favorites' ? 'active' : ''}`}
          onClick={() => setActiveTab('favorites')}
        >
          ⭐ 收藏
        </button>
      </div>

      {/* 搜索和过滤 */}
      <div className="library-controls">
        <div className="search-bar">
          <input
            type="text"
            placeholder="搜索模板..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          <span className="search-icon">🔍</span>
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

          <div className="category-filter">
            <button
              className={`filter-pill ${selectedCategory === '' ? 'active' : ''}`}
              onClick={() => setSelectedCategory('')}
            >
              全部
            </button>
            {categories.map(cat => (
              <button
                key={cat.id}
                className={`filter-pill ${selectedCategory === cat.id ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat.id)}
              >
                {cat.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 模板网格 */}
      <div className="library-content">
        {loading ? (
          <div className="loading-state">
            <p>加载中...</p>
          </div>
        ) : filteredTemplates.length > 0 ? (
          <div className="template-grid">
            {filteredTemplates.map(template => (
              <div key={template.id} className="template-card-large">
                {/* 缩略图 */}
                <div className="thumbnail-container">
                  {template.thumbnail ? (
                    <img src={template.thumbnail} alt={template.title} />
                  ) : (
                    <div className="placeholder">
                      <span>📄</span>
                    </div>
                  )}
                  
                  {/* 覆盖操作 */}
                  <div className="card-overlay">
                    <div className="card-actions">
                      {activeTab === 'my' && (
                        <>
                          <button className="action-btn preview" title="预览" onClick={() => handlePreview(template.id)}>
                            👁️
                          </button>
                          <button 
                            className="action-btn delete" 
                            title="删除"
                            onClick={() => handleDelete(template.id)}
                          >
                            🗑️
                          </button>
                        </>
                      )}
                      {activeTab === 'public' && (
                        <>
                          <button className="action-btn preview" title="预览" onClick={() => handlePreview(template.id)}>
                            👁️
                          </button>
                          <button 
                            className="action-btn copy" 
                            title="复制到个人库"
                            onClick={() => handleCopy(template.id)}
                          >
                            📋
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* 标签 */}
                  <div className="template-badges">
                    <span className="badge-category">{template.category}</span>
                    {template.visibility === 'public' && (
                      <span className="badge-public">公共</span>
                    )}
                  </div>
                </div>

                {/* 信息区域 */}
                <div className="card-info">
                  <h3>{template.title}</h3>
                  <p className="description">{template.description}</p>
                  
                  <div className="card-meta">
                    <span className="usage">
                      {template.usageCount > 0 ? `${template.usageCount}x` : '新'}
                    </span>
                    <span className="date">
                      {new Date(template.createdAt).toLocaleDateString('zh-CN')}
                    </span>
                  </div>
                </div>

                {/* 快速操作 */}
                <div className="card-footer">
                  {activeTab === 'my' && (
                    <button 
                      className="btn-small btn-primary"
                      onClick={() => onSelectTemplate?.(template)}
                    >
                      使用模板
                    </button>
                  )}
                  {activeTab === 'public' && (
                    <>
                      <button className="btn-small btn-secondary" onClick={() => handlePreview(template.id)}>预览</button>
                      <button 
                        className="btn-small btn-primary"
                        onClick={() => onSelectTemplate?.(template)}
                      >
                        使用
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>📭</p>
            <p>暂无模板</p>
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

      {/* 上传模态框 */}
      {showUploadModal && (
        <UploadTemplateModal
          onClose={() => setShowUploadModal(false)}
          onUpload={handleUpload}
          loading={uploading}
        />
      )}

      {/* 模板全页面预览 */}
      {fullPreviewTemplate && (
        <TemplateFullPreview
          template={fullPreviewTemplate}
          onClose={() => setFullPreviewTemplate(null)}
        />
      )}

      {/* 模板预览弹框 (保留作为快速查看，或在需要时切换) */}
      {previewTemplate && (
        <TemplatePreviewModal
          template={previewTemplate}
          onClose={() => setPreviewTemplate(null)}
        />
      )}
    </div>
  );
};

// 上传模态框组件
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) {
      alert('请填写所有必需字段');
      return;
    }
    onUpload(file, title, description, visibility);
  };

  return (
    <div className="upload-modal-overlay" onClick={onClose}>
      <div className="upload-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>上传PPT模板</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="upload-form">
          {/* 文件选择 */}
          <div className="form-group">
            <label>PPT文件 *</label>
            <div className="file-input-wrapper">
              <input
                type="file"
                accept=".pptx"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                disabled={loading}
              />
              <span>{file?.name || '选择 .pptx 文件'}</span>
            </div>
          </div>

          {/* 标题 */}
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

          {/* 描述 */}
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

          {/* 可见范围 */}
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
                <span>个人专用（仅自己可见）</span>
              </label>
              <label className="radio-option">
                <input
                  type="radio"
                  value="public"
                  checked={visibility === 'public'}
                  onChange={(e) => setVisibility(e.target.value as any)}
                  disabled={loading}
                />
                <span>公共模板（所有用户可见）</span>
              </label>
            </div>
          </div>

          {/* 按钮 */}
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
              disabled={loading || !file}
            >
              {loading ? '上传中...' : '上传模板'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TemplateLibraryPage;
