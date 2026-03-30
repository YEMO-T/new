import React, { useState } from 'react';
import { PPTTemplate } from '../types';

interface TemplatePreviewModalProps {
  template: PPTTemplate;
  onClose: () => void;
}

/**
 * 模板预览弹框 —— 利用 template_data 中的幻灯片结构信息，
 * 以线框骨架的方式在浏览器中可视化展示每一页的布局和主题色。
 */
const TemplatePreviewModal: React.FC<TemplatePreviewModalProps> = ({ template, onClose }) => {
  const [currentSlide, setCurrentSlide] = useState(0);

  const slides = template.templateData?.slidesStructure || [];
  const themeColors = template.templateData?.themeColors || {};
  const fonts = template.templateData?.fonts || {};

  // NOTE: 幻灯片画布虚拟尺寸（EMU → 像素的等比缩放基准）
  const CANVAS_W = 720;
  const CANVAS_H = 540;
  // 标准 PPT 尺寸（EMU），用于坐标归一化
  const SLIDE_W_EMU = 12192000;
  const SLIDE_H_EMU = 6858000;

  const primaryColor = themeColors.primary || '#0d631b';
  const defaultFont = fonts.default_font || 'SimHei';

  const renderSlide = (slideData: any) => {
    const shapes = slideData?.shapes || [];

    return (
      <div
        className="preview-canvas"
        style={{
          width: CANVAS_W,
          height: CANVAS_H,
          position: 'relative',
          backgroundColor: slideData?.background_color || '#fff',
          border: `1px solid #ddd`,
          borderRadius: 8,
          overflow: 'hidden',
          fontFamily: defaultFont,
          boxShadow: '0 12px 48px rgba(0,0,0,0.12)',
        }}
      >
        {/* 背景渐变蒙层 (可选) */}
        {!slideData?.background_color && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(135deg, #ffffff 0%, #f9fdfa 100%)',
            pointerEvents: 'none'
          }} />
        )}

        {/* 顶部主题色装饰条 (仅在无背景色时保留) */}
        {!slideData?.background_color && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, height: 4,
            background: `linear-gradient(90deg, ${primaryColor}, ${primaryColor}88)`,
          }} />
        )}

        {shapes.length > 0 ? shapes.map((shape: any, idx: number) => {
          const left = shape.left ? (shape.left / SLIDE_W_EMU) * CANVAS_W : 20;
          const top = shape.top ? (shape.top / SLIDE_H_EMU) * CANVAS_H : 20 + idx * 60;
          const width = shape.width ? (shape.width / SLIDE_W_EMU) * CANVAS_W : CANVAS_W - 40;
          const height = shape.height ? (shape.height / SLIDE_H_EMU) * CANVAS_H : 40;
          const text = shape.text || shape.name || '';
          const isTitle = (shape.text || shape.name || '').toLowerCase().includes('title') || shape.is_title;
          const isPic = shape.image_data;
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
                  padding: isPic ? 0 : '6px 10px',
                  borderRadius: 4,
                  backgroundColor: isPic ? 'transparent' : (hasFill || (isTitle ? `${primaryColor}15` : '#f0f0f0')),
                  border: isPic ? 'none' : (hasFill ? 'none' : `1px dashed ${isTitle ? primaryColor : '#ccc'}`),
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: isPic ? 'stretch' : 'center',
                  boxSizing: 'border-box',
                  opacity: 0.95,
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                }}
                title={shape.name}
              >
                {isPic && (
                  <img 
                    src={shape.image_data} 
                    alt="" 
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
                  />
                )}
                {!isPic && (
                  <span style={{
                    fontSize: isTitle ? 15 : 12,
                    fontWeight: isTitle ? 700 : 400,
                    color: isTitle ? (hasFill ? '#fff' : primaryColor) : (hasFill ? '#fff' : '#666'),
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    lineHeight: 1.3,
                    textShadow: hasFill ? '0 1px 2px rgba(0,0,0,0.2)' : 'none',
                  }}>
                    {text || `[${shape.name || '占位符'}]`}
                  </span>
                )}
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

        {/* 页码 */}
        <div style={{
          position: 'absolute', bottom: 8, right: 14,
          fontSize: 10, color: '#bbb', fontWeight: 600,
        }}>
          {currentSlide + 1} / {slides.length}
        </div>
      </div>
    );
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      backgroundColor: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: '#fff', borderRadius: 20, padding: 32,
        maxWidth: 860, width: '95%', maxHeight: '92vh', overflow: 'auto',
        boxShadow: '0 25px 80px rgba(0,0,0,0.2)',
      }} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#161d19' }}>
              👁️ {template.title}
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#888' }}>
              {template.description || '暂无描述'} · {slides.length} 页
            </p>
          </div>
          <button onClick={onClose} style={{
            background: '#f4f4f4', border: 'none', borderRadius: '50%',
            width: 36, height: 36, cursor: 'pointer', fontSize: 18, color: '#666',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>✕</button>
        </div>

        {/* 主题色预览 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#999', fontWeight: 600 }}>主题色：</span>
          {Object.entries(themeColors).map(([key, color]) => (
            <div key={key} style={{
              width: 24, height: 24, borderRadius: 6,
              backgroundColor: color as string, border: '2px solid #eee',
            }} title={`${key}: ${color}`} />
          ))}
          {fonts.default_font && (
            <span style={{ marginLeft: 16, fontSize: 12, color: '#999' }}>
              字体：<strong style={{ color: '#333' }}>{fonts.default_font}</strong>
            </span>
          )}
        </div>

        {/* 幻灯片画布 */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          {slides.length > 0 ? renderSlide(slides[currentSlide]) : (
            <div style={{
              width: CANVAS_W, height: CANVAS_H, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              background: '#fafafa', borderRadius: 12, color: '#ccc', fontSize: 18,
            }}>
              暂无幻灯片结构数据
            </div>
          )}
        </div>

        {/* 翻页控制 */}
        {slides.length > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, alignItems: 'center' }}>
            <button
              onClick={() => setCurrentSlide(p => Math.max(0, p - 1))}
              disabled={currentSlide === 0}
              style={{
                padding: '8px 20px', borderRadius: 20, border: '1px solid #ddd',
                background: currentSlide === 0 ? '#f5f5f5' : '#fff',
                cursor: currentSlide === 0 ? 'not-allowed' : 'pointer',
                fontWeight: 700, fontSize: 13, color: currentSlide === 0 ? '#ccc' : primaryColor,
              }}
            >
              ◀ 上一页
            </button>
            
            {/* 缩略图页码导航 */}
            <div style={{ display: 'flex', gap: 4 }}>
              {slides.map((_: any, idx: number) => (
                <button
                  key={idx}
                  onClick={() => setCurrentSlide(idx)}
                  style={{
                    width: 28, height: 28, borderRadius: 8,
                    border: idx === currentSlide ? `2px solid ${primaryColor}` : '1px solid #ddd',
                    background: idx === currentSlide ? `${primaryColor}15` : '#fff',
                    cursor: 'pointer', fontSize: 11, fontWeight: 700,
                    color: idx === currentSlide ? primaryColor : '#999',
                  }}
                >
                  {idx + 1}
                </button>
              ))}
            </div>

            <button
              onClick={() => setCurrentSlide(p => Math.min(slides.length - 1, p + 1))}
              disabled={currentSlide === slides.length - 1}
              style={{
                padding: '8px 20px', borderRadius: 20, border: '1px solid #ddd',
                background: currentSlide === slides.length - 1 ? '#f5f5f5' : '#fff',
                cursor: currentSlide === slides.length - 1 ? 'not-allowed' : 'pointer',
                fontWeight: 700, fontSize: 13, color: currentSlide === slides.length - 1 ? '#ccc' : primaryColor,
              }}
            >
              下一页 ▶
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default TemplatePreviewModal;
