import React, { useState } from 'react';
import { X, ChevronLeft, ChevronRight, Maximize2, Monitor } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import { cn } from '../../lib/utils';
import { PPTTemplate } from '../../types';

interface TemplateFullPreviewProps {
  template: PPTTemplate;
  onClose: () => void;
}

export const TemplateFullPreview: React.FC<TemplateFullPreviewProps> = ({ template, onClose }) => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const slides = template.templateData?.slidesStructure || [];
  
  if (slides.length === 0) {
    return (
      <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl p-10 max-w-md w-full text-center">
          <X className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-bold mb-2">暂无预览内容</h3>
          <p className="text-gray-500 mb-6">该模板尚未解析完成，或者不包含可预览的幻灯片结构。</p>
          <button onClick={onClose} className="w-full py-3 bg-[#0d631b] text-white rounded-xl font-bold">关闭</button>
        </div>
      </div>
    );
  }

  const handlePrev = () => setCurrentSlide(prev => Math.max(0, prev - 1));
  const handleNext = () => setCurrentSlide(prev => Math.min(slides.length - 1, prev + 1));

  return (
    <div className="fixed inset-0 z-[100] bg-[#161d19]/95 backdrop-blur-md flex flex-col overflow-hidden animate-in fade-in duration-300">
      {/* Header */}
      <header className="h-16 px-8 flex justify-between items-center border-b border-white/10 shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 rounded-lg bg-[#0d631b] flex items-center justify-center text-white font-bold">豆</div>
          <div>
            <h2 className="text-white font-bold leading-tight">{template.title}</h2>
            <p className="text-white/40 text-[10px] uppercase tracking-widest font-medium">模板全页面预览</p>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center bg-white/5 rounded-full px-4 py-1.5 gap-3 border border-white/5">
            <Monitor className="w-4 h-4 text-white/40" />
            <span className="text-white/60 text-sm font-medium">{currentSlide + 1} / {slides.length}</span>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-full text-white/60 hover:text-white transition-all"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 relative flex items-center justify-center p-8 lg:p-16">
        <button 
          onClick={handlePrev}
          disabled={currentSlide === 0}
          className="absolute left-8 z-10 p-4 hover:bg-white/10 rounded-full text-white/40 hover:text-white transition-all disabled:opacity-0 disabled:pointer-events-none"
        >
          <ChevronLeft className="w-10 h-10" />
        </button>

        <div className="w-full max-w-6xl aspect-[16/9] relative bg-white rounded-2xl shadow-2xl overflow-hidden group">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentSlide}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.02 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="absolute inset-0 p-12 flex flex-col items-center justify-center text-center"
            >
              {/* 模拟渲染 PPT 形状 */}
              {slides[currentSlide].shapes?.map((shape: any, idx: number) => {
                // 如果是占位符标题
                if (shape.name?.toLowerCase().includes('title') || idx === 0) {
                  return (
                    <h1 key={idx} className="text-4xl lg:text-5xl font-black text-[#0d631b] mb-8 tracking-tight">
                      {shape.text || "幻灯片标题内容"}
                    </h1>
                  );
                }
                
                // 如果是图片
                if (shape.image_data) {
                  return (
                    <div key={idx} className="w-full max-w-lg aspect-video rounded-xl overflow-hidden bg-gray-100 mb-6 shadow-sm border border-black/5">
                      <img src={shape.image_data} alt="slide component" className="w-full h-full object-cover" />
                    </div>
                  );
                }

                // 如果是正文
                if (shape.text) {
                  return (
                    <div key={idx} className="text-lg text-gray-700 max-w-2xl text-left font-medium leading-relaxed mb-4">
                      <ReactMarkdown>{shape.text}</ReactMarkdown>
                    </div>
                  );
                }

                return null;
              })}

              {/* 背景装饰（模拟） */}
              <div className="absolute top-0 left-0 w-full h-2 bg-[#0d631b]/20" />
              <div className="absolute bottom-6 right-8 text-[10px] text-gray-300 font-bold uppercase tracking-widest flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[#0d631b]" />
                豆沙包教师助手 · {template.title}
              </div>
            </motion.div>
          </AnimatePresence>

          <button className="absolute bottom-6 left-6 p-2 bg-black/5 hover:bg-black/10 rounded-full text-gray-400 opacity-0 group-hover:opacity-100 transition-all">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        <button 
          onClick={handleNext}
          disabled={currentSlide === slides.length - 1}
          className="absolute right-8 z-10 p-4 hover:bg-white/10 rounded-full text-white/40 hover:text-white transition-all disabled:opacity-0 disabled:pointer-events-none"
        >
          <ChevronRight className="w-10 h-10" />
        </button>
      </main>

      {/* Footer Navigation */}
      <footer className="h-24 bg-black/20 border-t border-white/5 flex items-center justify-center gap-4 px-8 overflow-x-auto no-scrollbar">
        {slides.map((_, idx) => (
          <button
            key={idx}
            onClick={() => setCurrentSlide(idx)}
            className={cn(
              "w-24 shrink-0 aspect-[16/9] rounded-lg border-2 transition-all flex items-center justify-center text-xs font-bold",
              currentSlide === idx 
                ? "border-[#0d631b] bg-[#0d631b]/20 text-white" 
                : "border-white/10 bg-white/5 text-white/20 hover:border-white/30"
            )}
          >
            P{idx + 1}
          </button>
        ))}
      </footer>
    </div>
  );
};
