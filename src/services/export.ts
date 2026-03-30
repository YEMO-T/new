import PptxGenJS from "pptxgenjs";
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";
import { saveAs } from "file-saver";
import { Slide, LessonPlan } from "../types";
import { renderPptxFromServer, renderDocxFromServer } from "./api";

/**
 * 导出 PPT (优先使用后端 Python 生成)
 */
export async function exportToPPTX(slides: Slide[], templateId?: string) {
  try {
    await renderPptxFromServer(slides, slides[0]?.title || "新建课件", templateId);
    return;
  } catch (error) {
    console.error('Backend PPTX export failed, falling back to client-side:', error);
    // 前端回退方案
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
    await pptx.writeFile({ fileName: "豆沙包课件.pptx" });
  }
}

/**
 * 导出教案 (优先使用后端 Python 生成)
 */
export async function exportToDOCX(lessonPlan: LessonPlan) {
  try {
    await renderDocxFromServer(lessonPlan.title, lessonPlan);
    return;
  } catch (error) {
    console.error('Backend DOCX export failed, falling back to client-side:', error);
    // 前端回退方案
    const doc = new Document({
      sections: [{
        properties: {},
        children: [
          new Paragraph({
            text: lessonPlan.title,
            heading: HeadingLevel.HEADING_1,
          }),
          new Paragraph({ text: "" }),
          new Paragraph({
            text: "教学目标",
            heading: HeadingLevel.HEADING_2,
          }),
          ...lessonPlan.objectives.map(obj => new Paragraph({ text: `• ${obj}` })),
          new Paragraph({ text: "" }),
          new Paragraph({
            text: "教学过程",
            heading: HeadingLevel.HEADING_2,
          }),
          ...lessonPlan.process.flatMap(p => [
            new Paragraph({
              children: [
                new TextRun({ text: `${p.stage} (${p.duration})`, bold: true }),
              ],
            }),
            new Paragraph({ text: p.content }),
            new Paragraph({ text: "" }),
          ]),
          new Paragraph({
            text: "课后作业",
            heading: HeadingLevel.HEADING_2,
          }),
          new Paragraph({ text: lessonPlan.homework }),
        ],
      }],
    });
    const blob = await Packer.toBlob(doc);
    saveAs(blob, "豆沙包教案.docx");
  }
}
