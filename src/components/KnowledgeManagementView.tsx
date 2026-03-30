import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Upload, FileText, Trash2, Search, Loader, CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils';
import { uploadKnowledgeFile, getKnowledgeList, deleteKnowledgeItem, searchRAG } from '../../services/knowledge';

interface KnowledgeItem {
  id: string;
  name: string;
  type: string;
  size: string;
  tags: string[];
  vector_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number;
}

interface SearchResult {
  content: string;
  source_resource: string;
  page_number: number;
  confidence_score: number;
  chunk_index: number;
}

export const KnowledgeManagementView = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedGrade, setSelectedGrade] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('');
  const [showSearchResults, setShowSearchResults] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadKnowledgeItems();
  }, []);

  const loadKnowledgeItems = async () => {
    try {
      setIsLoading(true);
      const data = await getKnowledgeList();
      setItems(data || []);
    } catch (error) {
      console.error('加载知识库失败:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const fileId = `${file.name}-${Date.now()}`;

      try {
        setIsUploading(true);
        setUploadProgress(prev => ({ ...prev, [fileId]: 0 }));

        const progressInterval = setInterval(() => {
          setUploadProgress(prev => {
            const current = prev[fileId] || 0;
            if (current >= 90) {
              clearInterval(progressInterval);
              return prev;
            }
            return { ...prev, [fileId]: current + Math.random() * 30 };
          });
        }, 300);

        await uploadKnowledgeFile(file, file.name.replace(/\.[^/.]+$/, ''), selectedGrade, selectedSubject);

        clearInterval(progressInterval);
        setUploadProgress(prev => ({ ...prev, [fileId]: 100 }));
        await loadKnowledgeItems();

        setTimeout(() => {
          setUploadProgress(prev => {
            const newProgress = { ...prev };
            delete newProgress[fileId];
            return newProgress;
          });
        }, 2000);
      } catch (error) {
        console.error('上传失败:', error);
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[fileId];
          return newProgress;
        });
      }
    }

    setIsUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (itemId: string) => {
    if (!confirm('确定要删除吗？')) return;
    try {
      await deleteKnowledgeItem(itemId);
      setItems(items.filter(item => item.id !== itemId));
    } catch (error) {
      alert('删除失败');
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      setIsSearching(true);
      const result = await searchRAG(searchQuery, selectedGrade || undefined, selectedSubject || undefined, 5, 0.5);
      setSearchResults(result.data || []);
      setShowSearchResults(true);
    } catch (error) {
      alert('搜索失败');
    } finally {
      setIsSearching(false);
    }
  };

  const getStatusText = (status: string, chunkCount: number) => {
    const statusMap: { [key: string]: string } = {
      'pending': '待处理',
      'processing': '处理中...',
      'completed': `已完成 (${chunkCount} 块)`,
      'failed': '处理失败'
    };
    return statusMap[status] || '未知';
  };

  const getStatusColor = (status: string) => {
    const colorMap: { [key: string]: string } = {
      'pending': 'text-yellow-500',
      'processing': 'text-blue-500',
      'completed': 'text-green-500',
      'failed': 'text-red-500'
    };
    return colorMap[status] || 'text-gray-500';
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="bg-white border-b border-slate-200 p-6 shadow-sm">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">📚 知识库管理</h1>
        <p className="text-slate-600">上传文件 → 自动向量化 → RAG搜索</p>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6 space-y-6">
          {/* 上传区域 */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-lg border-2 border-dashed border-blue-300 p-8 text-center hover:border-blue-500 transition-colors cursor-pointer" onClick={() => fileInputRef.current?.click()}>
            <Upload className="w-12 h-12 text-blue-500 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-slate-900 mb-1">上传知识库文件</h3>
            <p className="text-slate-600 mb-4">支持 .txt, .md, .pdf 等文本格式</p>
            
            <div className="flex gap-4 justify-center mb-4">
              <input type="text" placeholder="年级" value={selectedGrade} onChange={(e) => setSelectedGrade(e.target.value)} className="px-3 py-2 border border-slate-300 rounded-lg text-sm" onClick={(e) => e.stopPropagation()} />
              <input type="text" placeholder="学科" value={selectedSubject} onChange={(e) => setSelectedSubject(e.target.value)} className="px-3 py-2 border border-slate-300 rounded-lg text-sm" onClick={(e) => e.stopPropagation()} />
            </div>

            <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg font-medium transition-colors" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }} disabled={isUploading}>
              {isUploading ? '上传中...' : '选择文件'}
            </button>

            <input ref={fileInputRef} type="file" multiple accept=".txt,.md,.pdf,.docx" onChange={handleFileUpload} className="hidden" />
          </motion.div>

          {/* 搜索区域 */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="bg-white rounded-lg p-6 border border-slate-200">
            <h2 className="text-xl font-bold text-slate-900 mb-4">🔍 RAG搜索</h2>
            <div className="flex gap-3">
              <input type="text" placeholder="输入搜索内容..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && handleSearch()} className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button onClick={handleSearch} disabled={isSearching} className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg font-medium transition-colors disabled:opacity-50">
                {isSearching ? <Loader className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              </button>
            </div>
          </motion.div>

          {/* 搜索结果 */}
          <AnimatePresence>
            {showSearchResults && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="bg-white rounded-lg p-6 border border-slate-200">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-slate-900">搜索结果 ({searchResults.length})</h2>
                  <button onClick={() => setShowSearchResults(false)} className="text-slate-500 hover:text-slate-700">✕</button>
                </div>

                {searchResults.length === 0 ? (
                  <p className="text-slate-600 text-center py-8">未找到相关内容</p>
                ) : (
                  <div className="space-y-4">
                    {searchResults.map((result, idx) => (
                      <motion.div key={idx} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.1 }} className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                        <p className="text-sm font-medium text-slate-900 mb-2">{result.content.substring(0, 200)}...</p>
                        <div className="flex gap-4 text-xs text-slate-600 mb-2">
                          <span>📄 {result.source_resource}</span>
                          <span>📍 第 {result.page_number} 页</span>
                          <span>🔗 块 {result.chunk_index}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-bold text-blue-600">{(result.confidence_score * 100).toFixed(0)}%</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* 知识库列表 */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="p-6 border-b border-slate-200">
              <h2 className="text-xl font-bold text-slate-900">📋 我的知识库 ({items.length})</h2>
            </div>

            {isLoading ? (
              <div className="p-8 text-center">
                <Loader className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-2" />
                <p className="text-slate-600">加载中...</p>
              </div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-slate-600">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-2" />
                <p>还没有上传任何知识库</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">名称</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">大小</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">标签</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">向量化状态</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => (
                      <motion.tr key={item.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: idx * 0.05 }} className="border-b border-slate-200 hover:bg-slate-50">
                        <td className="px-6 py-4"><div className="flex items-center gap-2"><FileText className="w-4 h-4 text-slate-400" /><span className="font-medium text-slate-900">{item.name}</span></div></td>
                        <td className="px-6 py-4 text-sm text-slate-600">{item.size}</td>
                        <td className="px-6 py-4"><div className="flex gap-1 flex-wrap">{item.tags?.map((tag, i) => (<span key={i} className="inline-block bg-blue-100 text-blue-700 px-2 py-1 rounded text-xs">{tag}</span>))}</div></td>
                        <td className="px-6 py-4"><div className="flex items-center gap-2">{item.vector_status === 'processing' && <Loader className="w-4 h-4 animate-spin text-blue-500" />}{item.vector_status === 'completed' && <CheckCircle className="w-4 h-4 text-green-500" />}{item.vector_status === 'failed' && <AlertCircle className="w-4 h-4 text-red-500" />}<span className={cn('text-sm font-medium', getStatusColor(item.vector_status))}>{getStatusText(item.vector_status, item.chunk_count)}</span></div></td>
                        <td className="px-6 py-4"><button onClick={() => handleDelete(item.id)} className="text-red-500 hover:text-red-700"><Trash2 className="w-4 h-4" /></button></td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
};
