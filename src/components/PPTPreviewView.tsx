import React, { useState, useEffect } from 'react';
import { Eye, AlertCircle, RefreshCw, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { PreviewSlide } from '../services/apiEnhanced';
import { MarkdownErrorBoundary } from './common/ErrorBoundary';
import { preprocessSlideContent } from '../utils/textUtils';
import { cn } from '../lib/utils';

interface PPTErrrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

class PPTErrrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  PPTErrrorBoundaryState
> {
  constructor(props: { children: React.ReactNode; fallback?: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): PPTErrrorBoundaryState {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[PPT错误边界] 捕获错误:', error);
    console.error('[PPT错误边界] 错误堆栈:', errorInfo.componentStack);
    this.setState({ errorInfo });
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 bg-red-50 border border-red-200 rounded-2xl">
          <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
          <h3 className="text-xl font-bold text-red-700 mb-2">PPT预览出错</h3>
          <p className="text-sm text-red-600 mb-4 text-center max-w-md">
            {this.state.error?.message || '组件渲染失败'}
          </p>
          <button
            onClick={this.handleRetry}
            className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors font-semibold"
          >
            <RefreshCw className="w-4 h-4" />
            重试
          </button>
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <details className="mt-4 w-full">
              <summary className="cursor-pointer text-xs text-red-500 hover:text-red-700">
                查看错误详情
              </summary>
              <pre className="mt-2 p-3 bg-red-100 rounded text-xs overflow-auto max-h-40">
                {this.state.error.stack}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

interface PPTPreviewViewProps {
  slides: any[];
  title: string;
  templateId?: string;
  onPreviewRender: () => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  renderedSlides?: PreviewSlide[];
  previewMode: 'outline' | 'rendered';
  onModeChange: (mode: 'outline' | 'rendered') => void;
  onExport?: () => void;
}

export const PPTPreviewView: React.FC<PPTPreviewViewProps> = ({
  slides,
  title,
  templateId,
  onPreviewRender,
  isLoading = false,
  error = null,
  renderedSlides = [],
  previewMode,
  onModeChange,
  onExport
}) => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setCurrentSlide(0);
  }, [slides, renderedSlides]);

  const handleRenderPreview = async () => {
    setLocalError(null);
    try {
      await onPreviewRender();
    } catch (err: any) {
      console.error('[PPTPreviewView] 渲染失败:', err);
      setLocalError(err.message || '预览渲染失败');
    }
  };

  const displayError = error || localError;
  const displaySlides = previewMode === 'rendered' && renderedSlides.length > 0 ? renderedSlides : slides;
  const totalSlides = displaySlides.length;

  if (slides.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#f0f4f0]">
        <div className="text-center opacity-40">
          <Eye className="w-16 h-16 mx-auto mb-4" />
          <p className="text-xl font-bold">暂无预览内容</p>
          <p className="text-sm mt-2">请先生成PPT内容</p>
        </div>
      </div>
    );
  }

  return (
    <PPTErrrorBoundary>
      <div className="flex-1 flex flex-col bg-[#f0f4f0] overflow-hidden">
        <div className="bg-white border-b border-black/5 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-3">
              <button
                onClick={() => onModeChange('outline')}
                className={cn(
                  "px-5 py-2 rounded-full font-bold transition-all",
                  previewMode === 'outline'
                    ? "bg-[#0d631b] text-white"
                    : "bg-[#eef5ee] text-[#161d19]/60 hover:bg-[#dde4dd]"
                )}
              >
                大纲预览
              </button>
              <button
                onClick={handleRenderPreview}
                disabled={isLoading}
                className={cn(
                  "px-5 py-2 rounded-full font-bold transition-all flex items-center gap-2",
                  previewMode === 'rendered'
                    ? "bg-[#0d631b] text-white"
                    : "bg-[#eef5ee] text-[#161d19]/60 hover:bg-[#dde4dd]",
                  isLoading && "opacity-50 cursor-not-allowed"
                )}
              >
                {isLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    渲染中...
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4" />
                    渲染预览
                  </>
                )}
              </button>
            </div>

            {onExport && (
              <button
                onClick={onExport}
                className="px-5 py-2 bg-[#0d631b] text-white rounded-full font-bold hover:opacity-90 transition-all flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                导出PPT
              </button>
            )}
          </div>
        </div>

        {displayError && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-bold text-red-700">预览失败</p>
              <p className="text-xs text-red-600 mt-1">{displayError}</p>
            </div>
            <button
              onClick={handleRenderPreview}
              className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-semibold hover:bg-red-700 transition-colors"
            >
              重试
            </button>
          </div>
        )}

        <div className="flex-1 overflow-hidden relative">
          <AnimatePresence mode="wait">
            {isLoading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm"
              >
                <div className="text-center">
                  <RefreshCw className="w-12 h-12 text-[#0d631b] animate-spin mx-auto mb-4" />
                  <p className="text-lg font-bold text-[#0d631b]">正在渲染PPT预览...</p>
                  <p className="text-sm text-[#161d19]/60 mt-2">这可能需要几秒到几十秒</p>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="content"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="h-full flex flex-col"
              >
                <div className="flex-1 flex items-center justify-center p-8">
                  <div className="w-full max-w-4xl">
                    {previewMode === 'rendered' && renderedSlides.length > 0 ? (
                      <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
                        {renderedSlides[currentSlide]?.image ? (
                          <img
                            src={renderedSlides[currentSlide].image!}
                            alt={`幻灯片 ${currentSlide + 1}`}
                            className="w-full h-auto"
                          />
                        ) : (
                          <div className="p-8 text-center">
                            <p className="text-lg font-bold text-[#161d19]">
                              {renderedSlides[currentSlide]?.title || `第 ${currentSlide + 1} 页`}
                            </p>
                            <p className="text-sm text-[#161d19]/60 mt-2">
                              {renderedSlides[currentSlide]?.content_preview || '预览图片生成失败'}
                            </p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="bg-white rounded-2xl shadow-lg p-12">
                        <h2 className="text-3xl font-black text-[#0d631b] mb-6">
                          {slides[currentSlide]?.title || `第 ${currentSlide + 1} 页`}
                        </h2>
                        <div className="prose prose-green max-w-none">
                          <MarkdownErrorBoundary>
                            <div className="text-lg text-[#161d19]/80 leading-relaxed">
                              {preprocessSlideContent(slides[currentSlide])}
                            </div>
                          </MarkdownErrorBoundary>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-white border-t border-black/5 px-6 py-4">
                  <div className="flex items-center justify-between max-w-4xl mx-auto">
                    <button
                      onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
                      disabled={currentSlide === 0}
                      className="p-2 hover:bg-[#eef5ee] rounded-full text-[#161d19]/40 transition-all disabled:opacity-20"
                    >
                      <ChevronLeft className="w-6 h-6" />
                    </button>

                    <div className="flex items-center gap-4">
                      <span className="text-sm font-bold text-[#161d19]/60">
                        {currentSlide + 1} / {totalSlides}
                      </span>
                      <div className="w-32 h-2 bg-[#eef5ee] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#0d631b] transition-all"
                          style={{ width: `${((currentSlide + 1) / totalSlides) * 100}%` }}
                        />
                      </div>
                    </div>

                    <button
                      onClick={() => setCurrentSlide(Math.min(totalSlides - 1, currentSlide + 1))}
                      disabled={currentSlide === totalSlides - 1}
                      className="p-2 hover:bg-[#eef5ee] rounded-full text-[#161d19]/40 transition-all disabled:opacity-20"
                    >
                      <ChevronRight className="w-6 h-6" />
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </PPTErrrorBoundary>
  );
};

export default PPTPreviewView;
