import React from 'react';
import SafeMarkdown from './common/SafeMarkdown';
import {
  normalizeContent,
  processAIText,
  formatLongText,
  extractKeyPoints
} from '../utils/textUtils';

const TestMarkdown: React.FC = () => {
  const testCases = [
    {
      title: '字符串类型',
      content: '《琵琶行》是唐代诗人白居易的代表作之一',
    },
    {
      title: '数组类型',
      content: ['段落1', '段落2', '段落3'],
    },
    {
      title: '对象类型',
      content: { text: '对象内容' },
    },
    {
      title: '多行文本',
      content: `第一段内容

第二段内容

第三段内容`,
    },
    {
      title: 'Markdown格式',
      content: `# 标题

**粗体文本**

- 列表项1
- 列表项2
- 列表项3

\`\`\`javascript
const code = "示例代码";
\`\`\`
`,
    },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Markdown组件测试</h1>

      <div className="space-y-8">
        {testCases.map((testCase, index) => (
          <div key={index} className="border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">{testCase.title}</h2>
            <div className="bg-gray-50 p-4 rounded mb-4">
              <p className="text-sm text-gray-600 mb-2">原始数据类型:</p>
              <code className="text-xs">
                {typeof testCase.content === 'object'
                  ? JSON.stringify(testCase.content)
                  : typeof testCase.content}
              </code>
            </div>
            <div className="prose max-w-none">
              <SafeMarkdown>{testCase.content}</SafeMarkdown>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">文本处理工具测试</h2>
        
        <div className="space-y-4">
          <div>
            <h3 className="font-medium mb-2">normalizeContent</h3>
            <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto">
              {normalizeContent(['段落1', '段落2', '段落3'])}
            </pre>
          </div>

          <div>
            <h3 className="font-medium mb-2">processAIText</h3>
            <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto">
              {processAIText('《琵琶行》是唐代诗人白居易的代表作之一')}
            </pre>
          </div>

          <div>
            <h3 className="font-medium mb-2">formatLongText</h3>
            <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto">
              {formatLongText('这是一段很长的文本内容，用于测试文本截断功能。'.repeat(10), 100)}
            </pre>
          </div>

          <div>
            <h3 className="font-medium mb-2">extractKeyPoints</h3>
            <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto">
              {JSON.stringify(extractKeyPoints('- 要点1\n- 要点2\n- 要点3'), null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestMarkdown;
