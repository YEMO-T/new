import React, { useState, useEffect } from 'react';
import { PPTTemplate } from '../types';
import { getMyTemplates, getPublicTemplates, getTemplateCategories } from '../services/api';
import './TemplateSelector.css';

interface TemplateSelectorProps {
  onSelect: (templateId: string) => void;
  onSkip: () => void;
}

export const TemplateSelector: React.FC<TemplateSelectorProps> = ({ onSelect, onSkip }) => {
  const [templates, setTemplates] = useState<PPTTemplate[]>([]);
  const [activeTab, setActiveTab] = useState<'my' | 'public'>('my');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [activeTab, selectedCategory]);

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
      let data;
      if (activeTab === 'my') {
        data = await getMyTemplates(selectedCategory || undefined);
      } else {
        data = await getPublicTemplates(selectedCategory || undefined);
      }
      setTemplates(data || []);
      setSelectedId(null);
    } catch (error) {
      console.error('加载模板失败:', error);
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="template-selector-modal">
      <div className="template-selector-overlay" onClick={onSkip}></div>
      
      <div className="template-selector-content">
        <div className="template-selector-header">
          <h2>📋 选择PPT模板风格</h2>
          <button className="close-btn" onClick={onSkip}>✕</button>
        </div>

        <div className="template-selector-body">
          {/* Tab 切换 */}
          <div className="template-tabs">
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
          </div>

          {/* 分类过滤 */}
          <div className="template-filters">
            <button
              className={`filter-btn ${selectedCategory === '' ? 'active' : ''}`}
              onClick={() => setSelectedCategory('')}
            >
              全部
            </button>
            {categories.map(cat => (
              <button
                key={cat.id}
                className={`filter-btn ${selectedCategory === cat.id ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat.id)}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* 模板列表 */}
          <div className="template-grid">
            {loading ? (
              <div className="loading">加载中...</div>
            ) : templates.length > 0 ? (
              templates.map(template => (
                <div
                  key={template.id}
                  className={`template-card ${selectedId === template.id ? 'selected' : ''}`}
                  onClick={() => setSelectedId(template.id)}
                >
                  <div className="template-thumbnail">
                    {template.thumbnail ? (
                      <img src={template.thumbnail} alt={template.title} />
                    ) : (
                      <div className="placeholder">无缩略图</div>
                    )}
                  </div>
                  <div className="template-info">
                    <h4>{template.title}</h4>
                    <p className="description">{template.description}</p>
                    <div className="meta">
                      <span className="category">{template.category}</span>
                      <span className="usage">
                        {template.usageCount > 0 ? `已用 ${template.usageCount} 次` : '未使用'}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state">
                <p>暂无模板</p>
              </div>
            )}
          </div>
        </div>

        {/* 底部操作 */}
        <div className="template-selector-footer">
          <button className="btn btn-secondary" onClick={onSkip}>
            不使用模板
          </button>
          <button
            className="btn btn-primary"
            disabled={!selectedId}
            onClick={() => selectedId && onSelect(selectedId)}
          >
            使用此模板
          </button>
        </div>
      </div>
    </div>
  );
};

export default TemplateSelector;
