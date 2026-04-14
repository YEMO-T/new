import PptxGenJS from "pptxgenjs";
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";
import { saveAs } from "file-saver";
import { Slide, LessonPlan } from "../types";
import { renderPptxFromServer, renderDocxFromServer, generateFinalPptV2 } from "./api";

function triggerDownload(url: string, fileName?: string) {
  const link = document.createElement('a');
  link.href = url;
  if (fileName) {
    link.download = fileName;
  }
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    document.body.removeChild(link);
  }, 100);
}

async function fetchAndDownload(url: string, fileName: string) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    saveAs(blob, fileName);
  } catch (err) {
    console.warn('[export] fetch下载失败，回退到window.open:', err);
    window.open(url, '_blank');
  }
}

export async function exportToPPTX(slides: Slide[], templateId?: string, title?: string) {
  const defaultTitle = title || slides[0]?.title || '新建课件';
  const safeFileName = defaultTitle.replace(/[\\/:*?"<>|]/g, '_').substring(0, 50);

  if (templateId) {
    try {
      console.log('[export] 使用 V2 终极渲染器生成PPT，templateId:', templateId);
      const result = await generateFinalPptV2(templateId, slides.map(s => ({
        title: s.title,
        content: s.content,
        page_type: s.type || 'content',
      })), { title: defaultTitle });

      if (result.download_url) {
        if (result.download_url.startsWith('http')) {
          await fetchAndDownload(result.download_url, `${safeFileName}.pptx`);
        } else {
          triggerDownload(result.download_url, `${safeFileName}.pptx`);
        }
        return;
      } else {
        console.warn('[export] V2渲染器未返回download_url，尝试回退');
      }
    } catch (v2Error) {
      console.warn('[export] V2 渲染失败，回退到 V1:', v2Error);
    }

    try {
      const res = await renderPptxFromServer(slides, defaultTitle, templateId);
      if (res.file_url) {
        if (res.file_url.startsWith('http')) {
          await fetchAndDownload(res.file_url, `${safeFileName}.pptx`);
        } else {
          triggerDownload(res.file_url, `${safeFileName}.pptx`);
        }
        return;
      }
    } catch (error) {
      console.error('Backend PPTX export failed:', error);
    }

    console.warn('[export] 所有后端下载方式失败，使用前端客户端回退生成PPT');
    const pptx = new PptxGenJS();
    slides.forEach(slide => {
      const pptSlide = pptx.addSlide();
      if (slide.type === 'cover') {
        pptSlide.addText(slide.title, { 
          x: 0.5, y: 1.5, w: 9, h: 1, 
          fontSize: 44, bold: true, color: '0d631b', align: 'center' 
        });
        pptSlide.addText(slide.content, { 
          x: 0.5, y: 2.5, w: 9, h: 1, 
          fontSize: 24, italic: true, color: '666666', align: 'center' 
        });
      } else {
        pptSlide.addText(slide.title, { 
          x: 0.5, y: 0.5, w: 9, h: 0.5, 
          fontSize: 28, bold: true, color: '0d631b' 
        });
        pptSlide.addText(slide.content, { 
          x: 0.5, y: 1.2, w: 9, h: 4, 
          fontSize: 18, color: '333333', bullet: true 
        });
      }
    });
    await pptx.writeFile({ fileName: `${safeFileName}.pptx` });
  }
}

export async function exportToDOCX(lessonPlan: LessonPlan) {
  try {
    const res = await renderDocxFromServer(lessonPlan.title, lessonPlan);
    if (res && res.file_url) {
      const safeName = lessonPlan.title.replace(/[\\/:*?"<>|]/g, '_').substring(0, 50);
      if (res.file_url.startsWith('http')) {
        await fetchAndDownload(res.file_url, `${safeName}.docx`);
      } else {
        triggerDownload(res.file_url, `${safeName}.docx`);
      }
      return;
    }
  } catch (error) {
    console.error('Backend DOCX export failed, falling back to client-side:', error);
  }

  const doc = Document({
    sections: [{
      properties: {},
      children: [
        Paragraph({
          text: lessonPlan.title,
          heading: HeadingLevel.HEADING_1,
        }),
        Paragraph({ text: "" }),
        Paragraph({
          text: "教学目标",
          heading: HeadingLevel.HEADING_2,
        }),
        ...lessonPlan.objectives.map(obj => Paragraph({ text: `• ${obj}` })),
        Paragraph({ text: "" }),
        Paragraph({
          text: "教学过程",
          heading: HeadingLevel.HEADING_2,
        }),
        ...lessonPlan.process.flatMap(p => [
          Paragraph({
            children: [TextRun({ text: `${p.stage} (${p.duration})`, bold: true })],
          }),
          Paragraph({ text: p.content }),
          Paragraph({ text: "" }),
        ]),
        Paragraph({
          text: "课后作业",
          heading: HeadingLevel.HEADING_2,
        }),
        Paragraph({ text: lessonPlan.homework }),
      ],
    }],
  });
  const blob = await Packer.toBlob(doc);
  saveAs(blob, `${lessonPlan.title.replace(/[\\/:*?"<>|]/g, '_')}.docx`);
}
