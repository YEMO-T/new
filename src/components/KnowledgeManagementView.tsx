import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Database,
  Upload,
  Search,
  Filter,
  MoreHorizontal,
  Eye,
  Trash2,
  RefreshCw,
  FileText,
  File,
  FileSpreadsheet,
  CheckCircle2,
  Clock,
  AlertCircle,
  Lock,
  Globe,
  X,
  ChevronLeft,
  ChevronRight,
  Loader2
} from 'lucide-react';
import { cn } from '../lib/utils';
import {
  getKnowledgeList,
  uploadKnowledgeFile,
  deleteKnowledge,
  getKnowledgeStats,
  KnowledgeItem,
  KnowledgeStats
} from '../services/ragApi';

const GRADE_OPTIONS = [
  '高一', '高二', '高三', '高中通用',
  '大一', '大二', '大三', '大四', '研究生', '大学通用'
];

const SUBJECT_OPTIONS = [
  '语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理', '政治',
  '信息技术', '通用技术',
  '计算机科学', '电子信息', '机械工程', '土木工程', '经济管理',
  '法学', '教育学', '文学与新闻', '外语', '数学与统计',
  '物理学', '化学', '生物学', '医学', '艺术设计', '其他'
];

const EDUCATION_LEVEL_OPTIONS = [
  { value: 'senior_high', label: '高中' },
  { value: 'university', label: '大学' },
  { value: 'junior_high', label: '初中' },
  { value: 'primary', label: '小学' },
  { value: 'exam', label: '考试' },
  { value: 'vocational', label: '职业' },
  { value: 'general', label: '通用' }
];

const RESOURCE_TYPE_OPTIONS = [
  { value: 'textbook', label: '教材' },
  { value: 'curriculum', label: '课程标准' },
  { value: 'question_bank', label: '题库' },
  { value: 'notes', label: '笔记' },
  { value: 'exam_paper', label: '试卷' },
  { value: 'other', label: '其他' }
];

const DIFFICULTY_OPTIONS = [
  { value: 'basic', label: '基础' },
  { value: 'intermediate', label: '中等' },
  { value: 'advanced', label: '进阶' },
  { value: 'exam', label: '考试' }
];

const PulseLoader = ({ className }: { className?: string }) => (
  <div className={cn("flex gap-1 items-center", className)}>
    {[0, 1, 2].map((i) => (
      <motion.div
        key={i}
        className="w-1.5 h-1.5 bg-current rounded-full"
        initial={{ scale: 1, opacity: 0.3 }}
        animate={{ scale: [1, 1.5, 1], opacity: [0.3, 1, 0.3] }}
        transition={{ duration: 1, repeat: Infinity, delay: i * 0.2, ease: "easeInOut" }}
      />
    ))}
  </div>
);

const KnowledgeManagementView: React.FC = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  
  const [visibility, setVisibility] = useState<'private' | 'public' | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGrade, setSelectedGrade] = useState<string>('');
  const [selectedSubject, setSelectedSubject] = useState<string>('');
  
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 10;
  
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState<KnowledgeItem | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [uploadForm, setUploadForm] = useState({
    name: '',
    visibility: 'private' as 'private' | 'public',
    grade_level: '',
    subject: '',
    description: '',
    tags: '',
    education_level: '',
    resource_type: '',
    difficulty: '',
    semester: '',
    chapter: ''
  });
  
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    loadKnowledgeList();
    loadStats();
  }, [visibility, selectedGrade, selectedSubject, page]);

  const loadKnowledgeList = async () => {
    setLoading(true);
    try {
      const result = await getKnowledgeList({
        visibility,
        grade: selectedGrade || undefined,
        subject: selectedSubject || undefined,
        search: searchQuery || undefined,
        page,
        page_size: pageSize
      });
      setItems(result.items);
      setTotalPages(result.total_pages);
    } catch (error) {
      console.error('加载知识库列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const result = await getKnowledgeStats();
      setStats(result);
    } catch (error) {
      console.error('加载统计信息失败:', error);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadKnowledgeList();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      if (!uploadForm.name) {
        setUploadForm(prev => ({
          ...prev,
          name: file.name.replace(/\.[^/.]+$/, '')
        }));
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('请选择文件');
      return;
    }

    setUploading(true);
    try {
      await uploadKnowledgeFile(selectedFile, {
        name: uploadForm.name || undefined,
        visibility: uploadForm.visibility,
        grade_level: uploadForm.grade_level || undefined,
        subject: uploadForm.subject || undefined,
        description: uploadForm.description || undefined,
        tags: uploadForm.tags ? uploadForm.tags.split(',').map(t => t.trim()) : undefined,
        education_level: uploadForm.education_level || undefined,
        resource_type: uploadForm.resource_type || undefined,
        difficulty: uploadForm.difficulty || undefined,
        semester: uploadForm.semester || undefined,
        chapter: uploadForm.chapter || undefined
      });

      setShowUploadModal(false);
      setSelectedFile(null);
      setUploadForm({
        name: '',
        visibility: 'private',
        grade_level: '',
        subject: '',
        description: '',
        tags: '',
        education_level: '',
        resource_type: '',
        difficulty: '',
        semester: '',
        chapter: ''
      });
      
      loadKnowledgeList();
      loadStats();
    } catch (error) {
      alert(error instanceof Error ? error.message : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (item: KnowledgeItem) => {
    if (!window.confirm(`确定删除「${item.name}」吗？此操作不可恢复。`)) {
      return;
    }

    try {
      await deleteKnowledge(item.id);
      loadKnowledgeList();
      loadStats();
    } catch (error) {
      alert(error instanceof Error ? error.message : '删除失败');
    }
  };

  const getFileIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'pdf':
        return <File className="w-5 h-5 text-red-500" />;
      case 'pptx':
        return <FileSpreadsheet className="w-5 h-5 text-orange-500" />;
      default:
        return <FileText className="w-5 h-5 text-blue-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="flex items-center gap-1 text-green-600 text-xs font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            已就绪
          </span>
        );
      case 'processing':
        return (
          <span className="flex items-center gap-1 text-blue-600 text-xs font-medium">
            <Clock className="w-3.5 h-3.5" />
            处理中
            <PulseLoader />
          </span>
        );
      case 'failed':
        return (
          <span className="flex items-center gap-1 text-red-600 text-xs font-medium">
            <AlertCircle className="w-3.5 h-3.5" />
            失败
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-gray-500 text-xs font-medium">
            <Clock className="w-3.5 h-3.5" />
            待处理
          </span>
        );
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
  };

  return (
    <div className="flex-1 p-8 h-full overflow-y-auto bg-[#f4fbf4]">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-end mb-8">
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-[#161d19] mb-2">
              📚 知识库管理
            </h2>
            <p className="text-[#2a6b2c] font-medium">
              上传教学资料，构建您的智能知识库
            </p>
          </div>
          <button
            onClick={() => setShowUploadModal(true)}
            className="flex items-center gap-2 bg-[#0d631b] text-white px-6 py-3 rounded-full font-bold shadow-lg hover:opacity-90 transition-all"
          >
            <Upload className="w-5 h-5" />
            上传资料
          </button>
        </div>

        {stats && (
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white p-4 rounded-xl border border-black/5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#0d631b]/10 flex items-center justify-center">
                <Lock className="w-6 h-6 text-[#0d631b]" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#161d19]">{stats.private_count}</p>
                <p className="text-xs text-[#161d19]/60">私有知识库</p>
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-black/5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                <Globe className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#161d19]">{stats.public_count}</p>
                <p className="text-xs text-[#161d19]/60">公共知识库</p>
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-black/5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#161d19]">{stats.vectorized_count}</p>
                <p className="text-xs text-[#161d19]/60">已向量化</p>
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-black/5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-orange-100 flex items-center justify-center">
                <Clock className="w-6 h-6 text-orange-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#161d19]">{stats.pending_count}</p>
                <p className="text-xs text-[#161d19]/60">待处理</p>
              </div>
            </div>
          </div>
        )}

        <div className="bg-white rounded-2xl border border-black/5 p-4 mb-6">
          <div className="flex flex-wrap gap-4 items-center">
            <div className="flex items-center gap-2 bg-[#eef5ee] px-4 py-2 rounded-full flex-1 min-w-[200px]">
              <Search className="w-4 h-4 text-[#707a6c]" />
              <input
                type="text"
                placeholder="搜索知识库..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="bg-transparent border-none focus:ring-0 text-sm w-full"
              />
            </div>
            
            <select
              value={visibility || ''}
              onChange={(e) => setVisibility(e.target.value as 'private' | 'public' | undefined || undefined)}
              className="px-4 py-2 rounded-full border border-black/10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
            >
              <option value="">全部类型</option>
              <option value="private">私有</option>
              <option value="public">公共</option>
            </select>

            <select
              value={selectedGrade}
              onChange={(e) => setSelectedGrade(e.target.value)}
              className="px-4 py-2 rounded-full border border-black/10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
            >
              <option value="">全部年级</option>
              {GRADE_OPTIONS.map(g => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>

            <select
              value={selectedSubject}
              onChange={(e) => setSelectedSubject(e.target.value)}
              className="px-4 py-2 rounded-full border border-black/10 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
            >
              <option value="">全部学科</option>
              {SUBJECT_OPTIONS.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <button
              onClick={handleSearch}
              className="px-6 py-2 bg-[#0d631b] text-white rounded-full text-sm font-bold hover:opacity-90 transition-all"
            >
              搜索
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-black/5 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-[#0d631b]" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-[#161d19]/40">
              <Database className="w-16 h-16 mb-4" />
              <p className="font-medium">暂无知识库内容</p>
              <p className="text-sm mt-1">点击右上角「上传资料」开始构建知识库</p>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#f4fbf4] border-b border-black/5">
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">文件名</th>
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">类型</th>
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">大小</th>
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">年级/学科</th>
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">状态</th>
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">上传时间</th>
                  <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/5">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-[#f4fbf4] transition-colors group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        {getFileIcon(item.type)}
                        <div>
                          <p className="font-bold text-[#161d19]">{item.name}</p>
                          <div className="flex items-center gap-2 mt-1">
                            {item.visibility === 'private' ? (
                              <span className="flex items-center gap-1 text-[10px] text-[#161d19]/50">
                                <Lock className="w-3 h-3" />
                                私有
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-[10px] text-blue-600">
                                <Globe className="w-3 h-3" />
                                公共
                              </span>
                            )}
                            {item.chunk_count > 0 && (
                              <span className="text-[10px] text-[#161d19]/50">
                                {item.chunk_count} 个向量
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 bg-[#eef5ee] text-[#0d631b] text-xs font-bold rounded uppercase">
                        {item.type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-[#161d19]/60">{item.size}</td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col gap-1">
                        {item.grade_level && (
                          <span className="text-xs text-[#161d19]/60">{item.grade_level}</span>
                        )}
                        {item.subject && (
                          <span className="text-xs text-[#0d631b] font-medium">{item.subject}</span>
                        )}
                        {!item.grade_level && !item.subject && (
                          <span className="text-xs text-[#161d19]/40">-</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">{getStatusBadge(item.vector_status)}</td>
                    <td className="px-6 py-4 text-sm text-[#161d19]/60">{formatDate(item.created_at)}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => {
                            setSelectedItem(item);
                            setShowDetailModal(true);
                          }}
                          className="p-2 hover:bg-[#eef5ee] rounded-full text-[#161d19]/60 hover:text-[#0d631b] transition-all"
                          title="查看详情"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {item.is_owner && (
                          <button
                            onClick={() => handleDelete(item)}
                            className="p-2 hover:bg-red-50 rounded-full text-[#161d19]/60 hover:text-red-600 transition-all"
                            title="删除"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-black/5">
              <p className="text-sm text-[#161d19]/60">
                第 {page} 页，共 {totalPages} 页
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-2 rounded-full border border-black/10 disabled:opacity-50 hover:bg-[#eef5ee] transition-all"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-2 rounded-full border border-black/10 disabled:opacity-50 hover:bg-[#eef5ee] transition-all"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {showUploadModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={() => setShowUploadModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-[#161d19]">上传知识库</h3>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="p-2 hover:bg-[#eef5ee] rounded-full transition-all"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-[#0d631b]/30 rounded-xl p-8 text-center cursor-pointer hover:border-[#0d631b] hover:bg-[#f4fbf4] transition-all"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.pdf,.pptx"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  {selectedFile ? (
                    <div className="flex items-center justify-center gap-3">
                      {getFileIcon(selectedFile.name.split('.').pop() || '')}
                      <span className="font-medium text-[#161d19]">{selectedFile.name}</span>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 mx-auto text-[#0d631b]/40 mb-3" />
                      <p className="font-medium text-[#161d19]">点击选择文件</p>
                      <p className="text-sm text-[#161d19]/60 mt-1">支持 TXT、PDF、PPTX 格式</p>
                    </>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-[#161d19] mb-1">资源名称</label>
                  <input
                    type="text"
                    value={uploadForm.name}
                    onChange={(e) => setUploadForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="输入资源名称"
                    className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-[#161d19] mb-1">可见性</label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="visibility"
                        checked={uploadForm.visibility === 'private'}
                        onChange={() => setUploadForm(prev => ({ ...prev, visibility: 'private' }))}
                        className="w-4 h-4 text-[#0d631b]"
                      />
                      <Lock className="w-4 h-4 text-[#161d19]/60" />
                      <span className="text-sm">私有</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="visibility"
                        checked={uploadForm.visibility === 'public'}
                        onChange={() => setUploadForm(prev => ({ ...prev, visibility: 'public' }))}
                        className="w-4 h-4 text-[#0d631b]"
                      />
                      <Globe className="w-4 h-4 text-blue-600" />
                      <span className="text-sm">公共</span>
                    </label>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">年级</label>
                    <select
                      value={uploadForm.grade_level}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, grade_level: e.target.value }))}
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    >
                      <option value="">选择年级</option>
                      {GRADE_OPTIONS.map(g => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">学科</label>
                    <select
                      value={uploadForm.subject}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, subject: e.target.value }))}
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    >
                      <option value="">选择学科</option>
                      {SUBJECT_OPTIONS.map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">教育阶段</label>
                    <select
                      value={uploadForm.education_level}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, education_level: e.target.value }))}
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    >
                      <option value="">选择教育阶段</option>
                      {EDUCATION_LEVEL_OPTIONS.map(e => (
                        <option key={e.value} value={e.value}>{e.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">资源类型</label>
                    <select
                      value={uploadForm.resource_type}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, resource_type: e.target.value }))}
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    >
                      <option value="">选择资源类型</option>
                      {RESOURCE_TYPE_OPTIONS.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">难度</label>
                    <select
                      value={uploadForm.difficulty}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, difficulty: e.target.value }))}
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    >
                      <option value="">选择难度</option>
                      {DIFFICULTY_OPTIONS.map(d => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">学期</label>
                    <input
                      type="text"
                      value={uploadForm.semester}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, semester: e.target.value }))}
                      placeholder="如：上学期"
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#161d19] mb-1">章节</label>
                    <input
                      type="text"
                      value={uploadForm.chapter}
                      onChange={(e) => setUploadForm(prev => ({ ...prev, chapter: e.target.value }))}
                      placeholder="如：第一章"
                      className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-[#161d19] mb-1">描述</label>
                  <textarea
                    value={uploadForm.description}
                    onChange={(e) => setUploadForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="简要描述资源内容..."
                    rows={3}
                    className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30 resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-[#161d19] mb-1">标签</label>
                  <input
                    type="text"
                    value={uploadForm.tags}
                    onChange={(e) => setUploadForm(prev => ({ ...prev, tags: e.target.value }))}
                    placeholder="多个标签用逗号分隔，如：数学, 重点知识"
                    className="w-full px-4 py-2 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                  />
                </div>

                <button
                  onClick={handleUpload}
                  disabled={!selectedFile || uploading}
                  className="w-full py-3 bg-[#0d631b] text-white rounded-xl font-bold hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      上传处理中...
                    </>
                  ) : (
                    <>
                      <Upload className="w-5 h-5" />
                      上传并处理
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showDetailModal && selectedItem && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={() => setShowDetailModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-[#161d19]">{selectedItem.name}</h3>
                <button
                  onClick={() => setShowDetailModal(false)}
                  className="p-2 hover:bg-[#eef5ee] rounded-full transition-all"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-[#f4fbf4] p-4 rounded-xl">
                    <p className="text-xs text-[#161d19]/60 mb-1">文件类型</p>
                    <p className="font-bold text-[#161d19]">{selectedItem.type.toUpperCase()}</p>
                  </div>
                  <div className="bg-[#f4fbf4] p-4 rounded-xl">
                    <p className="text-xs text-[#161d19]/60 mb-1">文件大小</p>
                    <p className="font-bold text-[#161d19]">{selectedItem.size}</p>
                  </div>
                  <div className="bg-[#f4fbf4] p-4 rounded-xl">
                    <p className="text-xs text-[#161d19]/60 mb-1">可见性</p>
                    <p className="font-bold text-[#161d19]">
                      {selectedItem.visibility === 'private' ? '私有' : '公共'}
                    </p>
                  </div>
                  <div className="bg-[#f4fbf4] p-4 rounded-xl">
                    <p className="text-xs text-[#161d19]/60 mb-1">向量数量</p>
                    <p className="font-bold text-[#161d19]">{selectedItem.chunk_count}</p>
                  </div>
                </div>

                {selectedItem.grade_level && (
                  <div>
                    <p className="text-sm font-medium text-[#161d19] mb-1">年级</p>
                    <p className="text-[#161d19]/80">{selectedItem.grade_level}</p>
                  </div>
                )}

                {selectedItem.subject && (
                  <div>
                    <p className="text-sm font-medium text-[#161d19] mb-1">学科</p>
                    <p className="text-[#161d19]/80">{selectedItem.subject}</p>
                  </div>
                )}

                <div className="grid grid-cols-3 gap-4">
                  {(selectedItem as any).education_level && (
                    <div className="bg-[#f4fbf4] p-3 rounded-xl">
                      <p className="text-xs text-[#161d19]/60 mb-1">教育阶段</p>
                      <p className="font-medium text-[#161d19] text-sm">
                        {EDUCATION_LEVEL_OPTIONS.find(e => e.value === (selectedItem as any).education_level)?.label || (selectedItem as any).education_level}
                      </p>
                    </div>
                  )}
                  {(selectedItem as any).resource_type && (
                    <div className="bg-[#f4fbf4] p-3 rounded-xl">
                      <p className="text-xs text-[#161d19]/60 mb-1">资源类型</p>
                      <p className="font-medium text-[#161d19] text-sm">
                        {RESOURCE_TYPE_OPTIONS.find(r => r.value === (selectedItem as any).resource_type)?.label || (selectedItem as any).resource_type}
                      </p>
                    </div>
                  )}
                  {(selectedItem as any).difficulty && (
                    <div className="bg-[#f4fbf4] p-3 rounded-xl">
                      <p className="text-xs text-[#161d19]/60 mb-1">难度</p>
                      <p className="font-medium text-[#161d19] text-sm">
                        {DIFFICULTY_OPTIONS.find(d => d.value === (selectedItem as any).difficulty)?.label || (selectedItem as any).difficulty}
                      </p>
                    </div>
                  )}
                  {(selectedItem as any).semester && (
                    <div className="bg-[#f4fbf4] p-3 rounded-xl">
                      <p className="text-xs text-[#161d19]/60 mb-1">学期</p>
                      <p className="font-medium text-[#161d19] text-sm">{(selectedItem as any).semester}</p>
                    </div>
                  )}
                  {(selectedItem as any).chapter && (
                    <div className="bg-[#f4fbf4] p-3 rounded-xl">
                      <p className="text-xs text-[#161d19]/60 mb-1">章节</p>
                      <p className="font-medium text-[#161d19] text-sm">{(selectedItem as any).chapter}</p>
                    </div>
                  )}
                </div>

                {selectedItem.description && (
                  <div>
                    <p className="text-sm font-medium text-[#161d19] mb-1">描述</p>
                    <p className="text-[#161d19]/80">{selectedItem.description}</p>
                  </div>
                )}

                {selectedItem.tags && selectedItem.tags.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-[#161d19] mb-2">标签</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedItem.tags.map((tag, i) => (
                        <span key={i} className="px-3 py-1 bg-[#eef5ee] text-[#0d631b] text-xs font-bold rounded-full">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedItem.content && (
                  <div>
                    <p className="text-sm font-medium text-[#161d19] mb-2">内容预览</p>
                    <div className="bg-[#f4fbf4] p-4 rounded-xl max-h-60 overflow-y-auto">
                      <pre className="text-sm text-[#161d19]/80 whitespace-pre-wrap font-sans">
                        {selectedItem.content.slice(0, 1000)}
                        {selectedItem.content.length > 1000 && '...'}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default KnowledgeManagementView;
