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
  PenTool, 
  ArrowUp,
  FileText,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  PlayCircle,
  Copy,
  X,
  Brush,
  Eraser,
  Undo,
  Redo,
  Sparkles,
  RefreshCw,
  MoreHorizontal,
  Eye,
  Download,
  Trash2,
  FolderInput,
  Shield,
  Bot,
  Camera,
  Award,
  BookOpen,
  LogIn,
  UserPlus,
  ArrowRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import { cn } from './lib/utils';
import { Message, Template, KnowledgeItem, Slide, LessonPlan, Interaction } from './types';

// --- Components ---

const PulseLoader = ({ className }: { className?: string }) => (
  <div className={cn("flex gap-1 items-center", className)}>
    {[0, 1, 2].map((i) => (
      <motion.div
        key={i}
        className="w-1.5 h-1.5 bg-current rounded-full"
        animate={{
          scale: [1, 1.5, 1],
          opacity: [0.3, 1, 0.3],
        }}
        transition={{
          duration: 1,
          repeat: Infinity,
          delay: i * 0.2,
          ease: "easeInOut",
        }}
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

const Sidebar = ({ activeTab, setActiveTab }: { activeTab: string, setActiveTab: (tab: string) => void }) => {
  const menuItems = [
    { id: 'dashboard', label: '工作台', icon: LayoutDashboard },
    { id: 'knowledge', label: '知识库', icon: Database },
    { id: 'templates', label: '模板库', icon: Layers },
    { id: 'exports', label: '导出记录', icon: History },
    { id: 'sketch', label: '草图识别', icon: PenTool },
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
          <div className="w-10 h-10 rounded-full bg-[#dde4dd] overflow-hidden">
            <img 
              src="https://picsum.photos/seed/teacher/100/100" 
              alt="Avatar" 
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
          </div>
          <div>
            <p className="text-sm font-bold text-[#161d19]">王老师</p>
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

import { chatWithGemini, analyzeSketch, generateCourseware, MultimodalPart } from './services/gemini';
import { exportToPPTX, exportToDOCX } from './services/export';

// --- Components ---

const KnowledgeBaseView = ({ items, onUpload }: { items: KnowledgeItem[], onUpload: () => void }) => {
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
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-10 h-10 rounded-lg flex items-center justify-center",
                        item.type === 'pdf' ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"
                      )}>
                        <FileText className="w-5 h-5" />
                      </div>
                      <span className="font-bold text-[#161d19]">{item.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-[#161d19]/60">{item.size}</td>
                  <td className="px-6 py-4 text-sm text-[#161d19]/60">{item.date}</td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      {item.tags.map(tag => (
                        <span key={tag} className="px-2 py-0.5 bg-[#eef5ee] text-[#0d631b] text-[10px] font-bold rounded uppercase">{tag}</span>
                      ))}
                    </div>
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
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-2 hover:bg-white rounded-full text-[#161d19]/60 hover:text-[#0d631b] shadow-sm transition-all"><Eye className="w-4 h-4" /></button>
                      <button className="p-2 hover:bg-white rounded-full text-[#161d19]/60 hover:text-red-600 shadow-sm transition-all"><Trash2 className="w-4 h-4" /></button>
                    </div>
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

const ExportsView = () => {
  const records = [
    { id: '1', title: '初中数学-二次函数课件', format: 'PPTX', date: '2024-03-20 14:30', size: '12.4MB' },
    { id: '2', title: '英语语法-时态练习题', format: 'PDF', date: '2024-03-19 09:15', size: '2.1MB' },
    { id: '3', title: '物理实验-电路图演示', format: 'HTML', date: '2024-03-18 16:45', size: '5.8MB' },
  ];

  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <h2 className="text-4xl font-extrabold tracking-tight text-[#161d19] mb-2">📜 导出记录</h2>
      <p className="text-[#2a6b2c] font-medium mb-10">回顾并下载您生成的所有教学资源</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {records.map((record) => (
          <div key={record.id} className="bg-white p-6 rounded-2xl border border-black/5 shadow-sm hover:shadow-md transition-all group">
            <div className="flex justify-between items-start mb-4">
              <div className="w-12 h-12 rounded-xl bg-[#eef5ee] flex items-center justify-center text-[#0d631b]">
                <Download className="w-6 h-6" />
              </div>
              <span className="px-3 py-1 bg-[#0d631b]/10 text-[#0d631b] text-[10px] font-bold rounded-md">{record.format}</span>
            </div>
            <h3 className="font-bold text-[#161d19] mb-1">{record.title}</h3>
            <p className="text-xs text-[#161d19]/40 mb-4">{record.date} · {record.size}</p>
            <div className="flex gap-2">
              <button className="flex-1 py-2 rounded-full bg-[#0d631b] text-white text-xs font-bold hover:opacity-90 transition-all">重新下载</button>
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

const PreviewView = ({ slides, lessonPlan, interaction }: { slides: Slide[], lessonPlan: LessonPlan | null, interaction: Interaction | null }) => {
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
              <PenTool className="w-5 h-5" /> 课后作业
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
          onClick={() => slides.length > 0 && exportToPPTX(slides)}
          className="px-8 py-3 rounded-full bg-[#0d631b] text-white font-bold shadow-lg hover:opacity-90 transition-all flex items-center gap-2"
        >
          <Download className="w-5 h-5" /> 导出 PPT (.pptx)
        </button>
        <button 
          onClick={() => lessonPlan && exportToDOCX(lessonPlan)}
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

const DashboardView = ({ setActiveTab, onGenerated, knowledgeItems, messages, setMessages }: { 
  setActiveTab: (tab: string) => void, 
  onGenerated: (data: any) => void, 
  knowledgeItems: KnowledgeItem[],
  messages: Message[],
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}) => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [attachedFile, setAttachedFile] = useState<{ name: string, data: string, mimeType: string, size: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = (event.target?.result as string).split(',')[1];
      setAttachedFile({
        name: file.name,
        data: base64,
        mimeType: file.type,
        size: (file.size / 1024 / 1024).toFixed(2) + 'MB'
      });
    };
    reader.readAsDataURL(file);
  };

  const handleSend = async () => {
    if ((!input.trim() && !attachedFile) || isLoading) return;
    
    const userMsg: Message = { 
      id: Date.now().toString(), 
      role: 'user', 
      content: input || (attachedFile ? `上传了文件: ${attachedFile.name}` : ''),
      type: attachedFile ? 'file' : 'text',
      fileInfo: attachedFile ? {
        name: attachedFile.name,
        size: attachedFile.size,
        status: 'completed',
        mimeType: attachedFile.mimeType,
        data: attachedFile.data
      } : undefined
    };

    const currentInput = input;
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    
    const multimodalFiles: MultimodalPart[] = attachedFile ? [{
      inlineData: {
        data: attachedFile.data,
        mimeType: attachedFile.mimeType
      }
    }] : [];

    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    
    try {
      // Include knowledge base context
      const knowledgeContext = `当前知识库包含以下参考资料：${knowledgeItems.map(item => item.name).join(', ')}。您可以参考这些资料。`;
      const fullPrompt = `${knowledgeContext}\n\n用户输入：${currentInput}`;

      // Check if user wants to generate courseware
      const isGenerationIntent = currentInput.includes('生成') || currentInput.includes('制作') || currentInput.includes('开始');
      
      if (isGenerationIntent && messages.length >= 1) {
        const result = await generateCourseware(fullPrompt, [...messages, userMsg]);
        if (result && result.slides) {
          onGenerated(result);
          const aiMsg: Message = { 
            id: (Date.now() + 1).toString(), 
            role: 'assistant', 
            content: '太棒了！我已经根据我们的交流生成了完整的课件、教案和互动环节。您可以点击顶部的“预览”或“大纲”查看详情。您也可以继续在这里提出修改意见。' 
          };
          setMessages(prev => [...prev, aiMsg]);
          setActiveTab('preview');
        } else {
          const response = await chatWithGemini(fullPrompt, [...messages, userMsg], multimodalFiles);
          const aiMsg: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: response };
          setMessages(prev => [...prev, aiMsg]);
        }
      } else {
        const response = await chatWithGemini(fullPrompt, [...messages, userMsg], multimodalFiles);
        const aiMsg: Message = { 
          id: (Date.now() + 1).toString(), 
          role: 'assistant', 
          content: response 
        };
        setMessages(prev => [...prev, aiMsg]);
      }
    } catch (error) {
      console.error('Gemini Error:', error);
      const errorMsg: Message = { 
        id: (Date.now() + 1).toString(), 
        role: 'assistant', 
        content: '抱歉，我遇到了一些问题，请稍后再试。' 
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-white relative h-full">
      <div className="flex-1 overflow-y-auto px-10 py-8" ref={scrollRef}>
        <div className="max-w-[900px] mx-auto flex flex-col gap-8">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex items-start gap-4", msg.role === 'user' ? "justify-end" : "")}>
              {msg.role === 'assistant' && (
                <div className="w-9 h-9 rounded-full bg-[#eef5ee] flex items-center justify-center border border-[#0d631b]/20 shrink-0">
                  <Bot className="w-5 h-5 text-[#0d631b]" />
                </div>
              )}
              <div className={cn(
                "p-6 max-w-[80%] shadow-sm flex flex-col gap-4",
                msg.role === 'assistant' 
                  ? "bg-white border border-black/5 rounded-2xl rounded-tl-none" 
                  : "bg-gradient-to-br from-[#2e7d32] to-[#43a047] text-white rounded-2xl rounded-tr-none"
              )}>
                {msg.fileInfo && (
                  <div className={cn(
                    "flex items-center gap-3 p-3 rounded-xl border",
                    msg.role === 'user' ? "bg-white/10 border-white/20" : "bg-[#f4fbf4] border-[#0d631b]/10"
                  )}>
                    <FileText className="w-5 h-5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold truncate">{msg.fileInfo.name}</p>
                      <p className="text-[10px] opacity-60">{msg.fileInfo.size}</p>
                    </div>
                  </div>
                )}
                <div className="prose prose-sm max-w-none prose-p:leading-relaxed prose-headings:text-[#0d631b] prose-strong:text-[#0d631b]">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              </div>
              {msg.role === 'user' && (
                <div className="w-9 h-9 rounded-full overflow-hidden shrink-0">
                  <img src="https://picsum.photos/seed/teacher/100/100" alt="User" className="w-full h-full object-cover" />
                </div>
              )}
            </div>
          ))}
          {isLoading && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-4"
            >
              <div className="w-9 h-9 rounded-full bg-[#eef5ee] flex items-center justify-center border border-[#0d631b]/20 shrink-0">
                <Bot className="w-5 h-5 text-[#0d631b]" />
              </div>
              <div className="bg-white border border-black/5 p-4 rounded-2xl rounded-tl-none shadow-sm">
                <PulseLoader className="text-[#0d631b]" />
              </div>
            </motion.div>
          )}
        </div>
      </div>

      <div className="px-10 pb-8 bg-white pt-2">
        <div className="max-w-[900px] mx-auto">
          <div className="flex gap-2 mb-4 overflow-x-auto pb-2 no-scrollbar">
            {[
              { label: '📝 生成教案', prompt: '帮我针对“二次函数”生成一份详细的初中数学教案。' },
              { label: '📊 制作课件', prompt: '请为“光合作用”设计一份包含 5 页幻灯片的大纲。' },
              { label: '❓ 设计练习', prompt: '生成 3 道关于“动量守恒”的物理选择题及解析。' },
              { label: '🔍 错题分析', prompt: '我上传了一份学生错题，请帮我分析知识盲点。' }
            ].map(s => (
              <button 
                key={s.label} 
                onClick={() => { setInput(s.prompt); }}
                className="px-4 py-2 rounded-full border border-black/10 text-xs font-bold text-[#161d19]/60 hover:border-[#0d631b] hover:text-[#0d631b] transition-all whitespace-nowrap bg-white shadow-sm"
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="relative flex items-center p-2 bg-white border-2 border-[#0d631b] rounded-full shadow-lg">
            <div className="flex gap-1 ml-2">
              <button className="w-10 h-10 rounded-full flex items-center justify-center text-[#0d631b] hover:bg-[#eef5ee] transition-colors"><Mic className="w-5 h-5" /></button>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-colors",
                  attachedFile ? "bg-[#0d631b] text-white" : "text-[#0d631b] hover:bg-[#eef5ee]"
                )}
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                onChange={handleFileUpload}
                accept="image/*,application/pdf,.doc,.docx"
              />
              <button 
                onClick={() => setActiveTab('sketch')}
                className="w-10 h-10 rounded-full flex items-center justify-center text-[#0d631b] hover:bg-[#eef5ee] transition-colors"
              >
                <PenTool className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 flex flex-col min-w-0">
              {attachedFile && (
                <div className="px-4 py-1 flex items-center justify-between bg-[#f4fbf4] rounded-lg mx-2 mb-1">
                  <span className="text-[10px] font-bold text-[#0d631b] truncate max-w-[200px]">{attachedFile.name}</span>
                  <button onClick={() => setAttachedFile(null)} className="text-[#161d19]/40 hover:text-red-500"><X className="w-3 h-3" /></button>
                </div>
              )}
              <input 
                className="w-full border-none focus:ring-0 text-sm px-4 text-[#161d19]" 
                placeholder={attachedFile ? "为上传的文件添加说明..." : "告诉豆沙包你想生成什么课件..."} 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              />
            </div>
            <button 
              onClick={handleSend}
              className="w-10 h-10 rounded-full bg-[#0d631b] flex items-center justify-center text-white hover:opacity-90 transition-opacity ml-2 shrink-0"
            >
              <ArrowUp className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const SketchView = ({ setActiveTab }: { setActiveTab: (tab: string) => void }) => {
  const [sketchImage, setSketchImage] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<any[]>([
    { label: '数学模型', title: '二次函数曲线', desc: 'y = ax² + bx + c' },
    { label: '图形组件', title: '抛物线图像', desc: '开口向上, 顶点(0,0)' }
  ]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSketchUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      const base64WithPrefix = event.target?.result as string;
      const base64 = base64WithPrefix.split(',')[1];
      setSketchImage(base64WithPrefix);
      
      setIsAnalyzing(true);
      try {
        const results = await analyzeSketch(base64, file.type);
        setAnalysisResults(results);
      } catch (error) {
        console.error("Sketch Analysis Error:", error);
      } finally {
        setIsAnalyzing(false);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-11 h-full overflow-hidden">
      <header className="w-full max-w-[1140px] mb-8">
        <h2 className="text-4xl font-extrabold tracking-tighter text-[#161d19] mb-2">手绘草图识别</h2>
        <p className="text-[#2a6b2c] font-medium">将您的教学灵感瞬间转化为数字课件节点</p>
      </header>
      
      <div className="w-full max-w-[1140px] flex gap-8 h-[600px]">
        <div className="flex-1 bg-white rounded-lg overflow-hidden relative shadow-xl flex flex-col border border-black/5">
          <div className="absolute top-6 left-6 z-10 bg-white/60 backdrop-blur-md p-2 rounded-2xl flex flex-col gap-2 shadow-sm border border-black/5">
            <button 
              onClick={() => fileInputRef.current?.click()}
              className="w-10 h-10 flex items-center justify-center rounded-xl bg-[#0d631b] text-white"
            >
              <Plus className="w-5 h-5" />
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              onChange={handleSketchUpload} 
              accept="image/*" 
            />
            <button className="w-10 h-10 flex items-center justify-center rounded-xl hover:bg-[#dde4dd] text-[#40493d] transition-colors"><Brush className="w-5 h-5" /></button>
            <button className="w-10 h-10 flex items-center justify-center rounded-xl hover:bg-[#dde4dd] text-[#40493d] transition-colors"><Eraser className="w-5 h-5" /></button>
            <div className="w-6 h-[1px] bg-black/10 mx-auto my-1"></div>
            <button className="w-10 h-10 flex items-center justify-center rounded-xl hover:bg-[#dde4dd] text-[#40493d] transition-colors"><Undo className="w-5 h-5" /></button>
            <button className="w-10 h-10 flex items-center justify-center rounded-xl hover:bg-[#dde4dd] text-[#40493d] transition-colors"><Redo className="w-5 h-5" /></button>
          </div>
          
          <div className="flex-1 flex items-center justify-center p-12 bg-[radial-gradient(#e9f0e9_1px,transparent_1px)] [background-size:24px_24px]">
            <div className="w-full h-full relative border border-dashed border-black/10 rounded-md flex items-center justify-center overflow-hidden">
              {sketchImage ? (
                <img 
                  src={sketchImage} 
                  alt="Sketch" 
                  className={cn("max-w-full max-h-full object-contain transition-opacity", isAnalyzing ? "opacity-40" : "opacity-100")}
                />
              ) : (
                <img 
                  src="https://picsum.photos/seed/sketch/800/500" 
                  alt="Sketch Placeholder" 
                  className="max-w-full max-h-full opacity-20"
                />
              )}
              {isAnalyzing && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-white/40 backdrop-blur-[2px] z-20"
                >
                  <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center shadow-xl border border-[#0d631b]/10">
                    <RefreshCw className="w-8 h-8 text-[#0d631b] animate-spin" />
                  </div>
                  <div className="bg-white/80 backdrop-blur-md px-6 py-2 rounded-full shadow-lg border border-[#0d631b]/10 flex items-center gap-3">
                    <p className="text-[#0d631b] font-bold">豆沙包正在识别中</p>
                    <PulseLoader className="text-[#0d631b]" />
                  </div>
                </motion.div>
              )}
              {!sketchImage && !isAnalyzing && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <p className="text-sm text-black/20 font-medium">点击左上角 + 按钮上传您的教学草图</p>
                </div>
              )}
            </div>
          </div>
          
          <div className="h-12 px-6 flex items-center justify-between bg-[#eef5ee]/50 text-xs text-[#40493d] font-medium">
            <div className="flex items-center gap-4">
              <span>画布大小: 800 x 500 px</span>
              <span>缩放: 100%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={cn("w-2 h-2 rounded-full", isAnalyzing ? "bg-orange-500 animate-pulse" : "bg-[#2a6b2c]")}></span>
              <span>{isAnalyzing ? "正在识别" : "准备就绪"}</span>
            </div>
          </div>
        </div>

        <aside className="w-[300px] flex flex-col gap-4">
          <div className="flex-1 bg-[#dde4dd]/40 rounded-lg p-6 flex flex-col border border-black/5">
            <div className="flex items-center gap-2 mb-6">
              <Sparkles className="w-5 h-5 text-[#0d631b]" />
              <h3 className="font-bold text-[#161d19] tracking-tight">智能识别结果</h3>
            </div>
            
            <div className="flex-1 space-y-4 overflow-y-auto pr-2">
              {analysisResults.length > 0 ? analysisResults.map((node, i) => (
                <motion.div 
                  key={i} 
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="bg-white p-4 rounded-2xl shadow-sm border border-[#0d631b]/5"
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-[10px] font-bold text-[#0d631b] uppercase tracking-tighter">{node.label}</span>
                    <CheckCircle2 className="w-3 h-3 text-[#707a6c]" />
                  </div>
                  <p className="text-sm font-semibold text-[#161d19]">{node.title}</p>
                  <p className="text-xs text-[#40493d]/70 mt-1">{node.desc}</p>
                </motion.div>
              )) : (
                <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
                  <Database className="w-10 h-10 mb-2" />
                  <p className="text-xs font-bold">暂无识别结果</p>
                </div>
              )}
            </div>

            <div className="mt-6 space-y-3">
              <button 
                onClick={() => setActiveTab('outline')}
                disabled={analysisResults.length === 0 || isAnalyzing}
                className="w-full bg-gradient-to-r from-[#0d631b] to-[#2e7d32] text-white py-3.5 rounded-full font-bold shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-5 h-5" />
                应用到课件
              </button>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="w-full bg-[#e3eae3] text-[#161d19] py-3.5 rounded-full font-bold hover:bg-[#dde4dd] transition-all flex items-center justify-center gap-2"
              >
                <RefreshCw className="w-5 h-5" />
                重新识别
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

const TemplateView = ({ setActiveTab }: { setActiveTab: (tab: string) => void }) => {
  const [isLoading, setIsLoading] = useState(true);
  const templates: Template[] = [
    { id: '1', title: '基础几何学互动讲义', description: '涵盖平面几何核心概念，包含交互式练习。', author: '李老师', category: '数学', usageCount: '1.2k', image: 'https://picsum.photos/seed/math/400/300' },
    { id: '2', title: '植物的光合作用百科', description: '生动的生物学课件，包含动画演示。', author: '张老师', category: '生物', usageCount: '856', image: 'https://picsum.photos/seed/bio/400/300' },
    { id: '3', title: '诗词赏析与创作练习', description: '优美的语文课件，激发学生创作灵感。', author: '陈老师', category: '语文', usageCount: '2.3k', image: 'https://picsum.photos/seed/poem/400/300' },
    { id: '4', title: '未来信息技术发展史', description: '科技感十足的课件，探索IT前沿。', author: '王老师', category: '信息', usageCount: '540', image: 'https://picsum.photos/seed/tech/400/300' },
  ];

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 1500);
    return () => clearTimeout(timer);
  }, []);

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

const ProfileView = () => {
  return (
    <div className="flex-1 p-11 h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-3xl p-10 border border-black/5 shadow-sm flex items-center gap-10 mb-10">
          <div className="w-32 h-32 rounded-full bg-gradient-to-br from-[#0d631b] to-[#a3f69c] flex items-center justify-center text-white text-5xl font-black shadow-xl">
            G
          </div>
          <div>
            <h2 className="text-4xl font-black text-[#161d19] tracking-tighter">Gohil Sudarsan</h2>
            <p className="text-[#0d631b] font-bold mt-1">高级教师 | 数学学科带头人</p>
            <div className="flex gap-4 mt-6">
              <div className="text-center px-6 py-2 bg-[#f4fbf4] rounded-2xl">
                <p className="text-xl font-black text-[#0d631b]">128</p>
                <p className="text-[10px] text-[#161d19]/40 uppercase font-bold">课件数量</p>
              </div>
              <div className="text-center px-6 py-2 bg-[#f4fbf4] rounded-2xl">
                <p className="text-xl font-black text-[#0d631b]">3.5k</p>
                <p className="text-[10px] text-[#161d19]/40 uppercase font-bold">获得点赞</p>
              </div>
              <div className="text-center px-6 py-2 bg-[#f4fbf4] rounded-2xl">
                <p className="text-xl font-black text-[#0d631b]">12</p>
                <p className="text-[10px] text-[#161d19]/40 uppercase font-bold">教学荣誉</p>
              </div>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-8">
          <div className="bg-white rounded-3xl p-8 border border-black/5 shadow-sm">
            <h3 className="text-xl font-bold text-[#161d19] mb-6">个人简介</h3>
            <p className="text-[#161d19]/60 leading-relaxed">
              深耕初高中数学教育10年，擅长利用AI技术辅助教学设计。致力于打造互动性强、趣味性高的现代化课堂，已累计服务超过5000名学生。
            </p>
          </div>
          <div className="bg-white rounded-3xl p-8 border border-black/5 shadow-sm">
            <h3 className="text-xl font-bold text-[#161d19] mb-6">我的成就</h3>
            <div className="space-y-4">
              {['年度优秀教师', '课件设计大赛一等奖', 'AI教育先锋奖'].map((award, i) => (
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
            onClick={() => window.location.reload()}
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

const OnboardingView = ({ onComplete }: { onComplete: () => void }) => {
  const steps = [
    {
      title: "欢迎来到豆沙包",
      desc: "您的 AI 智能教学助手，让课件制作变得前所未有的简单。",
      icon: Sparkles,
      color: "bg-blue-500"
    },
    {
      title: "对话即创作",
      desc: "只需在工作台输入您的教学目标，豆沙包即可为您生成完整的大纲与内容。",
      icon: Bot,
      color: "bg-green-500"
    },
    {
      title: "智能草图识别",
      desc: "手绘灵感瞬间数字化，自动识别几何图形与数学公式。",
      icon: PenTool,
      color: "bg-orange-500"
    },
    {
      title: "海量模板库",
      desc: "一键套用精美模板，支持多种格式导出，适配各种教学场景。",
      icon: Layers,
      color: "bg-purple-500"
    }
  ];

  const [currentStep, setCurrentStep] = useState(0);

  return (
    <div className="fixed inset-0 z-[200] bg-[#f4fbf4] flex items-center justify-center font-['Noto_Sans_SC',_sans-serif]">
      <div className="max-w-4xl w-full p-12 bg-white rounded-[40px] shadow-2xl border border-black/5 flex flex-col items-center text-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex flex-col items-center"
          >
            <div className={cn("w-24 h-24 rounded-3xl flex items-center justify-center text-white mb-8 shadow-lg", steps[currentStep].color)}>
              {React.createElement(steps[currentStep].icon, { className: "w-12 h-12" })}
            </div>
            <h2 className="text-4xl font-black text-[#161d19] mb-4 tracking-tight">{steps[currentStep].title}</h2>
            <p className="text-xl text-[#161d19]/60 max-w-lg leading-relaxed">{steps[currentStep].desc}</p>
          </motion.div>
        </AnimatePresence>

        <div className="flex gap-2 mt-12 mb-12">
          {steps.map((_, i) => (
            <div 
              key={i} 
              className={cn(
                "h-2 rounded-full transition-all duration-300",
                i === currentStep ? "w-8 bg-[#0d631b]" : "w-2 bg-[#0d631b]/20"
              )}
            />
          ))}
        </div>

        <div className="flex gap-4">
          {currentStep > 0 && (
            <button 
              onClick={() => setCurrentStep(prev => prev - 1)}
              className="px-8 py-4 rounded-2xl border border-black/10 text-[#161d19]/60 font-bold hover:bg-[#f4fbf4] transition-all"
            >
              上一步
            </button>
          )}
          <button 
            onClick={() => {
              if (currentStep < steps.length - 1) {
                setCurrentStep(prev => prev + 1);
              } else {
                onComplete();
              }
            }}
            className="px-12 py-4 rounded-2xl bg-[#0d631b] text-white font-bold shadow-xl hover:opacity-90 transition-all flex items-center gap-2"
          >
            {currentStep === steps.length - 1 ? "立即开始" : "下一步"}
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

const LoginView = ({ onLogin }: { onLogin: () => void }) => {
  const [isLogin, setIsLogin] = useState(true);

  return (
    <div className="fixed inset-0 z-[300] bg-[#e9f0e9] flex font-['Noto_Sans_SC',_sans-serif]">
      <div className="flex-1 flex flex-col items-center justify-center p-20 relative overflow-hidden">
        <div className="absolute top-[-10%] right-[-10%] w-[60%] aspect-square bg-[#0d631b]/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[60%] aspect-square bg-[#a3f69c]/10 rounded-full blur-3xl"></div>
        
        <div className="relative z-10 text-center mb-12">
          <div className="w-24 h-24 rounded-[32px] bg-[#0d631b] flex items-center justify-center text-white font-black text-5xl shadow-2xl mx-auto mb-8">豆</div>
          <h1 className="text-6xl font-black text-[#0d631b] tracking-tighter mb-4">豆沙包</h1>
          <p className="text-xl text-[#161d19]/60 font-medium tracking-widest uppercase">AI 驱动的下一代教学助手</p>
        </div>

        <div className="w-full max-w-md bg-white rounded-[40px] p-10 shadow-2xl border border-black/5 relative z-10">
          <div className="flex gap-8 mb-10 border-b border-black/5">
            <button 
              onClick={() => setIsLogin(true)}
              className={cn(
                "pb-4 text-lg font-bold transition-all relative",
                isLogin ? "text-[#0d631b]" : "text-[#161d19]/40"
              )}
            >
              登录
              {isLogin && <motion.div layoutId="auth-tab" className="absolute bottom-0 left-0 right-0 h-1 bg-[#0d631b] rounded-full" />}
            </button>
            <button 
              onClick={() => setIsLogin(false)}
              className={cn(
                "pb-4 text-lg font-bold transition-all relative",
                !isLogin ? "text-[#0d631b]" : "text-[#161d19]/40"
              )}
            >
              注册
              {!isLogin && <motion.div layoutId="auth-tab" className="absolute bottom-0 left-0 right-0 h-1 bg-[#0d631b] rounded-full" />}
            </button>
          </div>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-bold text-[#161d19] mb-2">手机号 / 邮箱</label>
              <input 
                type="text" 
                className="w-full bg-[#f4fbf4] border-none rounded-2xl px-6 py-4 text-sm focus:ring-2 focus:ring-[#0d631b] transition-all"
                placeholder="请输入您的账号"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-[#161d19] mb-2">密码</label>
              <input 
                type="password" 
                className="w-full bg-[#f4fbf4] border-none rounded-2xl px-6 py-4 text-sm focus:ring-2 focus:ring-[#0d631b] transition-all"
                placeholder="请输入密码"
              />
            </div>
            
            {!isLogin && (
              <div>
                <label className="block text-sm font-bold text-[#161d19] mb-2">确认密码</label>
                <input 
                  type="password" 
                  className="w-full bg-[#f4fbf4] border-none rounded-2xl px-6 py-4 text-sm focus:ring-2 focus:ring-[#0d631b] transition-all"
                  placeholder="请再次输入密码"
                />
              </div>
            )}

            <button 
              onClick={onLogin}
              className="w-full bg-[#0d631b] text-white py-5 rounded-2xl font-black text-lg shadow-xl hover:opacity-90 transition-all flex items-center justify-center gap-3"
            >
              {isLogin ? <LogIn className="w-6 h-6" /> : <UserPlus className="w-6 h-6" />}
              {isLogin ? "立即登录" : "创建账号"}
            </button>

            <div className="flex items-center justify-between text-xs font-bold text-[#161d19]/40">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="rounded border-black/10 text-[#0d631b] focus:ring-[#0d631b]" />
                记住我
              </label>
              <button className="hover:text-[#0d631b] transition-colors">忘记密码？</button>
            </div>
          </div>

          <div className="mt-10 pt-10 border-t border-black/5">
            <p className="text-center text-xs font-bold text-[#161d19]/40 mb-6 uppercase tracking-widest">第三方快捷登录</p>
            <div className="flex justify-center gap-6">
              {['WeChat', 'QQ', 'DingTalk'].map(platform => (
                <button key={platform} className="w-12 h-12 rounded-2xl bg-[#f4fbf4] flex items-center justify-center text-[#161d19]/60 hover:bg-[#0d631b] hover:text-white transition-all shadow-sm">
                  <span className="text-[10px] font-black">{platform[0]}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      
      <div className="hidden lg:flex flex-1 bg-[#0d631b] relative items-center justify-center p-20 overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:40px_40px]"></div>
        <div className="relative z-10 text-white max-w-lg">
          <h2 className="text-7xl font-black tracking-tighter mb-8 leading-none">赋能每一位<br/>教育者</h2>
          <p className="text-2xl font-medium text-white/70 leading-relaxed mb-12">
            豆沙包通过先进的 AI 技术，将繁琐的课件制作流程简化为自然的对话，让老师回归教学本质。
          </p>
          <div className="flex gap-12">
            <div>
              <p className="text-5xl font-black mb-2">10k+</p>
              <p className="text-sm font-bold text-white/50 uppercase tracking-widest">活跃教师</p>
            </div>
            <div>
              <p className="text-5xl font-black mb-2">500k+</p>
              <p className="text-sm font-bold text-white/50 uppercase tracking-widest">生成课件</p>
            </div>
          </div>
        </div>
        <div className="absolute bottom-[-20%] right-[-10%] w-[80%] aspect-square bg-white/5 rounded-full blur-3xl"></div>
      </div>
    </div>
  );
};

// --- Main App ---

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([
    { id: '1', name: '2024初中数学教学大纲.pdf', type: 'pdf', size: '2.4MB', date: '2024-03-15', tags: ['大纲', '数学'], status: 'completed' },
    { id: '2', name: '几何学基础讲义.docx', type: 'docx', size: '1.1MB', date: '2024-03-10', tags: ['讲义', '几何'], status: 'completed' },
    { id: '3', name: '学生错题集锦_第一单元.pdf', type: 'pdf', size: '4.5MB', date: '2024-03-05', tags: ['错题', '分析'], status: 'syncing' },
  ]);

  // Courseware State
  const [slides, setSlides] = useState<Slide[]>([]);
  const [lessonPlan, setLessonPlan] = useState<LessonPlan | null>(null);
  const [interaction, setInteraction] = useState<Interaction | null>(null);

  // Chat History State
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: '您好，王老师！我是您的课件助手**豆沙包**。今天想为您准备哪一门课程的教学设计呢？您可以直接上传教材，或者告诉我您的教学目标。'
    }
  ]);

  const handleLogin = () => {
    setIsLoggedIn(true);
    setShowOnboarding(true);
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
      setTimeout(() => {
        setKnowledgeItems(prev => prev.map(item => item.id === newItem.id ? { ...item, status: 'completed' } : item));
      }, 2000);
    };
    input.click();
  };

  const handleGenerated = (data: any) => {
    if (data.slides) setSlides(data.slides);
    if (data.lessonPlan) setLessonPlan(data.lessonPlan);
    if (data.interaction) setInteraction(data.interaction);
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
        />
      );
      case 'outline': return <OutlineView slides={slides} />;
      case 'preview': return <PreviewView slides={slides} lessonPlan={lessonPlan} interaction={interaction} />;
      case 'knowledge': return <KnowledgeBaseView items={knowledgeItems} onUpload={handleKnowledgeUpload} />;
      case 'templates': return <TemplateView setActiveTab={setActiveTab} />;
      case 'exports': return <ExportsView />;
      case 'settings': return <SettingsView />;
      case 'sketch': return <SketchView setActiveTab={setActiveTab} />;
      case 'profile': return <ProfileView />;
      default: return (
        <DashboardView 
          setActiveTab={setActiveTab} 
          onGenerated={handleGenerated} 
          knowledgeItems={knowledgeItems} 
          messages={messages}
          setMessages={setMessages}
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
      case 'sketch': return '草图识别';
      case 'profile': return '个人中心';
      default: return '豆沙包';
    }
  };

  return (
    <div className="min-h-screen bg-[#f4fbf4] flex font-body">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      <main className="ml-64 flex-1 flex flex-col h-screen overflow-hidden">
        <TopNav title={getTitle()} activeTab={activeTab} setActiveTab={setActiveTab} setShowOnboarding={setShowOnboarding} />
        
        <div className="flex-1 pt-16 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
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
