import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Bot, FileText, User } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Message } from '../../types';

interface ChatMessageProps {
  message: Message;
  isLast?: boolean;
  onGenerateConfirm?: () => void;
  generateBtnLabel?: string; // 新增：自定义按钮文字
  isGenerating?: boolean;
  currentUser?: { username?: string };
}

export const ChatMessage = ({ message, isLast, onGenerateConfirm, generateBtnLabel, isGenerating, currentUser }: ChatMessageProps) => {
  const isAssistant = message.role === 'assistant';

  return (
    <div className={cn("flex items-start gap-4 mb-8", !isAssistant ? "justify-end" : "justify-start")}>
      {isAssistant && (
        <div className="w-10 h-10 rounded-full bg-[#eef5ee] flex items-center justify-center border border-[#0d631b]/10 shrink-0 shadow-sm">
          <Bot className="w-6 h-6 text-[#0d631b]" />
        </div>
      )}
      
      <div className={cn(
        "flex flex-col gap-3 max-w-[85%]",
        !isAssistant ? "items-end" : "items-start"
      )}>
        <div className={cn(
          "p-6 shadow-sm relative group transition-all",
          isAssistant 
            ? "bg-white border border-black/5 rounded-2xl rounded-tl-none" 
            : "bg-gradient-to-br from-[#0d631b] to-[#2e7d32] text-white rounded-2xl rounded-tr-none shadow-[0_8px_32px_-8px_rgba(13,99,27,0.3)]"
        )}>
          {/* 文件附件展示 */}
          {message.fileInfo && (
            <div className={cn(
              "flex items-center gap-3 p-3 rounded-xl border mb-4",
              !isAssistant ? "bg-white/10 border-white/20" : "bg-[#f4fbf4] border-[#0d631b]/10"
            )}>
              <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center">
                <FileText className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold truncate">{message.fileInfo.name}</p>
                <p className="text-[10px] opacity-60 uppercase tracking-tighter">{message.fileInfo.size}</p>
              </div>
            </div>
          )}

          {/* Markdown 内容渲染 */}
          <div className={cn(
            "prose prose-sm max-w-none break-words",
            !isAssistant ? "prose-invert prose-p:text-white/90" : "prose-p:text-[#161d19]/80",
            "prose-headings:font-black prose-headings:tracking-tight prose-strong:text-[#0d631b] prose-code:bg-black/5 prose-code:px-1 prose-code:rounded",
            "prose-table:border prose-table:border-black/5 prose-th:bg-[#f4fbf4] prose-th:px-4 prose-th:py-2 prose-td:px-4 prose-td:py-2"
          )}>
            <ReactMarkdown 
              remarkPlugins={[remarkGfm, remarkMath]} 
              rehypePlugins={[rehypeKatex]}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* 生成确认交互区 (仅限 Assistant 且消息包含触发意图或作为特定组件参数) */}
          {isAssistant && isLast && onGenerateConfirm && !isGenerating && (
            <div className="mt-6 pt-6 border-t border-black/5 flex flex-col gap-4">
              <div className="flex items-start gap-3 p-4 bg-[#f4fbf4] rounded-2xl border border-[#0d631b]/10">
                <div className="w-8 h-8 rounded-full bg-[#0d631b] text-white flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-[#0d631b] mb-1">课件制作就绪</p>
                  <p className="text-[11px] text-[#0d631b]/60 leading-relaxed font-medium">
                    我已收集到足够的信息。点击下方按钮，我将为您生成完整的 PPT 大纲、详细教案及互动环节设计。
                  </p>
                </div>
              </div>
              <button 
                onClick={onGenerateConfirm}
                className="w-full bg-[#0d631b] text-white py-4 rounded-xl font-black text-sm shadow-lg hover:shadow-xl hover:scale-[1.01] active:scale-[0.99] transition-all flex items-center justify-center gap-2"
              >
                <span>{generateBtnLabel || '🚀 开始生成整套教学资料'}</span>
              </button>
            </div>
          )}
        </div>
        
        {/* 用户名或角色标识 */}
        <span className="text-[10px] font-bold text-black/20 uppercase tracking-[0.2em] px-1">
          {isAssistant ? "Dousha Assistant" : (currentUser?.username || "You")}
        </span>
      </div>

      {!isAssistant && (
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#0d631b] to-[#a3f69c] flex items-center justify-center text-white text-xs font-black shrink-0 shadow-md border-2 border-white">
          {currentUser?.username?.charAt(0).toUpperCase() || "U"}
        </div>
      )}
    </div>
  );
};
