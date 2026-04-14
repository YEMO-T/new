import React, { useState, useCallback } from 'react';
import { 
  Download, Sparkles, Loader2, CheckCircle2, AlertCircle,
  FileText, Palette, Clock
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { saveAs } from 'file-saver';
import {
  generatePptDirect,
  generatePptFromTopic,
  getTemplatesWithStyle,
} from '../services/api';

interface TemplateOption {
  id: string;
  title: string;
  usage_count: number;
  style_preview: {
    primary_color: string;
    title_font: string;
    body_font: string;
    layout_count: number;
    has_style: boolean;
  };
}

async function forceDownload(url: string, fileName: string) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    saveAs(blob, fileName);
  } catch (err) {
    console.warn('[DirectDownload] fetch下载失败，尝试<a>标签:', err);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

interface DirectGeneratePanelProps {
  slides?: Array<{
    title: string;
    content?: string | string[];
    page_type?: string;
    subtitle?: string;
  }>;
  topic?: string;
  onGenerated?: (result: any) => void;
  className?: string;
}

export const DirectGeneratePanel: React.FC<DirectGeneratePanelProps> = ({
  slides,
  topic,
  onGenerated,
  className = '',
}) => {
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [title, setTitle] = useState(topic || '');
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateOption[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [mode, setMode] = useState<'direct' | 'topic'>(
    slides && slides.length > 0 ? 'direct' : 'topic'
  );

  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const data = await getTemplatesWithStyle();
      setTemplates(data.templates || []);
      
      if (data.templates?.length > 0 && !selectedTemplateId) {
        setSelectedTemplateId(data.templates[0].id);
      }
    } catch (err) {
      console.error('加载模板失败:', err);
    } finally {
      setLoadingTemplates(false);
    }
  }, [selectedTemplateId]);

  React.useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleGenerateDirect = async () => {
    if (!selectedTemplateId) {
      setError('请先选择一个模板');
      return;
    }
    if (!slides || slides.length === 0) {
      setError('没有可生成的幻灯片内容');
      return;
    }

    setGenerating(true);
    setError(null);
    setResult(null);
    setProgress('正在准备生成...');

    try {
      setProgress('正在应用模板样式...');
      
      const result = await generatePptDirect(
        selectedTemplateId,
        title || '未命名演示',
        slides
      );

      setResult(result);
      setProgress('');

      if (result.download_url) {
        setProgress('正在下载文件...');
        
        setTimeout(() => {
          forceDownload(result.download_url, result.file_name || '新建课件.pptx');
          setProgress('');
        }, 500);
      } else {
        console.warn('[DirectGenerate] 无download_url，尝试blob下载回退');
        await tryBlobDownload(result.file_name || 'generated.pptx', selectedTemplateId, slides, title || '未命名演示');
        setProgress('');
      }

      onGenerated?.(result);
    } catch (err: any) {
      console.error('生成失败:', err);
      setError(err.message || 'PPT生成失败，请重试');
      setProgress('');
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateFromTopic = async () => {
    if (!selectedTemplateId) {
      setError('请先选择一个模板');
      return;
    }
    if (!topic && !title) {
      setError('请输入教学主题');
      return;
    }

    setGenerating(true);
    setError(null);
    setResult(null);
    setProgress('AI 正在分析主题...');

    try {
      setProgress('正在生成教学内容...');
      
      const result = await generatePptFromTopic(
        topic || title,
        selectedTemplateId,
        { title: title || topic }
      );

      setResult(result);
      setProgress('');

      if (result.download_url) {
        setProgress('正在下载文件...');
        
        setTimeout(() => {
          forceDownload(result.download_url, result.file_name || '新建课件.pptx');
          setProgress('');
        }, 500);
      } else {
        console.warn('[DirectGenerate] 无download_url，尝试blob下载回退');
        await tryBlobDownload(result.file_name || 'generated.pptx', selectedTemplateId, [], title || topic || '未命名演示');
        setProgress('');
      }

      onGenerated?.(result);
    } catch (err: any) {
      console.error('生成失败:', err);
      setError(err.message || 'PPT生成失败，请重试');
      setProgress('');
    } finally {
      setGenerating(false);
    }
  };

  const selectedTemplate = templates.find(t => t.id === selectedTemplateId);

  return (
    <div className={`direct-generate-panel ${className}`}>
      <div className="bg-white rounded-2xl shadow-lg border border-black/5 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#0d631b] to-[#16a34a] px-6 py-4">
          <div className="flex items-center gap-3">
            <Sparkles className="w-6 h-6 text-white" />
            <h2 className="text-xl font-bold text-white">一键生成 PPT</h2>
          </div>
          <p className="text-sm text-white/80 mt-1">
            选择模板 → 直接输出渲染好的 PPT 文件
          </p>
        </div>

        <div className="p-6 space-y-5">
          {/* Mode Toggle */}
          {slides && slides.length > 0 && (
            <div className="flex gap-2 bg-[#f0f4f0] p-1 rounded-lg">
              <button
                onClick={() => setMode('direct')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-semibold transition-all ${
                  mode === 'direct'
                    ? 'bg-white text-[#0d631b] shadow-sm'
                    : 'text-[#161d19]/60 hover:text-[#161d19]'
                }`}
              >
                <FileText className="w-4 h-4 inline mr-1" />
                使用当前内容 ({slides.length}页)
              </button>
              <button
                onClick={() => setMode('topic')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-semibold transition-all ${
                  mode === 'topic'
                    ? 'bg-white text-[#0d631b] shadow-sm'
                    : 'text-[#161d19]/60 hover:text-[#161d19]'
                }`}
              >
                <Sparkles className="w-4 h-4 inline mr-1" />
                从主题自动生成
              </button>
            </div>
          )}

          {/* Title Input */}
          {(mode === 'topic' || !slides || slides.length === 0) && (
            <div>
              <label className="block text-sm font-bold text-[#161d19]/70 mb-2">
                教学主题 / 标题
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例如：小学三年级数学 - 分数的初步认识"
                className="w-full px-4 py-3 border border-black/10 rounded-xl focus:border-[#0d631b] focus:ring-2 focus:ring-[#0d631b]/20 outline-none transition-all"
                disabled={generating}
              />
            </div>
          )}

          {/* Template Selector */}
          <div>
            <label className="block text-sm font-bold text-[#161d19]/70 mb-2">
              <Palette className="w-4 h-4 inline mr-1" />
              选择模板（样式将完整应用）
            </label>
            
            {loadingTemplates ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-[#0d631b]" />
                <span className="ml-2 text-sm text-[#161d19]/60">加载模板...</span>
              </div>
            ) : templates.length === 0 ? (
              <div className="text-center py-8 text-[#161d19]/40">
                <p>暂无可用模板</p>
                <p className="text-xs mt-1">请先到模板库上传模板</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-48 overflow-y-auto pr-1">
                {templates.map((tpl) => (
                  <button
                    key={tpl.id}
                    onClick={() => setSelectedTemplateId(tpl.id)}
                    disabled={generating}
                    className={`p-3 rounded-xl border-2 text-left transition-all ${
                      selectedTemplateId === tpl.id
                        ? 'border-[#0d631b] bg-[#eef5ee]'
                        : 'border-black/5 hover:border-[#0d631b]/30 bg-white'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {tpl.style_preview.has_style && tpl.style_preview.primary_color && (
                        <span
                          className="w-4 h-4 rounded mt-0.5 shrink-0"
                          style={{ backgroundColor: tpl.style_preview.primary_color }}
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold truncate">{tpl.title}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-[#161d19]/50">
                          {tpl.style_preview.layout_count > 0 && (
                            <span>{tpl.style_preview.layout_count} 版式</span>
                          )}
                          {tpl.style_preview.title_font && (
                            <span>{tpl.style_preview.title_font}</span>
                          )}
                          {tpl.usage_count > 0 && (
                            <span>{tpl.usage_count}次使用</span>
                          )}
                        </div>
                      </div>
                      
                      {selectedTemplateId === tpl.id && (
                        <CheckCircle2 className="w-5 h-5 text-[#0d631b] shrink-0" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Selected Template Info */}
          {selectedTemplate && (
            <div className="bg-[#f0f4f0] rounded-xl p-4">
              <p className="text-xs font-bold text-[#161d19]/50 mb-2">已选模板样式</p>
              <div className="flex flex-wrap gap-3 text-xs">
                {selectedTemplate.style_preview.primary_color && (
                  <span className="flex items-center gap-1">
                    <span
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: selectedTemplate.style_preview.primary_color }}
                    />
                    主色调
                  </span>
                )}
                {selectedTemplate.style_preview.title_font && (
                  <span>标题: {selectedTemplate.style_preview.title_font}</span>
                )}
                {selectedTemplate.style_preview.body_font && (
                  <span>正文: {selectedTemplate.style_preview.body_font}</span>
                )}
              </div>
            </div>
          )}

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl"
              >
                <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Progress */}
          <AnimatePresence>
            {progress && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-3 p-4 bg-[#eef5ee] rounded-xl"
              >
                <Loader2 className="w-5 h-5 text-[#0d631b] animate-spin shrink-0" />
                <p className="text-sm font-medium text-[#0d631b]">{progress}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Result */}
          <AnimatePresence>
            {result && !progress && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-green-50 border border-green-200 rounded-xl p-4"
              >
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="w-6 h-6 text-green-600 shrink-0" />
                  <div className="flex-1">
                    <p className="font-bold text-green-800">{result.message}</p>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-green-700">
                      <span>📄 {result.slide_count} 页</span>
                      <span>💾 {(result.file_size / 1024).toFixed(1)} KB</span>
                      <span>⚙️ 引擎: {result.engine_used}</span>
                      <span>
                        🎨 样式: {result.style_applied ? '已应用' : '默认'}
                      </span>
                      <span className="col-span-2">
                        <Clock className="w-3 h-3 inline" />{' '}
                        耗时: {result.generation_time.toFixed(1)}s
                      </span>
                    </div>
                    
                    {!result.download_url && (
                      <p className="mt-2 text-xs text-yellow-600">
                        文件已保存，请在导出记录中查看
                      </p>
                    )}
                    
                    {result.download_url && (
                      <button
                        onClick={() => forceDownload(result.download_url, result.file_name || '新建课件.pptx')}
                        className="mt-3 px-4 py-2 bg-green-600 text-white rounded-lg text-xs font-semibold hover:bg-green-700 transition-colors flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" />
                        重新下载 PPT
                      </button>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Generate Button */}
          <button
            onClick={mode === 'direct' ? handleGenerateDirect : handleGenerateFromTopic}
            disabled={generating || !selectedTemplateId || (mode === 'direct' && (!slides || slides.length === 0)) || (mode === 'topic' && !title)}
            className={`w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2 ${
              generating || !selectedTemplateId
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-[#0d631b] to-[#16a34a] text-white hover:opacity-90 shadow-lg hover:shadow-xl'
            }`}
          >
            {generating ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                正在生成...
              </>
            ) : (
              <>
                <Download className="w-5 h-5" />
                {mode === 'direct' ? '一键生成并下载 PPT' : '一键生成（AI自动填充内容）'}
              </>
            )}
          </button>

          <p className="text-xs text-center text-[#161d19]/40">
            点击后系统将自动完成：内容渲染 → 样式匹配 → 文件输出
          </p>
        </div>
      </div>
    </div>
  );
};

async function tryBlobDownload(
  fileName: string,
  templateId: string,
  slides: any[],
  title: string
) {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token') || '';
  
  try {
    const response = await fetch(`/api/ppt-direct/generate-from-topic`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        topic: title,
        template_id: templateId,
        title: title,
        auto_download: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`Blob回退请求失败: ${response.status}`);
    }

    const data = await response.json();
    
    if (data.download_url) {
      forceDownload(data.download_url, fileName);
      return;
    }

    console.warn('[BlobDownload] 仍然无download_url，尝试直接生成下载');

    const genResponse = await fetch('/api/ppt-templates/v2/' + templateId + '/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: title,
        slides: (slides.length > 0 ? slides : [{ title: title, content: ['内容生成中'], page_type: 'content' }]).map((s: any) => ({
          title: s.title || title,
          content: s.content || [''],
          page_type: s.page_type || 'content',
        })),
        auto_export: true,
      }),
    });

    if (!genResponse.ok) {
      throw new Error('V2渲染器也失败了');
    }

    const v2Data = await genResponse.json();
    
    if (v2Data.download_url) {
      forceDownload(v2Data.download_url, fileName);
    } else {
      alert('PPT已生成成功，但自动下载失败。请刷新页面后手动下载。');
    }

  } catch (err: any) {
    console.error('[BlobDownload] 回退下载也失败:', err);
    alert(`PPT已生成，但下载遇到问题：${err.message}\n请稍后重试或联系管理员。`);
  }
}

export default DirectGeneratePanel;
