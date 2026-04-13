import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { safeMarkdownChildren } from '../../utils/textUtils';
import { MarkdownErrorBoundary } from './ErrorBoundary';

interface SafeMarkdownProps {
  children: any;
  className?: string;
  proseClass?: string;
}

export const SafeMarkdown: React.FC<SafeMarkdownProps> = ({
  children,
  className = '',
  proseClass = 'prose prose-sm max-w-none break-words'
}) => {
  const safeContent = safeMarkdownChildren(children);

  return (
    <MarkdownErrorBoundary>
      <div className={`${proseClass} ${className}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
        >
          {safeContent}
        </ReactMarkdown>
      </div>
    </MarkdownErrorBoundary>
  );
};

export default SafeMarkdown;
