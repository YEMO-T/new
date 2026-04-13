import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Bot, Mic, Paperclip, ArrowUp, X, Sparkles, Plus, FileText, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Message, UserInfo, KnowledgeItem } from '../../types';
import { chatWithGeminiStream, getChatHistory, decomposeTopic, generateSlide, clearChatHistory } from '../../services/api';
import { ChatMessage } from './ChatMessage';

interface DashboardViewProps {
  setActiveTab: (tab: string) => void;
  onGenerated: (data: any) => void;
  knowledgeItems: KnowledgeItem[];
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  currentUser: UserInfo | null;
  selectedTemplate: any | null;
  onSelectTemplate: (tpl: any | null) => void;
}

const PulseLoader = ({ className }: { className?: string }) => (
  <div className={cn("flex gap-1.5 items-center px-2 py-1", className)}>
    {[0, 1, 2].map((i) => (
      <motion.div
        key={i}
        className="w-2 h-2 bg-current rounded-full"
        animate={{ scale: [1, 1.4, 1], opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2, ease: "easeInOut" }}
      />
    ))}
  </div>
);

export const DashboardView = ({ 
  setActiveTab, 
  onGenerated, 
  knowledgeItems, 
  messages, 
  setMessages, 
  currentUser,
  selectedTemplate,
  onSelectTemplate 
}: DashboardViewProps) => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [attachedFile, setAttachedFile] = useState<any>(null);
  const [showConfirmBtnId, setShowConfirmBtnId] = useState<string | null>(null);
  const [pendingTasks, setPendingTasks] = useState<any[] | null>(null);
  const [genTargetPrompt, setGenTargetPrompt] = useState<string>('');
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isStreamingRef = useRef(false);
  const lastScrollTimeRef = useRef(0);
  const historyLoadedRef = useRef(false);
  const welcomeShownRef = useRef(false);
  const isRequestPendingRef = useRef(false);

  const scrollToBottom = (instant = false) => {
    if (scrollRef.current) {
      const { scrollHeight, clientHeight, scrollTop } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 150;
      
      if (isAtBottom || instant) {
        scrollRef.current.scrollTo({
          top: scrollHeight,
          behavior: instant ? 'auto' : 'smooth'
        });
      }
    }
  };

  useEffect(() => {
    scrollToBottom(isStreamingRef.current);
  }, [messages, isLoading, showConfirmBtnId]);

  useEffect(() => {
    if (historyLoadedRef.current) return;
    if (!currentUser?.id) return;
    
    const loadHistory = async () => {
      historyLoadedRef.current = true;
      setIsLoading(true);
      
      try {
        const history = await getChatHistory(currentUser.id);
        if (history && history.length > 0) {
          const formattedMessages = history.map((m: any) => ({
            id: m.id.toString(),
            role: m.role,
            content: m.content,
            fileInfo: m.file_info
          }));
          setMessages(formattedMessages);
        }
      } catch (err) {
        console.error('加载历史记录失败:', err);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadHistory();
  }, [currentUser?.id]);

  useEffect(() => {
    if (welcomeShownRef.current) return;
    if (messages.length === 0 && !isLoading && currentUser) {
      welcomeShownRef.current = true;
      
      const knowledgeHint = knowledgeItems.length > 0 
        ? `\n\n📚 **知识库已就绪**：已检测到 ${knowledgeItems.length} 份教学资料，我会自动从中检索相关内容来辅助回答。`
        : '';
      
      const welcomeMsg: Message = {
        id: 'welcome-msg',
        role: 'assistant',
        content: `👋 您好${currentUser?.username ? '，' + currentUser.username : ''}！我是您的教学助手"豆沙包"。

我可以帮您：
- 🎨 **设计精美课件**（输入主题即可生成大纲与 PPT 内容）
- 📝 **编写详细教案**（根据课程目标生成教学设计）
- 💡 **策划课堂互动**（设计趣味导入、课堂习题）
- 📚 **智能问答**（基于您的知识库进行精准回答）${knowledgeHint}

您今天想准备什么课程？直接告诉我，或者试试下方的快捷功能。`
      };
      setMessages([welcomeMsg]);
    }
  }, [messages.length, isLoading, currentUser, knowledgeItems.length]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setAttachedFile({
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        data: (event.target?.result as string).split(',')[1],
        mimeType: file.type
      });
    };
    reader.readAsDataURL(file);
  };

  const handleNewChat = async () => {
    if (!window.confirm('确定要开启新一轮对话吗？这会清除当前的聊天记录。')) return;
    
    setIsLoading(true);
    const success = await clearChatHistory();
    if (success) {
      const welcomeMsg: Message = {
        id: 'welcome-' + Date.now(),
        role: 'assistant',
        content: '新对话已开启，请问有什么可以帮您？您也可以点击左下角的麦克风直接对我说话。'
      };
      setMessages([welcomeMsg]);
      setInput('');
      setAttachedFile(null);
      setShowConfirmBtnId(null);
      setPendingTasks(null);
    } else {
      alert('清空对话失败，请重试');
    }
    setIsLoading(false);
  };

  const handleSend = async () => {
    if (!input.trim() && !attachedFile) return;
    if (isRequestPendingRef.current) return;
    isRequestPendingRef.current = true;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      fileInfo: attachedFile ? {
        name: attachedFile.name,
        size: attachedFile.size,
        mimeType: attachedFile.mimeType,
        data: attachedFile.data
      } : undefined
    };

    const currentInput = input;
    const updatedHistory = [...messages, userMsg];
    setMessages(updatedHistory);
    setInput('');
    setIsLoading(true);
    setAttachedFile(null);
    setShowConfirmBtnId(null);
    if (fileInputRef.current) fileInputRef.current.value = '';

    const knowledgeContext = knowledgeItems.length > 0
      ? `\n（参考知识库：${knowledgeItems.map(item => item.name).join('、')}）`
      : '';
    const fullPrompt = `${currentInput}${knowledgeContext}`;

    const aiMsgId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: aiMsgId, role: 'assistant', content: '' }]);

    let fullResponse = '';
    let lastUpdate = Date.now();
    isStreamingRef.current = true;

    try {
      await chatWithGeminiStream(
        fullPrompt,
        updatedHistory,
        (token) => {
          fullResponse += token;
          const now = Date.now();
          if (now - lastUpdate > 60) {
            setMessages(prev =>
              prev.map(m => m.id === aiMsgId ? { ...m, content: fullResponse } : m)
            );
            lastUpdate = now;
          }
        },
        () => {
          isStreamingRef.current = false;
          setIsLoading(false);
          isRequestPendingRef.current = false;
          setMessages(prev =>
            prev.map(m => m.id === aiMsgId ? { ...m, content: fullResponse.replace('[READY_TO_GENERATE]', '').trim() } : m)
          );
          
          if (fullResponse.includes('[READY_TO_GENERATE]')) {
            setShowConfirmBtnId(aiMsgId);
          }
        },
        (errorText) => {
          isStreamingRef.current = false;
          setIsLoading(false);
          isRequestPendingRef.current = false;
          setMessages(prev =>
            prev.map(m => m.id === aiMsgId ? { ...m, content: `❌ **连接中断：** ${errorText}` } : m)
          );
        },
        currentUser?.id || 'default_user'
      );
    } catch (error) {
      console.error('Chat Error:', error);
      setIsLoading(false);
      isRequestPendingRef.current = false;
      setMessages(prev =>
        prev.map(m => m.id === aiMsgId ? { ...m, content: '抱歉，系统响应异常，请刷新重试。' } : m)
      );
    }
  };

  const startDecomposition = async (prompt: string) => {
    if (isRequestPendingRef.current) {
      console.log('[startDecomposition] 请求正在进行中，跳过');
      return;
    }
    isRequestPendingRef.current = true;
    
    setIsGenerating(true);
    setShowConfirmBtnId(null);
    setGenTargetPrompt(prompt);
    
    const genMsgId = (Date.now() + 2).toString();
    setMessages(prev => [...prev, {
      id: genMsgId,
      role: 'assistant',
      content: '🔍 **正在针对您的课题进行深度拆解并生成大纲...**\n\n⏱️ 预计需要 10-30 秒，请耐心等待...'
    }]);

    try {
      console.log('[startDecomposition] 开始调用 decomposeTopic API');
      const startTime = Date.now();
      
      const { tasks } = await decomposeTopic(
        prompt, 
        "通用", 
        "通用", 
        selectedTemplate?.id
      );
      
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`[startDecomposition] API 返回，耗时 ${elapsed}秒，任务数: ${tasks?.length || 0}`);

      if (!tasks || tasks.length === 0) {
        throw new Error('大纲生成异常，请重试。');
      }

      setPendingTasks(tasks);
      
      const outlineMarkdown = tasks.map((t: any) => `- ${t.page}. **${t.topic}**: ${t.description}`).join('\n');
      setMessages(prev => prev.map(m =>
        m.id === genMsgId ? { 
          ...m, 
          content: `📝 **大纲已就绪，共 ${tasks.length} 章节（耗时 ${elapsed}秒）：**\n\n${outlineMarkdown}\n\n✅ 确认大纲无误后，点击下方按钮开始为您精细化制作课件。` 
        } : m
      ));
      
      setShowConfirmBtnId(genMsgId);
    } catch (error: any) {
      console.error('[startDecomposition] 错误:', error);
      const errorMsg = error.message?.includes('超时') 
        ? `⚠️ **大纲生成超时。** ${error.message}\n\n💡 建议：请简化问题描述后重试，或刷新页面。`
        : `⚠️ **大纲生成失败。** ${error.message}\n\n💡 建议：请检查网络连接后重试。`;
      
      setMessages(prev => prev.map(m =>
        m.id === genMsgId ? { ...m, content: errorMsg } : m
      ));
    } finally {
      setIsGenerating(false);
      isRequestPendingRef.current = false;
    }
  };

  const startContentGeneration = async () => {
    if (!pendingTasks) {
      console.log('[startContentGeneration] 没有待处理的任务');
      return;
    }
    if (isRequestPendingRef.current) {
      console.log('[startContentGeneration] 请求正在进行中，跳过');
      return;
    }
    isRequestPendingRef.current = true;
    
    setIsGenerating(true);
    const genMsgId = showConfirmBtnId!; 
    setShowConfirmBtnId(null);
    
    let successCount = 0;
    let failCount = 0;

    try {
      setMessages(prev => prev.map(m =>
        m.id === genMsgId ? { ...m, content: `✍️ **大纲已确认，开始逐页精雕细琢内容... (0/${pendingTasks.length})**\n\n⏱️ 每页约需 5-15 秒，整体预计 ${Math.ceil(pendingTasks.length * 10 / 60)} 分钟` } : m
      ));

      const slides: any[] = [];
      const context = `主题: ${genTargetPrompt}; 大纲概览: ${pendingTasks.map((t: any) => t.topic).join(' -> ')}`;

      for (let i = 0; i < pendingTasks.length; i++) {
        const task = pendingTasks[i];
        setMessages(prev => prev.map(m =>
          m.id === genMsgId ? { 
            ...m, 
            content: `⚡ **正在处理第 ${i + 1}/${pendingTasks.length} 页：** ${task.topic}...\n\n✅ 已完成: ${successCount} 页 | ❌ 失败: ${failCount} 页` 
          } : m
        ));

        try {
          console.log(`[startContentGeneration] 开始生成第 ${i + 1} 页: ${task.topic}`);
          const slideContent = await generateSlide(
            task,
            context,
            currentUser?.id || 'default_user',
            selectedTemplate?.id
          );
          
          slides.push({
            title: slideContent?.title || task.topic || `第${i + 1}页`,
            content: slideContent?.content || [],
            page_type: slideContent?.page_type || slideContent?.type || 'content',
            type: slideContent?.type || task.layout_suggestion || 'content',
            layout_suggestion: slideContent?.layout_suggestion || 'bullet_points',
            variables: slideContent?.variables || {},
            images: slideContent?.images || [],
            tables: slideContent?.tables || [],
            charts: slideContent?.charts || [],
            page: task.page
          });
          successCount++;
          console.log(`[startContentGeneration] 第 ${i + 1} 页生成成功`);
        } catch (slideError: any) {
          console.error(`[startContentGeneration] 第${i + 1}页生成失败:`, slideError);
          failCount++;
          slides.push({
            title: task.topic || `第${i + 1}页`,
            content: [task.description || '内容生成失败，请手动编辑'],
            page_type: 'content',
            type: 'content',
            layout_suggestion: 'bullet_points',
            variables: {},
            images: [],
            tables: [],
            charts: [],
            page: task.page,
            error: slideError.message
          });
        }
      }

      if (slides.length === 0) {
        throw new Error('所有幻灯片生成失败，请重试');
      }

      const finalResult = {
        slides: slides,
        lessonPlan: {
          title: genTargetPrompt,
          objectives: ["核心算法讲解", "实践练习提升"],
          content: "详细教案已基于内容自动生成..."
        },
        interaction: { quiz: [], activities: [] }
      };

      onGenerated(finalResult);
      
      const statusMsg = failCount > 0 
        ? `🎨 **课件制作完成！** 共 ${slides.length} 页（成功 ${successCount} 页，失败 ${failCount} 页）。\n\n⚠️ 部分页面生成失败，已使用占位内容，请在预览中检查。`
        : `🎨 **整套课件制作完成！** 共 ${slides.length} 页，全部成功。点击顶部 **「预览」** 即可查看。`;
      
      setMessages(prev => prev.map(m =>
        m.id === genMsgId ? { ...m, content: statusMsg } : m
      ));
      
      setPendingTasks(null); 
      setActiveTab('preview');
    } catch (error: any) {
      console.error('[startContentGeneration] 最终错误:', error);
      const errorMsg = error.message?.includes('超时')
        ? `⚠️ **内容生成超时。** ${error.message}\n\n💡 建议：请尝试减少幻灯片数量或刷新页面重试。`
        : `⚠️ **内容生成中断。** ${error.message}\n\n💡 建议：请检查网络连接后重试。`;
      
      setMessages(prev => prev.map(m =>
        m.id === genMsgId ? { ...m, content: errorMsg } : m
      ));
    } finally {
      setIsGenerating(false);
      isRequestPendingRef.current = false;
    }
  };

  const triggerGeneration = async (history: Message[], prompt: string) => {
    if (!pendingTasks) {
      await startDecomposition(prompt);
    } else {
      await startContentGeneration();
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#fdfdfd] relative h-full font-['Noto_Sans_SC',_sans-serif] overflow-hidden">
      {/* 智能生成浮动建议栏 (Pop-up Suggestion) */}
      <AnimatePresence>
        {pendingTasks && !isGenerating && (
          <motion.div 
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="absolute bottom-36 left-0 right-0 z-50 px-6 pointer-events-none"
          >
            <div className="max-w-xl mx-auto pointer-events-auto">
              <div className="bg-white/80 backdrop-blur-xl border-2 border-[#0d631b]/30 rounded-3xl p-5 shadow-[0_25px_50px_-12px_rgba(13,99,27,0.25)] flex items-center justify-between gap-6 relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-r from-[#0d631b]/5 to-transparent pointer-none" />
                
                <div className="flex items-center gap-4 relative z-10">
                  <div className="w-12 h-12 rounded-2xl bg-[#0d631b] text-white flex items-center justify-center shadow-lg shadow-[#0d631b]/20 shrink-0">
                    <Sparkles className="w-6 h-6 animate-pulse" />
                  </div>
                  <div>
                    <h4 className="text-sm font-black text-[#0d631b]">教学大纲已就绪</h4>
                    <p className="text-[11px] text-[#0d631b]/60 font-bold uppercase tracking-wider">共 {pendingTasks.length} 个章节章节待生成</p>
                  </div>
                </div>

                <div className="flex gap-2 relative z-10">
                  <button 
                    onClick={() => { setPendingTasks(null); setShowConfirmBtnId(null); }}
                    className="px-4 py-3 rounded-xl text-[11px] font-black text-black/40 hover:bg-black/5 transition-all"
                  >
                    取消
                  </button>
                  <button 
                    onClick={startContentGeneration}
                    className="px-6 py-3 bg-[#0d631b] text-white rounded-xl text-[11px] font-black shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 transition-all flex items-center gap-2"
                  >
                    🚀 立即制作全套课件
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 对话列表区 */}
      <div className="flex-1 overflow-y-auto px-6 py-10 lg:px-20 no-scrollbar" ref={scrollRef}>
        <div className="max-w-4xl mx-auto">
          <AnimatePresence>
            {messages.map((msg, index) => (
              <ChatMessage 
                key={msg.id} 
                message={msg} 
                isLast={index === messages.length - 1}
                currentUser={currentUser || undefined}
                onGenerateConfirm={showConfirmBtnId === msg.id ? () => triggerGeneration(messages, msg.content) : undefined}
                generateBtnLabel={pendingTasks ? '✨ 确认大纲并生成详细课件' : '🚀 开始构思教学大纲'}
                isGenerating={isGenerating}
              />
            ))}
          </AnimatePresence>

          {isLoading && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex gap-4 items-start">
              <div className="w-10 h-10 rounded-full bg-[#eef5ee] flex items-center justify-center border border-[#0d631b]/10 shrink-0">
                <Bot className="w-6 h-6 text-[#0d631b]" />
              </div>
              <div className="bg-white border border-black/5 p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2">
                <span className="text-xs font-bold text-[#0d631b]/60">豆沙包正在思考</span>
                <PulseLoader className="text-[#0d631b]" />
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* 输入区 */}
      <div className="px-6 pb-8 bg-gradient-to-t from-white via-white to-transparent pt-10">
        <div className="max-w-4xl mx-auto">
          {/* Kimi 大模型标识与快捷建议 */}
          <div className="flex gap-2 mb-6 overflow-x-auto pb-2 no-scrollbar items-center">
            <div className="px-4 py-2 rounded-full border border-[#0d631b]/30 text-xs font-bold text-[#0d631b] bg-[#f4fbf4] flex items-center gap-1.5 flex-shrink-0 shadow-sm">
              🌙 Kimi 大模型
            </div>
            
            {selectedTemplate && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0d631b]/5 border border-[#0d631b]/20 rounded-full animate-in fade-in slide-in-from-left-2">
                <div className="w-6 h-6 rounded bg-white overflow-hidden border border-black/5">
                  <img src={selectedTemplate.image || selectedTemplate.thumbnail} alt="" className="w-full h-full object-cover" />
                </div>
                <span className="text-[10px] font-bold text-[#0d631b] max-w-[80px] truncate">{selectedTemplate.title}</span>
                <button 
                  onClick={() => onSelectTemplate(null)}
                  className="p-0.5 hover:bg-white rounded-full text-[#0d631b]/40 hover:text-red-500 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}

            <div className="h-5 w-[1px] bg-black/10 mx-2 shrink-0"></div>
            
            <button 
              onClick={handleNewChat}
              className="px-4 py-2 rounded-full border border-orange-200 text-xs font-bold text-orange-500 hover:bg-orange-50 transition-all flex items-center gap-1.5 flex-shrink-0 shadow-sm bg-white"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              开启新对话
            </button>

            <div className="h-5 w-[1px] bg-black/10 mx-2 shrink-0"></div>

            {[
              { label: '🚀 生成教案', prompt: '请帮我生成一份针对“小学三年级数学-长方形周长”的专业教案。' },
              { label: '🎨 创作课件', prompt: '帮我设计一个“恐龙灭绝”主题的科普 PPT 大纲。' },
              { label: '📝 设计习题', prompt: '围绕“英语过去式”生成 5 道互动选择题。' },
              { label: '💡 创意课堂', prompt: '帮我设计一个关于“光合作用”的课堂导入游戏。' }
            ].map(s => (
              <button 
                key={s.label} 
                onClick={() => setInput(s.prompt)}
                className="px-5 py-2.5 rounded-full border border-black/5 text-[11px] font-bold text-black/50 hover:border-[#0d631b] hover:text-[#0d631b] hover:bg-[#f4fbf4] transition-all whitespace-nowrap bg-white shadow-sm"
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="relative group p-2 bg-white border-2 border-[#0d631b] rounded-[32px] shadow-[0_20px_50px_-12px_rgba(13,99,27,0.15)] focus-within:shadow-[0_20px_50px_-12px_rgba(13,99,27,0.25)] transition-all">
            <div className="flex items-center gap-1 ml-2">
              <button 
                onMouseDown={async () => {
                  try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    const recorder = new MediaRecorder(stream);
                    mediaRecorderRef.current = recorder;
                    audioChunksRef.current = [];
                    
                    recorder.ondataavailable = (e) => {
                      if (e.data.size > 0) audioChunksRef.current.push(e.data);
                    };
                    
                    recorder.onstop = async () => {
                      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                      const formData = new FormData();
                      formData.append('file', audioBlob, 'voice.webm');
                      
                      try {
                        setIsLoading(true);
                        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/voice/transcribe`, {
                          method: 'POST',
                          body: formData
                        });
                        const data = await response.json();
                        if (data.text) {
                          setInput(data.text);
                        }
                      } catch (err) {
                        console.error('语音转写识别失败:', err);
                      } finally {
                        setIsLoading(false);
                      }
                      // 停止流
                      stream.getTracks().forEach(track => track.stop());
                    };
                    
                    recorder.start();
                    setIsRecording(true);
                  } catch (err) {
                    alert('无法访问麦克风，请检查权限设置');
                  }
                }}
                onMouseUp={() => {
                  if (mediaRecorderRef.current && isRecording) {
                    mediaRecorderRef.current.stop();
                    setIsRecording(false);
                  }
                }}
                className={cn(
                  "w-11 h-11 rounded-full flex items-center justify-center transition-all",
                  isRecording ? "bg-red-500 text-white animate-pulse" : "text-[#0d631b] hover:bg-[#f4fbf4]"
                )}
              >
                <Mic className="w-5 h-5" />
              </button>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "w-11 h-11 rounded-full flex items-center justify-center transition-all",
                  attachedFile ? "bg-[#0d631b] text-white" : "text-[#0d631b] hover:bg-[#f4fbf4]"
                )}
              >
                <Paperclip className="w-5 h-5" />
              </button>
              <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileUpload} accept="image/*,application/pdf,.doc,.docx" />
            </div>

            <div className="flex-1 flex flex-col min-w-0">
              {attachedFile && (
                <div className="px-4 py-1.5 flex items-center justify-between bg-[#f4fbf4] rounded-xl mx-3 mb-1.5 border border-[#0d631b]/10 animate-in fade-in slide-in-from-bottom-2">
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="w-3.5 h-3.5 text-[#0d631b]" />
                    <span className="text-[10px] font-bold text-[#0d631b] truncate max-w-[240px]">{attachedFile.name}</span>
                  </div>
                  <button onClick={() => setAttachedFile(null)} className="text-[#161d19]/30 hover:text-red-500 transition-colors ml-2"><X className="w-3.5 h-3.5" /></button>
                </div>
              )}
              <input 
                className="w-full border-none focus:ring-0 text-sm px-5 py-3 text-[#161d19] font-medium placeholder-black/20" 
                placeholder={attachedFile ? "为上传的文件添加引导说明..." : "随时告诉我您的教学灵感..."} 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              />
            </div>

            <button 
              onClick={handleSend}
              disabled={isLoading || (!input.trim() && !attachedFile)}
              className="w-12 h-12 rounded-full bg-[#0d631b] text-white shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 transition-all flex items-center justify-center disabled:opacity-30 disabled:scale-100 ml-2"
            >
              <ArrowUp className="w-6 h-6" />
            </button>
          </div>
          
          <p className="text-center mt-4 text-[10px] text-black/15 font-bold uppercase tracking-[0.25em]">
            Dousha Smart Education Engine v2.0
          </p>
        </div>
      </div>
    </div>
  );
};
