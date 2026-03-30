import PptxGenJS from "pptxgenjs";
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";
import { saveAs } from "file-saver";
import { Slide, LessonPlan } from "../types";

export async function exportToPPTX(slides: Slide[]) {
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

export async function exportToDOCX(lessonPlan: LessonPlan) {
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
