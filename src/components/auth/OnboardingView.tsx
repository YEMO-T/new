import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, Bot, Layers, ArrowRight, ChevronRight, Check } from 'lucide-react';
import { cn } from '../../lib/utils';

interface OnboardingViewProps {
  onComplete: () => void;
}

const steps = [
  {
    title: "欢迎来到豆沙包",
    desc: "您的 AI 智能教学助手，将繁琐的教研流程转化为指尖的轻松对话。",
    icon: Sparkles,
    color: "from-blue-500 to-cyan-400",
    bg: "bg-blue-50"
  },
  {
    title: "对话即创作",
    desc: "只需输入课题，豆沙包即可为您自动生成大纲、PPT 及专业教案。",
    icon: Bot,
    color: "from-green-500 to-emerald-400",
    bg: "bg-green-50"
  },
  {
    title: "海量专业模板",
    desc: "套用来自全国名师的互动模板，支持多种格式一键导出分享。",
    icon: Layers,
    color: "from-purple-500 to-violet-400",
    bg: "bg-purple-50"
  }
];

export const OnboardingView = ({ onComplete }: OnboardingViewProps) => {
  const [currentStep, setCurrentStep] = useState(0);

  return (
    <div className="fixed inset-0 z-[400] bg-[#f8fbf8] flex items-center justify-center font-['Noto_Sans_SC',_sans-serif] overflow-hidden">
      {/* 背景光晕 */}
      <div className="absolute inset-0 z-0">
        <div className={cn("absolute inset-0 transition-colors duration-1000 opacity-30", steps[currentStep].bg)} />
      </div>

      <div className="relative z-10 max-w-5xl w-full mx-6 h-[640px] bg-white rounded-[48px] shadow-[0_40px_120px_-20px_rgba(0,0,0,0.08)] border border-black/5 flex overflow-hidden">
        {/* 左侧展示图 */}
        <div className={cn("hidden lg:flex w-[400px] bg-gradient-to-br items-center justify-center relative overflow-hidden transition-all duration-700", steps[currentStep].color)}>
          <div className="absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_center,#fff_1.5px,transparent_1.5px)] [background-size:32px_32px]"></div>
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ scale: 0.8, opacity: 0, rotate: -10 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 1.2, opacity: 0, rotate: 10 }}
              className="relative z-10 w-48 h-48 bg-white/20 backdrop-blur-xl rounded-[40px] border border-white/30 flex items-center justify-center shadow-2xl"
            >
              {React.createElement(steps[currentStep].icon, { className: "w-24 h-24 text-white" })}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* 右侧内容 */}
        <div className="flex-1 flex flex-col p-16 lg:p-24 relative">
          <div className="flex-1">
            <div className="flex gap-2 mb-12">
              {steps.map((_, i) => (
                <div 
                  key={i} 
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-500",
                    i === currentStep ? "w-10 bg-[#0d631b]" : "w-1.5 bg-[#0d631b]/10"
                  )}
                />
              ))}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="space-y-6"
              >
                <h2 className="text-5xl font-black text-[#161d19] tracking-tighter leading-tight">
                  {steps[currentStep].title}
                </h2>
                <p className="text-xl text-[#161d19]/50 font-medium leading-relaxed max-w-md">
                  {steps[currentStep].desc}
                </p>
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="mt-auto flex items-center justify-between">
            <button 
              onClick={onComplete}
              className="text-sm font-bold text-[#161d19]/30 hover:text-[#0d631b] transition-colors"
            >
              跳过指引
            </button>
            <div className="flex gap-4">
              {currentStep > 0 && (
                <button 
                  onClick={() => setCurrentStep(prev => prev - 1)}
                  className="px-8 py-4 rounded-2xl bg-[#f0f4f0] text-[#161d19]/60 font-bold hover:bg-[#e8ece8] transition-all"
                >
                  回看
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
                className="px-10 py-4 rounded-2xl bg-[#0d631b] text-white font-black shadow-[0_20px_40px_-10px_rgba(13,99,27,0.3)] hover:shadow-[0_24px_48px_-10px_rgba(13,99,27,0.4)] hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-3"
              >
                <span>{currentStep === steps.length - 1 ? "立即开启" : "继续了解"}</span>
                {currentStep === steps.length - 1 ? <Check className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
