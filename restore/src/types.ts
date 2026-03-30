export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: 'text' | 'file' | 'plan';
  fileInfo?: {
    name: string;
    size: string;
    status: string;
    mimeType?: string;
    data?: string; // base64
  };
}

export interface Slide {
  title: string;
  content: string;
  type: 'cover' | 'content' | 'summary';
  imagePrompt?: string;
}

export interface LessonPlan {
  title: string;
  objectives: string[];
  process: {
    stage: string;
    content: string;
    duration: string;
  }[];
  homework: string;
}

export interface Interaction {
  type: 'quiz' | 'game' | 'animation';
  title: string;
  description: string;
}

export interface Template {
  id: string;
  title: string;
  description: string;
  author: string;
  category: string;
  usageCount: string;
  image: string;
}

export interface KnowledgeItem {
  id: string;
  name: string;
  type: 'pdf' | 'docx';
  size: string;
  date: string;
  tags: string[];
  status: 'completed' | 'syncing';
}
