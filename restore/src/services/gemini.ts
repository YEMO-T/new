import { GoogleGenAI, GenerateContentResponse } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

export interface MultimodalPart {
  inlineData?: {
    data: string;
    mimeType: string;
  };
  text?: string;
}

export async function chatWithGemini(prompt: string, history: any[] = [], files: MultimodalPart[] = []) {
  const contents = [
    ...history.map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content }],
    })),
    { 
      role: 'user', 
      parts: [
        ...files,
        { text: prompt }
      ] 
    }
  ];

  const response: GenerateContentResponse = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: contents,
    config: {
      systemInstruction: `你是一个名为'豆沙包'的高级AI教学智能体。你的目标是协助教师完成从意图理解到课件生成的全流程。

你的核心能力与行为准则：
1. **主动对话与意图澄清**：如果教师的需求模糊（如只说“帮我做个数学课件”），你必须主动询问：教学目标、学生学段、课程时长、核心知识点、以及期望的视觉风格。
2. **多模态融合**：分析用户上传的PDF、Word或图片，提取其中的逻辑结构、案例和风格，并将其融入后续生成。
3. **结构化输出**：
   - 当用户确认需求后，你需要生成一份详细的【教学大纲】。
   - 随后，根据大纲生成【PPT内容集】（包含封面、目录、多页内容、总结）和【配套Word教案】。
   - PPT内容应图文并茂，逻辑清晰。
4. **迭代优化**：理解用户的修改意见（如“第3页太复杂了”、“增加一个互动小游戏”），并精准调整对应内容。
5. **互动设计**：主动提议并设计至少一种互动环节（如知识点动画创意、H5小游戏、课堂讨论点）。

请始终保持专业、严谨且富有启发性的语气。在对话中，如果检测到用户准备好生成了，请以明确的结构展示大纲。`
    }
  });

  return response.text || "抱歉，我无法生成回复。";
}

export async function generateCourseware(prompt: string, history: any[] = []) {
  const response: GenerateContentResponse = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: [
      ...history.map(msg => ({
        role: msg.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: msg.content }],
      })),
      { role: 'user', parts: [{ text: `请根据以上对话内容，生成一份完整的课件（PPT）、教案和互动环节设计。
      如果对话中信息不足，请根据你的专业知识进行合理补充。
      
      必须严格按照以下 JSON 格式返回：
      {
        "slides": [
          { "title": "标题", "content": "正文内容", "type": "cover|content|summary", "imagePrompt": "配图描述" }
        ],
        "lessonPlan": {
          "title": "教案标题",
          "objectives": ["目标1", "目标2"],
          "process": [
            { "stage": "环节名称", "content": "详细教学过程", "duration": "时长" }
          ],
          "homework": "课后作业"
        },
        "interaction": {
          "type": "quiz|game|animation",
          "title": "互动环节标题",
          "description": "详细设计思路或代码逻辑"
        }
      }
      
      补充要求：${prompt}` }] }
    ],
    config: {
      responseMimeType: "application/json",
      systemInstruction: "你是一个专业的教学设计专家。你的任务是将教学意图转化为结构化的课件数据。请确保生成的 JSON 格式完全正确，内容专业且富有启发性。"
    }
  });

  try {
    return JSON.parse(response.text || "{}");
  } catch (e) {
    console.error("Failed to parse courseware generation:", e);
    return null;
  }
}

export async function analyzeSketch(base64Image: string, mimeType: string) {
  const imagePart: MultimodalPart = {
    inlineData: {
      data: base64Image,
      mimeType: mimeType,
    },
  };

  const response: GenerateContentResponse = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: {
      parts: [
        imagePart,
        { text: "请分析这张教学草图。识别出其中的几何图形、数学公式、逻辑流程或教学大纲。请以 JSON 格式返回结果，包含 'title' (标题), 'label' (类型), 'desc' (详细描述) 三个字段。返回一个数组。" }
      ]
    },
    config: {
      responseMimeType: "application/json",
    }
  });

  try {
    return JSON.parse(response.text || "[]");
  } catch (e) {
    console.error("Failed to parse sketch analysis:", e);
    return [];
  }
}
