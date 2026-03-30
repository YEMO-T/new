import React, { useState, useEffect, useRef } from 'react';
import { 
  LayoutDashboard, 
  Database, 
  Layers, 
  History, 
  Settings, 
  Plus, 
  Search, 
  HelpCircle, 
  Bell, 
  Mic, 
  Paperclip, 
  ArrowUp,
  FileText,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  PlayCircle,
  Copy,
  X,
  Sparkles,
  RefreshCw,
  MoreHorizontal,
  Eye,
  Download,
  Trash2,
  FolderInput,
  Shield,
  Bot,
  Award,
  BookOpen,
  LogIn,
  UserPlus,
  ArrowRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import { cn } from './lib/utils';
import { Message, Template, KnowledgeItem, Slide, LessonPlan, Interaction, UserInfo } from './types';
import { LoginView } from './components/auth/LoginView';
import { OnboardingView } from './components/auth/OnboardingView';
import { DashboardView } from './components/chat/DashboardView';
import TemplateLibraryPage from './components/TemplateLibraryPage';

// --- Components ---

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

const SkeletonLoader = ({ className, count = 1 }: { className?: string, count?: number }) => (
  <div className="space-y-3 w-full">
    {Array.from({ length: count }).map((_, i) => (
      <div 
        key={i} 
        className={cn(
          "h-4 bg-[#eef5ee] rounded-md relative overflow-hidden",
          "after:absolute after:inset-0 after:-translate-x-full after:bg-gradient-to-r after:from-transparent after:via-white/40 after:to-transparent after:animate-[shimmer_2s_infinite]",
          className
        )} 
      />
    ))}
  </div>
);

const Sidebar = ({ activeTab, setActiveTab, currentUser }: { activeTab: string, setActiveTab: (tab: string) => void, currentUser: UserInfo | null }) => {
  const initial = currentUser?.username?.charAt(0).toUpperCase() ?? '用';
  const menuItems = [
    { id: 'dashboard', label: '工作台', icon: LayoutDashboard },
    { id: 'knowledge', label: '知识库', icon: Database },
    { id: 'templates', label: '模板库', icon: Layers },
    { id: 'exports', label: '导出记录', icon: History },
    { id: 'profile', label: '个人中心', icon: Award },
    { id: 'settings', label: '设置', icon: Settings },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-64 flex flex-col py-8 px-4 bg-[#e9f0e9] border-r border-outline-variant/10 z-50">
      <div className="px-4 mb-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[#0d631b] flex items-center justify-center text-white font-bold text-lg">豆</div>
          <div>
            <h1 className="text-xl font-bold text-[#0d631b] tracking-tight">豆沙包</h1>
            <p className="text-[10px] text-[#161d19]/60 font-medium tracking-widest uppercase mt-1">教师助手</p>
          </div>
        </div>
      </div>
      
      <nav className="flex-1 space-y-2">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={cn(
              "w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200",
              activeTab === item.id 
                ? "bg-[#dde4dd] text-[#0d631b] font-bold border-r-4 border-[#0d631b]" 
                : "text-[#161d19]/60 hover:bg-[#dde4dd]"
            )}
          >
            <item.icon className="w-5 h-5" />
            <span className="font-semibold tracking-tight">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="mt-auto px-4 pt-6">
        <div 
          onClick={() => setActiveTab('profile')}
          className="flex items-center gap-3 mb-6 p-2 hover:bg-[#dde4dd] rounded-2xl transition-all cursor-pointer"
        >
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#0d631b] to-[#a3f69c] flex items-center justify-center text-white font-bold shadow-sm">
            {initial}
          </div>
          <div>
            <p className="text-sm font-bold text-[#161d19] truncate max-w-[100px]">{currentUser?.username || '用户'}</p>
            <p className="text-[10px] text-[#161d19]/60 uppercase tracking-widest">高级教师</p>
          </div>
        </div>
        <button 
          onClick={() => setActiveTab('dashboard')}
          className="w-full bg-[#0d631b] text-white py-3 rounded-xl font-bold text-sm hover:opacity-90 transition-all"
        >
          新建课件
        </button>
      </div>
    </aside>
  );
};

const TopNav = ({ title, activeTab, setActiveTab, setShowOnboarding }: { title: string, activeTab: string, setActiveTab: (tab: string) => void, setShowOnboarding: (show: boolean) => void }) => {
  return (
    <nav className="fixed top-0 right-0 left-64 h-16 flex justify-between items-center px-8 z-40 bg-[#f4fbf4]/80 backdrop-blur-xl border-b border-black/5">
      <div className="flex items-center gap-8">
        <h2 className="text-lg font-bold tracking-tight text-[#0d631b]">{title}</h2>
        <div className="flex gap-6">
          <button 
            onClick={() => setActiveTab('outline')}
            className={cn(
              "text-sm tracking-tight transition-all cursor-pointer pb-1",
              activeTab === 'outline' ? "text-[#0d631b] font-semibold border-b-2 border-[#0d631b]" : "text-[#161d19]/70 hover:text-[#0d631b]"
            )}
          >
            大纲
          </button>
          <button 
            onClick={() => setActiveTab('preview')}
            className={cn(
              "text-sm tracking-tight transition-all cursor-pointer pb-1",
              activeTab === 'preview' ? "text-[#0d631b] font-semibold border-b-2 border-[#0d631b]" : "text-[#161d19]/70 hover:text-[#0d631b]"
            )}
          >
            预览
          </button>
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={cn(
              "text-sm tracking-tight transition-all cursor-pointer pb-1",
              activeTab === 'dashboard' ? "text-[#0d631b] font-semibold border-b-2 border-[#0d631b]" : "text-[#161d19]/70 hover:text-[#0d631b]"
            )}
          >
            编辑
          </button>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="relative flex items-center bg-[#eef5ee] px-4 py-1.5 rounded-full">
          <Search className="w-4 h-4 text-[#707a6c]" />
          <input 
            className="bg-transparent border-none focus:ring-0 text-sm ml-2 w-48" 
            placeholder="搜索..." 
            type="text"
          />
        </div>
        <button 
          onClick={() => setShowOnboarding(true)}
          className="p-2 text-[#40493d] hover:bg-[#e3eae3] rounded-full transition-colors"
        >
          <HelpCircle className="w-5 h-5" />
        </button>
        <button className="p-2 text-[#40493d] hover:bg-[#e3eae3] rounded-full transition-colors"><Bell className="w-5 h-5" /></button>
        <button 
          onClick={() => setActiveTab('exports')}
          className="ml-2 bg-[#0d631b] text-white px-6 py-2 rounded-full font-semibold text-sm hover:opacity-90 transition-all"
        >
          导出
        </button>
      </div>
    </nav>
  );
};

import { 
  chatWithGeminiStream, 
  loginUser, 
  registerUser, 
  getTemplates,
  getExports,
  logExport,
  deleteExport,
  getKnowledgeItems,
  uploadKnowledge,
  deleteKnowledgeItem,
  updateKnowledgeItem,
  renderPptxFromServer,
  renderDocxFromServer
} from './services/api';
import { exportToPPTX, exportToDOCX } from './services/export';

// --- Components ---

const KnowledgeBaseView = ({
  items,
  onUpload,
  onDeleteItem,
  onUpdateItem
}: {
  items: KnowledgeItem[];
  onUpload: () => void;
  onDeleteItem: (itemId: string) => Promise<void>;
  onUpdateItem: (itemId: string, data: { name?: string; tags?: string[]; content?: string }) => Promise<void>;
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editContent, setEditContent] = useState('');

  const startEdit = (item: KnowledgeItem) => {
    setEditingId(item.id);
    setEditName(item.name);
    setEditTags((item.tags || []).join(', '));
    setEditContent(item.content || '');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName('');
    setEditTags('');
    setEditContent('');
  };

  const saveEdit = async (item: KnowledgeItem) => {
    const tagsArr = editTags
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);

    await onUpdateItem(item.id, {
      name: editName.trim(),
      tags: tagsArr,
      content: editContent
    });
    cancelEdit();
  };

  const confirmDelete = async (item: KnowledgeItem) => {
    const ok = window.confirm(`确定删除「${item.name}」吗？该操作不可恢复。`);
    if (!ok) return;
    await onDeleteItem(item.id);
  };

  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <div className="flex justify-between items-end mb-10">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-[#161d19] mb-2">📚 知识库中心</h2>
          <p className="text-[#2a6b2c] font-medium">上传教材、教案 or 参考资料，让豆沙包更懂您的教学风格</p>
        </div>
        <button 
          onClick={onUpload}
          className="flex items-center gap-2 bg-[#0d631b] text-white px-8 py-3 rounded-full font-bold shadow-lg hover:opacity-90 transition-all"
        >
          <FolderInput className="w-5 h-5" />
          上传资料
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <div className="bg-[#eef5ee] p-4 rounded-xl flex items-center gap-4 text-sm font-bold text-[#0d631b] mb-4">
          <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-sm">
            <Database className="w-5 h-5" />
          </div>
          <span>已存储 3 个文件，共使用 8.0MB / 1GB</span>
        </div>

        <div className="bg-white rounded-2xl border border-black/5 overflow-hidden shadow-sm">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#f4fbf4] border-b border-black/5">
                <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">文件名</th>
                <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">大小</th>
                <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">上传日期</th>
                <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">标签</th>
                <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest">状态</th>
                <th className="px-6 py-4 text-xs font-bold text-[#161d19]/40 uppercase tracking-widest text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-[#f4fbf4] transition-colors group">
                  <td className="px-6 py-4 align-top">
                    {editingId === item.id ? (
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            "w-10 h-10 rounded-lg flex items-center justify-center",
                            item.type === 'pdf' ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"
                          )}>
                            <FileText className="w-5 h-5" />
                          </div>
                          <input
                            className="w-full border border-black/10 rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                          />
                        </div>
                        <textarea
                          className="w-full border border-black/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                          rows={4}
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          placeholder="这里可以编辑知识库内容（用于检索与生成）"
                        />
                      </div>
                    ) : (
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "w-10 h-10 rounded-lg flex items-center justify-center",
                          item.type === 'pdf' ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"
                        )}>
                          <FileText className="w-5 h-5" />
                        </div>
                        <span className="font-bold text-[#161d19]">{item.name}</span>
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-[#161d19]/60">{item.size}</td>
                  <td className="px-6 py-4 text-sm text-[#161d19]/60">{item.date}</td>
                  <td className="px-6 py-4 align-top">
                    {editingId === item.id ? (
                      <input
                        className="w-full border border-black/10 rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-[#0d631b]/30"
                        value={editTags}
                        onChange={(e) => setEditTags(e.target.value)}
                        placeholder="标签（逗号分隔，如：数学, 三年级）"
                      />
                    ) : (
                      <div className="flex gap-2 flex-wrap">
                        {item.tags.map(tag => (
                          <span key={tag} className="px-2 py-0.5 bg-[#eef5ee] text-[#0d631b] text-[10px] font-bold rounded uppercase">{tag}</span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-2 h-2 rounded-full", item.status === 'completed' ? "bg-green-500" : "bg-orange-500")}></div>
                      <span className="text-xs font-medium text-[#161d19]/60">
                        {item.status === 'completed' ? '已就绪' : (
                          <div className="flex items-center gap-2">
                            <span>同步中</span>
                            <PulseLoader className="text-orange-500" />
                          </div>
                        )}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    {editingId === item.id ? (
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => saveEdit(item)}
                          className="px-4 py-2 rounded-full bg-[#0d631b] text-white text-xs font-bold hover:opacity-90 transition-all"
                        >
                          保存
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="px-4 py-2 rounded-full border border-black/10 text-[#161d19]/60 text-xs font-bold hover:bg-[#f4fbf4] transition-all"
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => startEdit(item)}
                          className="p-2 hover:bg-white rounded-full text-[#161d19]/60 hover:text-[#0d631b] shadow-sm transition-all"
                          title="编辑"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => confirmDelete(item)}
                          className="p-2 hover:bg-white rounded-full text-[#161d19]/60 hover:text-red-600 shadow-sm transition-all"
                          title="删除"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const ExportsView = ({ records, onDelete }: { records: any[], onDelete: (id: string) => void }) => {

  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <h2 className="text-4xl font-extrabold tracking-tight text-[#161d19] mb-2">📜 导出记录</h2>
      <p className="text-[#2a6b2c] font-medium mb-10">回顾并下载您生成的所有教学资源</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {records.map((record) => (
          <div key={record.id} className="bg-white p-6 rounded-2xl border border-black/5 shadow-sm hover:shadow-md transition-all group relative">
            <button 
              onClick={() => onDelete(record.id)}
              className="absolute top-4 right-4 p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-full opacity-0 group-hover:opacity-100 transition-all"
              title="删除记录"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <div className="flex justify-between items-start mb-4">
              <div className="w-12 h-12 rounded-xl bg-[#eef5ee] flex items-center justify-center text-[#0d631b]">
                <Download className="w-6 h-6" />
              </div>
              <span className="px-3 py-1 bg-[#0d631b]/10 text-[#0d631b] text-[10px] font-bold rounded-md">{record.format}</span>
            </div>
            <h3 className="font-bold text-[#161d19] mb-1">{record.title}</h3>
            <p className="text-xs text-[#161d19]/40 mb-4">{record.date} · {record.size}</p>
            <div className="flex gap-2">
              {record.fileUrl ? (
                <a 
                  href={record.fileUrl} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="flex-1 py-2 rounded-full bg-[#0d631b] text-white text-xs font-bold hover:opacity-90 transition-all text-center flex items-center justify-center"
                >
                  查看/下载
                </a>
              ) : (
                <button className="flex-1 py-2 rounded-full bg-[#0d631b]/50 text-white text-xs font-bold cursor-not-allowed">链接失效</button>
              )}
              <button className="px-4 py-2 rounded-full border border-black/10 text-[#161d19]/60 text-xs font-bold hover:bg-[#f4fbf4] transition-all">详情</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const SettingsView = () => {
  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <h2 className="text-4xl font-extrabold tracking-tight text-[#161d19] mb-2">⚙️ 系统设置</h2>
      <p className="text-[#2a6b2c] font-medium mb-10">个性化您的 AI 教学助手</p>

      <div className="max-w-2xl space-y-8">
        <section>
          <h3 className="text-lg font-bold text-[#161d19] mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-[#0d631b]" />
            账号安全
          </h3>
          <div className="bg-white rounded-2xl border border-black/5 p-6 space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <p className="font-bold text-[#161d19]">绑定邮箱</p>
                <p className="text-xs text-[#161d19]/60">gohilsudarsan838@gmail.com</p>
              </div>
              <button className="text-[#0d631b] text-sm font-bold">修改</button>
            </div>
            <div className="h-[1px] bg-black/5"></div>
            <div className="flex justify-between items-center">
              <div>
                <p className="font-bold text-[#161d19]">登录密码</p>
                <p className="text-xs text-[#161d19]/60">已设置，定期更换更安全</p>
              </div>
              <button className="text-[#0d631b] text-sm font-bold">重置</button>
            </div>
          </div>
        </section>

        <section>
          <h3 className="text-lg font-bold text-[#161d19] mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-[#0d631b]" />
            AI 模型偏好
          </h3>
          <div className="bg-white rounded-2xl border border-black/5 p-6 space-y-6">
            <div>
              <label className="block text-sm font-bold text-[#161d19] mb-2">默认生成风格</label>
              <select className="w-full bg-[#f4fbf4] border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-[#0d631b]">
                <option>专业严谨</option>
                <option>生动有趣</option>
                <option>简约现代</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-[#161d19] mb-2">互动等级</label>
              <input type="range" className="w-full accent-[#0d631b]" />
              <div className="flex justify-between text-[10px] text-[#161d19]/40 font-bold uppercase mt-1">
                <span>低</span>
                <span>中</span>
                <span>高</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

const OutlineView = ({ slides }: { slides: Slide[] }) => {
  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold text-[#161d19] mb-8">课件大纲设计</h2>
        <div className="space-y-4">
          {slides.length > 0 ? slides.map((slide, i) => (
            <div key={i} className="bg-white p-6 rounded-2xl border border-black/5 shadow-sm flex items-center justify-between group hover:border-[#0d631b]/30 transition-all">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-[#f4fbf4] text-[#0d631b] flex items-center justify-center font-bold text-sm">
                  {i + 1}
                </div>
                <div>
                  <h3 className="font-bold text-[#161d19]">{slide.title}</h3>
                  <p className="text-xs text-[#161d19]/40 mt-1">{slide.type === 'cover' ? '封面' : slide.type === 'summary' ? '总结' : '正文'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button className="p-2 hover:bg-[#f4fbf4] rounded-full text-[#161d19]/40 group-hover:text-[#0d631b] transition-all">
                  <MoreHorizontal className="w-5 h-5" />
                </button>
              </div>
            </div>
          )) : (
            <div className="text-center py-20 opacity-40">
              <Layers className="w-16 h-16 mx-auto mb-4" />
              <p className="text-xl font-bold">暂无大纲，请在工作台与豆沙包交流生成</p>
            </div>
          )}
          {slides.length > 0 && (
            <button className="w-full py-4 border-2 border-dashed border-black/10 rounded-2xl text-[#161d19]/40 font-bold hover:border-[#0d631b]/30 hover:text-[#0d631b] transition-all flex items-center justify-center gap-2">
              <Plus className="w-5 h-5" />
              添加新章节
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const PreviewView = ({ slides, lessonPlan, interaction, onExport, currentUser }: { 
  slides: Slide[], 
  lessonPlan: LessonPlan | null, 
  interaction: Interaction | null,
  onExport?: (title: string, format: string) => void,
  currentUser: UserInfo | null
}) => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [mode, setMode] = useState<'ppt' | 'word' | 'interaction'>('ppt');
  const [isRendering, setIsRendering] = useState(true);

  useEffect(() => {
    setIsRendering(true);
    const timer = setTimeout(() => setIsRendering(false), 1000);
    return () => clearTimeout(timer);
  }, [mode]);

  if (slides.length === 0 && !lessonPlan) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#f0f4f0]">
        <div className="text-center opacity-40">
          <Eye className="w-16 h-16 mx-auto mb-4" />
          <p className="text-xl font-bold">暂无预览内容</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-11 h-full overflow-y-auto bg-[#f0f4f0]">
      <div className="max-w-5xl mx-auto mb-8 flex gap-4">
        <button 
          onClick={() => setMode('ppt')}
          className={cn("px-6 py-2 rounded-full font-bold transition-all", mode === 'ppt' ? "bg-[#0d631b] text-white" : "bg-white text-[#161d19]/60")}
        >
          PPT 预览
        </button>
        <button 
          onClick={() => setMode('word')}
          className={cn("px-6 py-2 rounded-full font-bold transition-all", mode === 'word' ? "bg-[#0d631b] text-white" : "bg-white text-[#161d19]/60")}
        >
          教案预览
        </button>
        <button 
          onClick={() => setMode('interaction')}
          className={cn("px-6 py-2 rounded-full font-bold transition-all", mode === 'interaction' ? "bg-[#0d631b] text-white" : "bg-white text-[#161d19]/60")}
        >
          互动环节
        </button>
      </div>

      {isRendering ? (
        <div className="max-w-5xl mx-auto aspect-video bg-white rounded-3xl shadow-2xl overflow-hidden p-20 flex flex-col items-center justify-center gap-8">
          <RefreshCw className="w-12 h-12 text-[#0d631b] animate-spin" />
          <div className="w-full max-w-md space-y-4">
            <SkeletonLoader className="h-8 w-3/4 mx-auto" />
            <SkeletonLoader className="h-4 w-full" count={3} />
          </div>
          <p className="text-[#0d631b] font-bold animate-pulse">正在渲染预览内容...</p>
        </div>
      ) : (
        <>
          {mode === 'ppt' && slides.length > 0 && (
        <div className="max-w-5xl mx-auto aspect-video bg-white rounded-3xl shadow-2xl overflow-hidden relative flex flex-col border border-black/5">
          <AnimatePresence mode="wait">
            <motion.div 
              key={currentSlide}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex-1 flex flex-col items-center justify-center p-20 relative"
            >
              <div className="text-center max-w-3xl">
                <h1 className={cn(
                  "font-black text-[#0d631b] mb-6 tracking-tighter",
                  slides[currentSlide].type === 'cover' ? "text-6xl" : "text-4xl"
                )}>
                  {slides[currentSlide].title}
                </h1>
                <div className="text-xl text-[#161d19]/80 font-medium leading-relaxed prose prose-green max-w-none">
                  <ReactMarkdown>{slides[currentSlide].content}</ReactMarkdown>
                </div>
              </div>
              {slides[currentSlide].imagePrompt && (
                <div className="absolute bottom-6 right-6 opacity-20">
                  <Sparkles className="w-8 h-8" />
                </div>
              )}
            </motion.div>
          </AnimatePresence>
          <div className="h-20 px-10 bg-[#f4fbf4] border-t border-black/5 flex items-center justify-between">
            <div className="flex items-center gap-6">
              <button 
                disabled={currentSlide === 0}
                onClick={() => setCurrentSlide(prev => prev - 1)}
                className="p-2 hover:bg-white rounded-full text-[#161d19]/40 transition-all disabled:opacity-20"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>
              <span className="text-sm font-bold text-[#161d19]/60">{currentSlide + 1} / {slides.length}</span>
              <button 
                disabled={currentSlide === slides.length - 1}
                onClick={() => setCurrentSlide(prev => prev + 1)}
                className="p-2 hover:bg-white rounded-full text-[#161d19]/40 transition-all disabled:opacity-20"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            </div>
            <div className="flex items-center gap-4">
              <button className="p-2 hover:bg-white rounded-full text-[#161d19]/40 transition-all"><Maximize2 className="w-5 h-5" /></button>
              <button className="p-2 hover:bg-white rounded-full text-[#161d19]/40 transition-all"><Copy className="w-5 h-5" /></button>
            </div>
          </div>
        </div>
      )}

      {mode === 'word' && lessonPlan && (
        <div className="max-w-4xl mx-auto bg-white rounded-3xl shadow-xl p-16 border border-black/5 min-h-[800px]">
          <h1 className="text-4xl font-black text-[#161d19] mb-8 border-b-4 border-[#0d631b] pb-4">{lessonPlan.title}</h1>
          <section className="mb-10">
            <h2 className="text-xl font-bold text-[#0d631b] mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5" /> 教学目标
            </h2>
            <ul className="list-disc list-inside space-y-2 text-[#161d19]/80">
              {lessonPlan.objectives.map((obj, i) => <li key={i}>{obj}</li>)}
            </ul>
          </section>
          <section className="mb-10">
            <h2 className="text-xl font-bold text-[#0d631b] mb-4 flex items-center gap-2">
              <Layers className="w-5 h-5" /> 教学过程
            </h2>
            <div className="space-y-6">
              {lessonPlan.process.map((p, i) => (
                <div key={i} className="flex gap-6">
                  <div className="w-24 shrink-0 font-bold text-[#0d631b]">{p.duration}</div>
                  <div className="flex-1">
                    <h3 className="font-bold text-[#161d19] mb-1">{p.stage}</h3>
                    <p className="text-[#161d19]/70 leading-relaxed">{p.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
          <section>
            <h2 className="text-xl font-bold text-[#0d631b] mb-4 flex items-center gap-2">
              <BookOpen className="w-5 h-5" /> 课后作业
            </h2>
            <p className="text-[#161d19]/80">{lessonPlan.homework}</p>
          </section>
        </div>
      )}

      {mode === 'interaction' && interaction && (
        <div className="max-w-4xl mx-auto bg-white rounded-3xl shadow-xl p-16 border border-black/5 text-center">
          <div className="w-20 h-20 bg-[#f4fbf4] rounded-2xl flex items-center justify-center text-[#0d631b] mx-auto mb-6">
            {interaction.type === 'game' ? <PlayCircle className="w-10 h-10" /> : <Sparkles className="w-10 h-10" />}
          </div>
          <h2 className="text-3xl font-black text-[#161d19] mb-4">{interaction.title}</h2>
          <div className="bg-[#f4fbf4] p-8 rounded-2xl text-left border border-[#0d631b]/10">
            <p className="text-lg text-[#161d19]/80 leading-relaxed whitespace-pre-wrap">{interaction.description}</p>
          </div>
          <button className="mt-8 px-10 py-4 bg-[#0d631b] text-white rounded-full font-black shadow-lg hover:scale-105 transition-transform">
            立即运行演示
          </button>
        </div>
      )}

      <div className="max-w-5xl mx-auto mt-8 flex justify-center gap-4">
        <button 
          onClick={() => {
            if (slides.length > 0) {
              exportToPPTX(slides);
              onExport?.(slides[0].title || '新建课件', 'PPTX');
            }
          }}
          className="px-8 py-3 rounded-full bg-[#0d631b] text-white font-bold shadow-lg hover:opacity-90 transition-all flex items-center gap-2"
        >
          <Download className="w-5 h-5" /> 导出 PPT (.pptx)
        </button>
        <button 
          onClick={() => {
            if (lessonPlan) {
              exportToDOCX(lessonPlan);
              onExport?.(lessonPlan.title, 'DOCX');
            }
          }}
          className="px-8 py-3 rounded-full bg-white text-[#161d19] font-bold border border-black/10 hover:bg-[#f4fbf4] transition-all flex items-center gap-2"
        >
          <FileText className="w-5 h-5" /> 导出教案 (.docx)
        </button>
      </div>
    </>
  )}
</div>
);
};

const TemplateView = ({ setActiveTab, templates }: { setActiveTab: (tab: string) => void, templates: Template[] }) => {
  const [isLoading, setIsLoading] = useState(templates.length === 0);

  useEffect(() => {
    if (templates.length > 0) {
      setIsLoading(false);
    }
  }, [templates]);

  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <section className="mb-12">
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-4xl font-extrabold tracking-tight text-[#161d19] mb-2">🎨 模板中心</h2>
            <p className="text-[#2a6b2c] font-medium">发现由顶尖教师和教育专家设计的互动课件模板</p>
          </div>
          <div className="flex gap-3">
            <button className="px-6 py-2 rounded-full bg-white text-[#0d631b] font-semibold text-sm border-2 border-[#0d631b]/10 hover:bg-[#eef5ee] transition-colors">我的收藏</button>
            <button className="px-6 py-2 rounded-full bg-[#0d631b] text-white font-semibold text-sm hover:opacity-90 transition-all">上传模板</button>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3 mt-8">
          {['全部', '学术', '趣味互动', '简约白板', '科学探究', '艺术创作'].map((cat, i) => (
            <button 
              key={cat} 
              className={cn(
                "px-6 py-2.5 rounded-full text-sm font-semibold transition-all",
                i === 0 ? "bg-[#0d631b] text-white" : "bg-white text-[#161d19]/70 hover:bg-[#e3eae3]"
              )}
            >
              {cat}
            </button>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-x-8 gap-y-11">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-4">
              <div className="aspect-[4/3] rounded-lg bg-[#eef5ee] relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-[shimmer_2s_infinite] -translate-x-full"></div>
              </div>
              <SkeletonLoader className="h-6 w-3/4" />
              <SkeletonLoader className="h-4 w-1/2" />
            </div>
          ))
        ) : (
          templates.map((tpl) => (
            <motion.div 
              key={tpl.id} 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="group flex flex-col gap-4"
            >
              <div className="relative aspect-[4/3] rounded-lg overflow-hidden bg-[#e3eae3] shadow-sm group-hover:shadow-xl transition-all duration-300">
                <img src={tpl.image} alt={tpl.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div className="absolute bottom-4 left-4 flex gap-2">
                  <span className="px-3 py-1 bg-white/90 text-[10px] font-bold uppercase tracking-wider rounded-md text-[#0d631b]">{tpl.category}</span>
                </div>
              </div>
              <div className="px-1">
                <h3 className="font-bold text-lg text-[#161d19] leading-tight">{tpl.title}</h3>
                <div className="flex items-center justify-between mt-2">
                  <div className="flex items-center gap-2">
                    <Eye className="w-3 h-3 text-[#161d19]/60" />
                    <span className="text-xs text-[#161d19]/60 font-medium">{tpl.usageCount}次使用</span>
                  </div>
                  <span className="text-[10px] font-bold bg-[#2a6b2c]/10 text-[#2a6b2c] px-2 py-0.5 rounded">{tpl.category}</span>
                </div>
                <div className="mt-4 flex gap-2">
                  <button 
                    onClick={() => setActiveTab('preview')}
                    className="flex-1 py-2 rounded-full border border-[#0d631b]/20 text-[#0d631b] text-xs font-bold hover:bg-[#0d631b] hover:text-white transition-all"
                  >
                    预览详情
                  </button>
                  <button 
                    onClick={() => setActiveTab('dashboard')}
                    className="w-10 h-10 flex items-center justify-center rounded-full bg-[#a3f69c] text-[#0d631b] hover:bg-[#0d631b] hover:text-white transition-all"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
};

const ProfileView = ({ currentUser, onLogout }: { currentUser: UserInfo | null, onLogout: () => void }) => {
  const initial = currentUser?.username?.charAt(0).toUpperCase() ?? '?';

  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-3xl p-10 border border-black/5 shadow-sm flex items-center gap-10 mb-10">
          <div className="w-32 h-32 rounded-full bg-gradient-to-br from-[#0d631b] to-[#a3f69c] flex items-center justify-center text-white text-5xl font-black shadow-xl">
            {initial}
          </div>
          <div>
            <h2 className="text-4xl font-black text-[#161d19] tracking-tighter">{currentUser?.username ?? '未知用户'}</h2>
            <p className="text-[#0d631b] font-bold mt-1">{currentUser?.email ?? ''}</p>
            <div className="flex gap-4 mt-6">
              <div className="text-center px-6 py-2 bg-[#f4fbf4] rounded-2xl">
                <p className="text-xl font-black text-[#0d631b]">0</p>
                <p className="text-[10px] text-[#161d19]/40 uppercase font-bold">课件数量</p>
              </div>
              <div className="text-center px-6 py-2 bg-[#f4fbf4] rounded-2xl">
                <p className="text-xl font-black text-[#0d631b]">0</p>
                <p className="text-[10px] text-[#161d19]/40 uppercase font-bold">获得点赞</p>
              </div>
              <div className="text-center px-6 py-2 bg-[#f4fbf4] rounded-2xl">
                <p className="text-xl font-black text-[#0d631b]">0</p>
                <p className="text-[10px] text-[#161d19]/40 uppercase font-bold">教学荣誉</p>
              </div>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-8">
          <div className="bg-white rounded-3xl p-8 border border-black/5 shadow-sm">
            <h3 className="text-xl font-bold text-[#161d19] mb-6">账号信息</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center p-3 bg-[#f4fbf4] rounded-xl">
                <span className="text-sm text-[#161d19]/60">用户名</span>
                <span className="text-sm font-bold text-[#161d19]">{currentUser?.username}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-[#f4fbf4] rounded-xl">
                <span className="text-sm text-[#161d19]/60">邮箱</span>
                <span className="text-sm font-bold text-[#161d19]">{currentUser?.email}</span>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-3xl p-8 border border-black/5 shadow-sm">
            <h3 className="text-xl font-bold text-[#161d19] mb-6">我的成就</h3>
            <div className="space-y-4">
              {['豆沙包新手勋章', 'AI 教学探索者'].map((award, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-[#f4fbf4] rounded-xl border border-[#0d631b]/5">
                  <Award className="w-5 h-5 text-[#0d631b]" />
                  <span className="text-sm font-bold text-[#161d19]">{award}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-10 flex justify-center">
          <button 
            onClick={onLogout}
            className="flex items-center gap-2 text-red-600 font-bold hover:bg-red-50 px-6 py-3 rounded-xl transition-all"
          >
            <LogIn className="w-5 h-5 rotate-180" />
            退出登录
          </button>
        </div>
      </div>
    </div>
  );
};

// Removed inline LoginView and OnboardingView - now imported from components/auth/

// --- Main App ---

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserInfo | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [templateItems, setTemplateItems] = useState<Template[]>([]);
  const [exportRecords, setExportRecords] = useState<any[]>([]);

  // Courseware State
  const [slides, setSlides] = useState<Slide[]>([]);
  const [lessonPlan, setLessonPlan] = useState<LessonPlan | null>(null);
  const [interaction, setInteraction] = useState<Interaction | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);

  // NOTE: 根据真实用户名动态生成欢迎语
  const buildWelcomeMessage = (username: string): Message => ({
    id: '1',
    role: 'assistant',
    content: `您好，**${username}**！我是您的 AI 教学助手**豆沙包**。\n\n我会先和您聊几句，了解您的课程主题、学情和偏好，然后再为您生成最贴心的课件。\n\n今天想为哪门课准备教学内容呢？😊`
  });

  const [messages, setMessages] = useState<Message[]>([]);

  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    const storedUser = localStorage.getItem('user_info');
    if (storedToken && storedUser) {
      try {
        const user = JSON.parse(storedUser) as UserInfo;
        setCurrentUser(user);
        setIsLoggedIn(true);
        setMessages([buildWelcomeMessage(user.username)]);
        
        // 初始加载数据
        loadAllData(user.id);
      } catch {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_info');
      }
    }
  }, []);

  const handleLogin = (userInfo: UserInfo) => {
    setCurrentUser(userInfo);
    setIsLoggedIn(true);
    setMessages([buildWelcomeMessage(userInfo.username)]);
    setShowOnboarding(true);
    loadAllData(userInfo.id);
  };

  const loadAllData = async (userId: string) => {
    try {
      const [knowledges, templates, exports] = await Promise.all([
        getKnowledgeItems(),
        getTemplates(),
        getExports()
      ]);
      setKnowledgeItems(knowledges.map((k: any) => ({
        id: k.id,
        name: k.name,
        type: k.type,
        size: k.size,
        date: k.created_at?.split('T')[0] || '',
        tags: k.tags || [],
        status: k.status || 'completed',
        content: k.content || ''
      })));
      setTemplateItems(templates.map((t: any) => ({
        id: t.id,
        title: t.title,
        description: t.description,
        author: t.author,
        category: t.category,
        usageCount: t.usage_count >= 1000 ? (t.usage_count/1000).toFixed(1) + 'k' : t.usage_count.toString(),
        image: t.image_url
      })));
      setExportRecords(exports.map((e: any) => ({
        id: e.id,
        title: e.title,
        format: e.format,
        date: e.created_at?.replace('T', ' ').slice(0, 16),
        size: e.size,
        fileUrl: e.file_url
      })));
    } catch (err) {
      console.error('Failed to load storage data:', err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_info');
    setIsLoggedIn(false);
    setCurrentUser(null);
    setMessages([]);
    setActiveTab('dashboard');
  };

  const handleKnowledgeUpload = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;
      
      const newItem: KnowledgeItem = {
        id: Date.now().toString(),
        name: file.name,
        type: file.name.endsWith('.pdf') ? 'pdf' : 'docx',
        size: (file.size / 1024 / 1024).toFixed(1) + 'MB',
        date: new Date().toISOString().split('T')[0],
        tags: ['新上传'],
        status: 'syncing'
      };
      
      setKnowledgeItems(prev => [newItem, ...prev]);

      // 读取文件内容以支持 RAG
      const reader = new FileReader();
      reader.onload = async (event) => {
        const content = event.target?.result as string;
        try {
          await uploadKnowledge({
            name: newItem.name,
            type: newItem.type,
            size: newItem.size,
            tags: newItem.tags,
            content: content.slice(0, 10000) // 限制长度
          });
          
          setKnowledgeItems(prev => prev.map(item => item.id === newItem.id ? { ...item, status: 'completed' } : item));
        } catch (err) {
          console.error('Upload failed:', err);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const handleKnowledgeDeleteItem = async (itemId: string) => {
    try {
      if (!currentUser?.id) return;
      await deleteKnowledgeItem(itemId);
      await loadAllData(currentUser.id);
    } catch (err) {
      console.error('Delete knowledge item failed:', err);
      alert('删除失败，请稍后重试。');
    }
  };

  const handleKnowledgeUpdateItem = async (
    itemId: string,
    data: { name?: string; tags?: string[]; content?: string }
  ) => {
    try {
      if (!currentUser?.id) return;
      await updateKnowledgeItem(itemId, data);
      await loadAllData(currentUser.id);
    } catch (err) {
      console.error('Update knowledge item failed:', err);
      alert('更新失败，请稍后重试。');
    }
  };

  const handleGenerated = (data: any) => {
    if (data.slides) setSlides(data.slides);
    if (data.lessonPlan) setLessonPlan(data.lessonPlan);
    if (data.interaction) setInteraction(data.interaction);
    // 生成成功后自动跳转到预览页
    setActiveTab('preview');
  };

  const handleExport = async (title: string, format: string) => {
    try {
      let fileUrl = '';
      if (format === 'PPTX') {
        const res = await renderPptxFromServer(slides, title, selectedTemplate?.id);
        fileUrl = res.file_url;
      } else {
        if (!lessonPlan) throw new Error('教案内容缺失');
        const res = await renderDocxFromServer(title, lessonPlan);
        fileUrl = res.file_url;
      }

      if (fileUrl) {
        window.open(fileUrl, '_blank');
      }
      // 刷新列表
      const exports = await getExports();
      setExportRecords(exports.map((e: any) => ({
        id: e.id,
        title: e.title,
        format: e.format,
        date: e.created_at?.replace('T', ' ').slice(0, 16),
        size: e.size,
        fileUrl: e.file_url
      })));
    } catch (err) {
      console.error('Failed to log export:', err);
    }
  };

  const handleDeleteExport = async (exportId: string) => {
    if (!window.confirm('确定要删除这条导出记录吗？')) return;
    try {
      await deleteExport(exportId);
      setExportRecords(prev => prev.filter(r => r.id !== exportId));
    } catch (err) {
      console.error('Failed to delete export:', err);
      alert('删除失败，请重试');
    }
  };

  const renderView = () => {
    if (!isLoggedIn) return <LoginView onLogin={handleLogin} />;
    if (showOnboarding) return <OnboardingView onComplete={() => setShowOnboarding(false)} />;

    switch (activeTab) {
      case 'dashboard': return (
        <DashboardView 
          setActiveTab={setActiveTab} 
          onGenerated={handleGenerated} 
          knowledgeItems={knowledgeItems} 
          messages={messages}
          setMessages={setMessages}
          currentUser={currentUser}
          selectedTemplate={selectedTemplate}
          onSelectTemplate={setSelectedTemplate}
        />
      );
      case 'outline': return <OutlineView slides={slides} />;
      case 'preview': return <PreviewView slides={slides} lessonPlan={lessonPlan} interaction={interaction} onExport={handleExport} currentUser={currentUser} />;
      case 'knowledge': return (
        <KnowledgeBaseView
          items={knowledgeItems}
          onUpload={handleKnowledgeUpload}
          onDeleteItem={handleKnowledgeDeleteItem}
          onUpdateItem={handleKnowledgeUpdateItem}
        />
      );
      case 'templates': return <TemplateLibraryPage onSelectTemplate={(tpl: any) => {
        setSelectedTemplate(tpl);
        setActiveTab('dashboard');
      }} />;
      case 'exports': return <ExportsView records={exportRecords} onDelete={handleDeleteExport} />;
      case 'settings': return <SettingsView />;
      case 'profile': return <ProfileView currentUser={currentUser} onLogout={handleLogout} />;
      default: return (
        <DashboardView 
          setActiveTab={setActiveTab} 
          onGenerated={handleGenerated} 
          knowledgeItems={knowledgeItems} 
          messages={messages}
          setMessages={setMessages}
          currentUser={currentUser}
          selectedTemplate={selectedTemplate}
          onSelectTemplate={setSelectedTemplate}
        />
      );
    }
  };

  const getTitle = () => {
    switch (activeTab) {
      case 'dashboard': return '工作台';
      case 'outline': return '课件大纲';
      case 'preview': return '课件预览';
      case 'knowledge': return '知识库';
      case 'templates': return '模板库';
      case 'exports': return '导出记录';
      case 'settings': return '设置';
      case 'profile': return '个人中心';
      default: return '豆沙包';
    }
  };

  return (
    <div className="min-h-screen bg-[#f4fbf4] flex font-body">
      {isLoggedIn && <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} currentUser={currentUser} />}
      
      <main className={cn("flex-1 flex flex-col h-screen overflow-hidden transition-all", isLoggedIn ? "ml-64" : "ml-0")}>
        {isLoggedIn && <TopNav title={getTitle()} activeTab={activeTab} setActiveTab={setActiveTab} setShowOnboarding={setShowOnboarding} />}
        
        <div className={cn("flex-1 overflow-hidden", isLoggedIn ? "pt-16" : "pt-0")}>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab + (isLoggedIn ? 'in' : 'out')}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              {renderView()}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
