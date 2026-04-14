import React, { useState, useEffect, useCallback } from 'react';
import { saveAs } from 'file-saver';
import './PPTSlidePreview.css';

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

interface SlideData {
  slide_num: number;
  title: string;
  content_preview: string;
  image: string;
}

interface StructureSlide {
  index: number;
  layout_name: string;
  shapes: any[];
  background_color?: string;
}

interface PPTSlidePreviewProps {
  templateId: string;
  token: string;
  title?: string;
  templateData?: {
    slidesStructure?: StructureSlide[];
    themeColors?: Record<string, string>;
    fonts?: Record<string, any>;
  };
  onClose: () => void;
}

const CANVAS_W = 960;
const CANVAS_H = 540;
const SLIDE_W_EMU = 12192000;
const SLIDE_H_EMU = 6858000;

export const PPTSlidePreview: React.FC<PPTSlidePreviewProps> = ({
  templateId,
  token,
  title = 'PPT预览',
  templateData,
  onClose
}) => {
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showThumbnails, setShowThumbnails] = useState(false);
  const [previewType, setPreviewType] = useState<string>('loading');
  const [previewMessage, setPreviewMessage] = useState<string>('');

  const loadSlides = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPreviewType('loading');
    
    console.log('[PPTSlidePreview] 开始加载幻灯片, templateId:', templateId);
    
    try {
      if (!token) {
        throw new Error('未登录或 Token 已过期，请重新登录');
      }

      const url = `${BASE_URL}/ppt-templates/${templateId}/slides?token=${encodeURIComponent(token)}`;
      console.log('[PPTSlidePreview] 请求 URL:', url);
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      console.log('[PPTSlidePreview] 响应状态:', response.status);
      
      if (!response.ok) {
        let errorMsg = `加载失败 (${response.status})`;
        try {
          const data = await response.json();
          errorMsg = data.detail || errorMsg;
        } catch {
          errorMsg = response.statusText || errorMsg;
        }
        throw new Error(errorMsg);
      }
      
      const data = await response.json();
      console.log('[PPTSlidePreview] 返回数据:', data);
      
      if (data.slides && data.slides.length > 0 && data.preview_type === 'rendered') {
        setSlides(data.slides);
        setPreviewType('rendered');
        setPreviewMessage(data.message || '');
        setCurrentIndex(0);
        console.log('[PPTSlidePreview] 渲染预览加载成功，共', data.slides.length, '页');
        return;
      }
      
      if (templateData?.slidesStructure && templateData.slidesStructure.length > 0) {
        console.log('[PPTSlidePreview] 使用结构数据预览');
        const structureSlides = generateStructureSlides(templateData.slidesStructure, templateData.themeColors, templateData.fonts);
        setSlides(structureSlides);
        setPreviewType('structure');
        setPreviewMessage('基于模板结构生成预览');
        setCurrentIndex(0);
        return;
      }
      
      if (data.slides && data.slides.length > 0) {
        setSlides(data.slides);
        setPreviewType(data.preview_type || 'placeholder');
        setPreviewMessage(data.message || '');
        setCurrentIndex(0);
        return;
      }
      
      throw new Error('该模板暂无幻灯片数据');
      
    } catch (err) {
      console.error('[PPTSlidePreview] 加载失败:', err);
      
      if (templateData?.slidesStructure && templateData.slidesStructure.length > 0) {
        console.log('[PPTSlidePreview] 渲染失败，使用结构数据预览');
        const structureSlides = generateStructureSlides(templateData.slidesStructure, templateData.themeColors, templateData.fonts);
        setSlides(structureSlides);
        setPreviewType('structure');
        setPreviewMessage('基于模板结构生成预览');
        setCurrentIndex(0);
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : '加载幻灯片失败');
        setPreviewType('error');
      }
    } finally {
      setLoading(false);
    }
  }, [templateId, token, templateData]);

  useEffect(() => {
    loadSlides();
  }, [loadSlides]);

  const handlePrev = () => {
    setCurrentIndex(prev => Math.max(0, prev - 1));
  };

  const handleNext = () => {
    setCurrentIndex(prev => Math.min(slides.length - 1, prev + 1));
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'ArrowLeft') handlePrev();
    if (e.key === 'ArrowRight') handleNext();
    if (e.key === 'Escape') onClose();
    if (e.key === 't' || e.key === 'T') setShowThumbnails(prev => !prev);
  }, [onClose]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleDownload = async () => {
    const url = `${BASE_URL}/ppt-templates/${templateId}/download?token=${encodeURIComponent(token)}`;
    try {
      const response = await fetch(url);
      if (response.ok) {
        const blob = await response.blob();
        saveAs(blob, `模板_${templateId}.pptx`);
      } else {
        window.open(url, '_blank');
      }
    } catch {
      window.open(url, '_blank');
    }
  };

  const renderStructureSlide = (slideData: StructureSlide, themeColors?: Record<string, string>, fonts?: Record<string, any>) => {
    const shapes = slideData?.shapes || [];
    const primaryColor = themeColors?.primary || '#0d631b';
    const defaultFont = fonts?.default_font || 'SimHei';

    const canvasStyle: React.CSSProperties = {
      width: CANVAS_W,
      height: CANVAS_H,
      position: 'relative' as const,
      backgroundColor: slideData?.background_color || '#fff',
      border: '1px solid #ddd',
      borderRadius: 8,
      overflow: 'hidden',
      fontFamily: defaultFont,
      boxShadow: '0 12px 48px rgba(0,0,0,0.12)',
    };

    return (
      <div style={canvasStyle}>
        {!slideData?.background_color && (
          <>
            <div style={{
              position: 'absolute', inset: 0,
              background: 'linear-gradient(135deg, #ffffff 0%, #f9fdfa 100%)',
              pointerEvents: 'none'
            }} />
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 4,
              background: `linear-gradient(90deg, ${primaryColor}, ${primaryColor}88)`,
            }} />
          </>
        )}
        
        {shapes.length > 0 ? shapes.map((shape: any, idx: number) => {
          const left = shape.left ? (shape.left / SLIDE_W_EMU) * CANVAS_W : 20;
          const top = shape.top ? (shape.top / SLIDE_H_EMU) * CANVAS_H : 20 + idx * 60;
          const width = shape.width ? (shape.width / SLIDE_W_EMU) * CANVAS_W : CANVAS_W - 40;
          const height = shape.height ? (shape.height / SLIDE_H_EMU) * CANVAS_H : 40;
          const text = shape.text || shape.name || '';
          const isTitle = text.toLowerCase().includes('title') || shape.is_title;
          const hasFill = shape.fill_color;

          return (
            <div
              key={idx}
              style={{
                position: 'absolute',
                left: Math.max(0, left),
                top: Math.max(0, top),
                width: Math.min(width, CANVAS_W),
                height: Math.min(height, CANVAS_H),
                padding: '6px 10px',
                borderRadius: 4,
                backgroundColor: hasFill || (isTitle ? `${primaryColor}15` : '#f0f0f0'),
                border: hasFill ? 'none' : `1px dashed ${isTitle ? primaryColor : '#ccc'}`,
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                boxSizing: 'border-box',
                opacity: 0.95,
              }}
              title={shape.name}
            >
              <span style={{
                fontSize: isTitle ? 15 : 12,
                fontWeight: isTitle ? 700 : 400,
                color: hasFill ? '#fff' : (isTitle ? primaryColor : '#666'),
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: 1.3,
              }}>
                {text || `[${shape.name || '占位符'}]`}
              </span>
            </div>
          );
        }) : (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: '#ccc', fontSize: 16,
          }}>
            此页无可预览的布局元素
          </div>
        )}
      </div>
    );
  };

  const generateStructureSlides = (slidesStructure: StructureSlide[], themeColors?: Record<string, string>, fonts?: Record<string, any>): SlideData[] => {
    return slidesStructure.map((slide, index) => {
      const canvas = document.createElement('canvas');
      canvas.width = CANVAS_W;
      canvas.height = CANVAS_H;
      const ctx = canvas.getContext('2d');
      
      if (ctx) {
        const bgColor = slide.background_color || '#ffffff';
        ctx.fillStyle = bgColor;
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        
        if (!slide.background_color) {
          const gradient = ctx.createLinearGradient(0, 0, CANVAS_W, CANVAS_H);
          gradient.addColorStop(0, '#ffffff');
          gradient.addColorStop(1, '#f9fdfa');
          ctx.fillStyle = gradient;
          ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
          
          const primaryColor = themeColors?.primary || '#0d631b';
          ctx.fillStyle = primaryColor;
          ctx.fillRect(0, 0, CANVAS_W, 4);
        }
        
        const shapes = slide.shapes || [];
        shapes.forEach((shape: any) => {
          const left = shape.left ? (shape.left / SLIDE_W_EMU) * CANVAS_W : 20;
          const top = shape.top ? (shape.top / SLIDE_H_EMU) * CANVAS_H : 20;
          const width = shape.width ? (shape.width / SLIDE_W_EMU) * CANVAS_W : 100;
          const height = shape.height ? (shape.height / SLIDE_H_EMU) * CANVAS_H : 40;
          
          if (shape.fill_color) {
            ctx.fillStyle = shape.fill_color;
            ctx.fillRect(left, top, width, height);
          } else {
            ctx.fillStyle = '#f0f0f0';
            ctx.fillRect(left, top, width, height);
            ctx.strokeStyle = '#ccc';
            ctx.setLineDash([5, 5]);
            ctx.strokeRect(left, top, width, height);
            ctx.setLineDash([]);
          }
          
          if (shape.text) {
            ctx.fillStyle = shape.fill_color ? '#ffffff' : '#333333';
            ctx.font = '14px SimHei, Arial';
            ctx.fillText(shape.text.substring(0, 30), left + 8, top + 20);
          }
        });
        
        ctx.fillStyle = '#999999';
        ctx.font = 'bold 12px Arial';
        ctx.textAlign = 'right';
        ctx.fillText(`${index + 1} / ${slidesStructure.length}`, CANVAS_W - 20, CANVAS_H - 15);
      }
      
      return {
        slide_num: index + 1,
        title: `第 ${index + 1} 页`,
        content_preview: '',
        image: canvas.toDataURL('image/png')
      };
    });
  };

  return (
    <div className="ppt-preview-overlay" onClick={onClose}>
      <div className="ppt-preview-container" onClick={e => e.stopPropagation()}>
        <div className="ppt-preview-header">
          <div className="header-left">
            <h2>{title}</h2>
            {!loading && slides.length > 0 && (
              <span className="slide-counter">
                {currentIndex + 1} / {slides.length}
              </span>
            )}
            {previewType === 'structure' && (
              <span className="preview-type-badge structure">结构预览</span>
            )}
            {previewType === 'rendered' && (
              <span className="preview-type-badge rendered">渲染预览</span>
            )}
          </div>
          <div className="header-right">
            <button 
              className="toolbar-btn" 
              onClick={() => setShowThumbnails(!showThumbnails)}
              title="缩略图 (T)"
            >
              📑
            </button>
            <button 
              className="toolbar-btn" 
              onClick={handleDownload}
              title="下载"
            >
              ⬇️
            </button>
            <button className="toolbar-btn" onClick={loadSlides} title="刷新">
              🔄
            </button>
            <button className="close-btn" onClick={onClose}>✕</button>
          </div>
        </div>

        {previewType === 'placeholder' && previewMessage && (
          <div className="preview-notice">
            <span className="notice-icon">ℹ️</span>
            <span>{previewMessage}</span>
            <button className="notice-download" onClick={handleDownload}>
              下载原文件
            </button>
          </div>
        )}

        {previewType === 'structure' && (
          <div className="preview-notice structure-notice">
            <span className="notice-icon">📐</span>
            <span>基于模板结构生成预览，实际效果请下载查看</span>
            <button className="notice-download" onClick={handleDownload}>
              下载原文件
            </button>
          </div>
        )}

        <div className="ppt-preview-body">
          {loading ? (
            <div className="loading-container">
              <div className="spinner"></div>
              <p>正在加载幻灯片...</p>
              <p className="loading-hint">首次加载可能需要较长时间</p>
            </div>
          ) : error ? (
            <div className="error-container">
              <p>❌ {error}</p>
              <div className="error-actions">
                <button onClick={loadSlides}>重试</button>
                <button onClick={handleDownload} className="download-btn">下载文件</button>
              </div>
            </div>
          ) : slides.length === 0 ? (
            <div className="empty-container">
              <p>📭 暂无幻灯片</p>
              <button onClick={handleDownload}>下载文件查看</button>
            </div>
          ) : (
            <>
              {showThumbnails && (
                <div className="thumbnails-sidebar">
                  <div className="thumbnails-list">
                    {slides.map((slide, index) => (
                      <div
                        key={index}
                        className={`thumbnail-item ${index === currentIndex ? 'active' : ''}`}
                        onClick={() => setCurrentIndex(index)}
                      >
                        <img src={slide.image} alt={`幻灯片 ${index + 1}`} />
                        <span>{index + 1}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="slide-display">
                <div className="slide-image-container">
                  <img 
                    src={slides[currentIndex]?.image} 
                    alt={`幻灯片 ${currentIndex + 1}`}
                  />
                </div>
                
                <div className="slide-info">
                  <h3>{slides[currentIndex]?.title || `第 ${currentIndex + 1} 页`}</h3>
                  {slides[currentIndex]?.content_preview && (
                    <p className="content-preview">{slides[currentIndex].content_preview}</p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {!loading && slides.length > 0 && (
          <div className="ppt-preview-footer">
            <button 
              className="nav-btn prev"
              onClick={handlePrev}
              disabled={currentIndex === 0}
            >
              ◀ 上一页
            </button>
            
            <div className="progress-bar">
              <div 
                className="progress-fill"
                style={{ width: `${((currentIndex + 1) / slides.length) * 100}%` }}
              />
            </div>
            
            <button 
              className="nav-btn next"
              onClick={handleNext}
              disabled={currentIndex === slides.length - 1}
            >
              下一页 ▶
            </button>
          </div>
        )}

        <div className="keyboard-hints">
          <span>← → 翻页</span>
          <span>T 缩略图</span>
          <span>ESC 关闭</span>
        </div>
      </div>
    </div>
  );
};

export default PPTSlidePreview;
