export interface UserInfo {
  id: string;
  username: string;
  email: string;
  role: string;
}

export interface AuthResult {
  token: string;
  user: UserInfo;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: 'text' | 'file' | 'plan';
  fileInfo?: {
    name: string;
    size: string;
    status?: string;
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

// PPT模板库新类型
export interface PPTTemplate {
  id: string;
  userId: string;
  title: string;
  description: string;
  category: string;
  sourceType: 'upload' | 'saved_courseware';
  visibility: 'private' | 'public';
  thumbnail: string;
  usageCount: number;
  isFavorite: boolean;
  createdAt: string;
  updatedAt: string;
  templateData?: {
    slidesStructure: any[];
    themeColors: Record<string, string>;
    fonts: Record<string, any>;
    placeholders: Record<string, any>;
  };
}

export interface GenerateCoursewareRequest {
  topic: string;
  templateId?: string;
  knowledgeItems?: string[];
}

export interface KnowledgeItem {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt';
  size: string;
  date: string;
  tags: string[];
  status: 'completed' | 'syncing';
  content?: string;
}
