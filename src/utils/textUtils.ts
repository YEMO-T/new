export const normalizeContent = (content: any): string => {
  if (typeof content === 'string') {
    return content.trim();
  }
  
  if (Array.isArray(content)) {
    return content
      .filter(item => item != null && item !== '')
      .map(item => {
        if (typeof item === 'string') {
          return item.trim();
        }
        if (typeof item === 'object') {
          return JSON.stringify(item, null, 2);
        }
        return String(item);
      })
      .filter(text => text.length > 0)
      .join('\n\n');
  }
  
  if (typeof content === 'object' && content !== null) {
    return JSON.stringify(content, null, 2);
  }
  
  if (content == null) {
    return '';
  }
  
  return String(content);
};

export const sanitizeMarkdownText = (text: string): string => {
  if (!text || typeof text !== 'string') {
    return '';
  }
  
  let sanitized = text
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  
  return sanitized;
};

export const preprocessSlideContent = (slide: any): string => {
  if (!slide) {
    return '内容加载中...';
  }
  
  if (slide.content) {
    const normalized = normalizeContent(slide.content);
    return sanitizeMarkdownText(normalized);
  }
  
  if (slide.description) {
    return sanitizeMarkdownText(normalizeContent(slide.description));
  }
  
  if (slide.title) {
    return `## ${slide.title}`;
  }
  
  return '暂无内容';
};

export const safeMarkdownChildren = (content: any): string => {
  try {
    const normalized = normalizeContent(content);
    return sanitizeMarkdownText(normalized);
  } catch (error) {
    console.error('[safeMarkdownChildren] 处理失败:', error);
    return '内容解析失败';
  }
};

export const processAIText = (text: any): string => {
  if (!text) {
    return '';
  }

  let processed = safeMarkdownChildren(text);

  processed = processed
    .replace(/【/g, '\u300C')
    .replace(/】/g, '\u300D')
    .replace(/\u201C/g, '"')
    .replace(/\u201D/g, '"')
    .replace(/\u2018/g, "'")
    .replace(/\u2019/g, "'");

  return processed;
};

export const formatLongText = (text: string, maxLength: number = 500): string => {
  if (!text || text.length <= maxLength) {
    return text;
  }

  const paragraphs = text.split('\n\n');
  let result = '';
  let currentLength = 0;

  for (const paragraph of paragraphs) {
    if (currentLength + paragraph.length > maxLength) {
      break;
    }
    result += paragraph + '\n\n';
    currentLength += paragraph.length + 2;
  }

  return result.trim() + '...';
};

export const extractKeyPoints = (text: string): string[] => {
  if (!text) {
    return [];
  }

  const lines = text.split('\n');
  const points: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.match(/^[-•*]\s+/) || trimmed.match(/^\d+[.、]\s+/)) {
      const point = trimmed.replace(/^[-•*\d.、]+\s+/, '').trim();
      if (point) {
        points.push(point);
      }
    }
  }

  return points;
};
