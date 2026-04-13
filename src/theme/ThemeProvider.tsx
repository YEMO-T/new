import React from 'react';
import { ConfigProvider, theme as antdTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#0d631b',
          colorSuccess: '#52c41a',
          colorWarning: '#faad14',
          colorError: '#ff4d4f',
          colorInfo: '#1890ff',
          fontSize: 14,
          borderRadius: 8,
        },
        components: {
          Button: {
            primaryShadow: '0 2px 8px rgba(13, 99, 27, 0.2)',
          },
          Card: {
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          },
          Modal: {
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
};

export default ThemeProvider;
