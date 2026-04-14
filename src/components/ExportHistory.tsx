import React, { useState, useEffect, useCallback } from 'react';
import { getExports, deleteExport } from '../services/api';
import './ExportHistory.css';

interface ExportRecord {
  id: string;
  title: string;
  format: string;
  size: string;
  file_url?: string;
  created_at: string;
}

interface ExportHistoryProps {
  isOpen: boolean;
  onClose: () => void;
  onDownload?: (exportId: string) => void;
}

const ExportHistory: React.FC<ExportHistoryProps> = ({ isOpen, onClose, onDownload }) => {
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadExports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getExports();
      if (Array.isArray(response)) {
        setExports(response);
        setTotalPages(1);
      } else if (response.data && Array.isArray(response.data.records)) {
        setExports(response.data.records);
        setTotalPages(response.data.total_pages || 1);
      }
    } catch (err) {
      setError('加载导出记录失败，请稍后重试');
      console.error('加载导出记录失败:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadExports();
    }
  }, [isOpen, loadExports]);

  const handleDelete = async (exportId: string) => {
    if (!window.confirm('确定要删除这条导出记录吗？')) return;

    try {
      await deleteExport(exportId);
      setExports(exports.filter(exp => exp.id !== exportId));
      setSelectedIds(selectedIds.filter(id => id !== exportId));
    } catch (err) {
      console.error('删除失败:', err);
      alert('删除失败，请稍后重试');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.length === 0) {
      alert('请先选择要删除的记录');
      return;
    }

    if (!window.confirm(`确定要删除选中的 ${selectedIds.length} 条记录吗？`)) return;

    try {
      for (const id of selectedIds) {
        await deleteExport(id);
      }
      setExports(exports.filter(exp => !selectedIds.includes(exp.id)));
      setSelectedIds([]);
      alert(`成功删除 ${selectedIds.length} 条记录`);
    } catch (err) {
      console.error('批量删除失败:', err);
      alert('部分或全部删除失败，请稍后重试');
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.length === exports.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(exports.map(exp => exp.id));
    }
  };

  const handleSelectOne = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(sid => sid !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleDownload = async (record: ExportRecord) => {
    if (!record.file_url) {
      alert('该文件没有可用的下载链接');
      return;
    }

    setDownloadingId(record.id);

    try {
      const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';
      const downloadUrl = `${BASE_URL}/exports/${record.id}/download`;
      
      const token = localStorage.getItem('auth_token');
      const response = await fetch(downloadUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error(`下载失败 (${response.status})`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${record.title}.${record.format.toLowerCase()}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      if (onDownload) {
        onDownload(record.id);
      }
    } catch (err) {
      console.error('下载失败:', err);
      alert('下载失败，请检查网络连接或稍后重试');
    } finally {
      setDownloadingId(null);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  const getFormatIcon = (format: string) => {
    switch (format.toLowerCase()) {
      case 'pptx':
        return '📊';
      case 'docx':
        return '📝';
      case 'pdf':
        return '📄';
      default:
        return '📁';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="export-history-overlay" onClick={onClose}>
      <div className="export-history-modal" onClick={(e) => e.stopPropagation()}>
        <div className="export-history-header">
          <h2>📥 导出记录</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="export-history-toolbar">
          <div className="toolbar-left">
            <label className="select-all">
              <input
                type="checkbox"
                checked={selectedIds.length === exports.length && exports.length > 0}
                onChange={handleSelectAll}
              />
              全选
            </label>
            {selectedIds.length > 0 && (
              <button
                className="btn btn-danger"
                onClick={handleBatchDelete}
              >
                🗑️ 删除选中 ({selectedIds.length})
              </button>
            )}
          </div>
          <div className="toolbar-right">
            <button className="btn btn-primary" onClick={loadExports}>
              🔄 刷新
            </button>
          </div>
        </div>

        {error && (
          <div className="export-error">
            ⚠️ {error}
            <button onClick={loadExports}>重试</button>
          </div>
        )}

        {loading ? (
          <div className="export-loading">
            <div className="spinner"></div>
            <p>加载中...</p>
          </div>
        ) : exports.length === 0 ? (
          <div className="export-empty">
            <div className="empty-icon">📭</div>
            <p>暂无导出记录</p>
            <p className="empty-hint">生成并下载PPT后，记录会显示在这里</p>
          </div>
        ) : (
          <>
            <div className="export-list">
              <table>
                <thead>
                  <tr>
                    <th className="col-checkbox"></th>
                    <th className="col-title">文件名</th>
                    <th className="col-format">格式</th>
                    <th className="col-size">大小</th>
                    <th className="col-time">导出时间</th>
                    <th className="col-actions">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {exports.map((record) => (
                    <tr key={record.id} className={selectedIds.includes(record.id) ? 'selected' : ''}>
                      <td className="col-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(record.id)}
                          onChange={() => handleSelectOne(record.id)}
                        />
                      </td>
                      <td className="col-title">
                        <span className="title-text">{record.title}</span>
                      </td>
                      <td className="col-format">
                        <span className="format-badge">
                          {getFormatIcon(record.format)} {record.format.toUpperCase()}
                        </span>
                      </td>
                      <td className="col-size">{record.size || '-'}</td>
                      <td className="col-time">{formatDate(record.created_at)}</td>
                      <td className="col-actions">
                        <button
                          className="btn btn-download"
                          onClick={() => handleDownload(record)}
                          disabled={downloadingId === record.id || !record.file_url}
                          title="重新下载"
                        >
                          {downloadingId === record.id ? '⏳' : '⬇️'}
                        </button>
                        <button
                          className="btn btn-delete"
                          onClick={() => handleDelete(record.id)}
                          title="删除记录"
                        >
                          🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  ‹ 上一页
                </button>
                <span className="page-info">
                  第 {page} / {totalPages} 页
                </span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  下一页 ›
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default ExportHistory;