import React, { useState } from 'react';
import { saveCoursewareAsTemplate } from '../services/api';
import './SaveAsTemplateModal.css';

interface SaveAsTemplateModalProps {
  coursewareId: string;
  coursewareTitle?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export const SaveAsTemplateModal: React.FC<SaveAsTemplateModalProps> = ({
  coursewareId,
  coursewareTitle,
  onClose,
  onSuccess
}) => {
  const [title, setTitle] = useState(coursewareTitle || '');
  const [description, setDescription] = useState('');
  const [visibility, setVisibility] = useState<'private' | 'public'>('private');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!title.trim()) {
      setError('模板标题不能为空');
      return;
    }

    setLoading(true);
    try {
      await saveCoursewareAsTemplate(coursewareId, title, description, visibility);
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="save-template-overlay" onClick={onClose}>
      <div className="save-template-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>💾 保存为模板</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="save-form">
          {error && (
            <div className="error-message">
              ⚠️ {error}
            </div>
          )}

          {/* 模板标题 */}
          <div className="form-group">
            <label>模板标题 *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="为这个模板取个名字"
              disabled={loading}
              autoFocus
            />
          </div>

          {/* 描述 */}
          <div className="form-group">
            <label>模板描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述这个模板的特点、适用场景等"
              rows={3}
              disabled={loading}
            />
          </div>

          {/* 可见范围 */}
          <div className="form-group">
            <label>可见范围</label>
            <div className="visibility-options">
              <label className="radio-label">
                <input
                  type="radio"
                  value="private"
                  checked={visibility === 'private'}
                  onChange={(e) => setVisibility(e.target.value as any)}
                  disabled={loading}
                />
                <div>
                  <strong>🔒 个人专用</strong>
                  <p>仅自己可见和使用</p>
                </div>
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  value="public"
                  checked={visibility === 'public'}
                  onChange={(e) => setVisibility(e.target.value as any)}
                  disabled={loading}
                />
                <div>
                  <strong>🌍 公共模板</strong>
                  <p>所有用户可见，他人可复制到个人库</p>
                </div>
              </label>
            </div>
          </div>

          {/* 信息提示 */}
          <div className="info-box">
            <p>💡 <strong>提示：</strong></p>
            <ul>
              <li>保存的模板将包含当前课件的完整结构和样式</li>
              <li>其他用户可以基于此模板生成相似风格的新课件</li>
              <li>你随时可以在模板库中修改或删除此模板</li>
            </ul>
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
              disabled={loading || !title.trim()}
            >
              {loading ? '保存中...' : '保存为模板'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SaveAsTemplateModal;
