import React, { useState, useEffect, useRef, useCallback } from 'react';

interface SupabaseImageProps {
  src?: string | null;
  alt: string;
  templateId?: string;
  className?: string;
  style?: React.CSSProperties;
  fallback?: React.ReactNode;
  onLoaded?: () => void;
  onError?: (error: Error) => void;
}

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

export const SupabaseImage: React.FC<SupabaseImageProps> = ({
  src,
  alt,
  templateId,
  className = '',
  style,
  fallback,
  onLoaded,
  onError
}) => {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<boolean>(false);
  const [retryCount, setRetryCount] = useState(0);
  const maxRetries = 2;
  const retryDelay = 500;
  const hasTriedSignedUrl = useRef(false);

  const getSignedUrl = useCallback(async () => {
    if (!templateId) return null;
    
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return null;
      
      const response = await fetch(
        `${BASE_URL}/ppt-templates/${templateId}/thumbnail-url?expires_in=3600`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      if (!response.ok) return null;
      
      const data = await response.json();
      return data.signed_url || null;
    } catch (err) {
      console.error('[SupabaseImage] 获取签名URL失败:', err);
      return null;
    }
  }, [templateId]);

  const tryLoadImage = useCallback(async (url: string): Promise<boolean> => {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = url;
    });
  }, []);

  useEffect(() => {
    let mounted = true;
    
    const loadImage = async () => {
      if (!src) {
        if (mounted) {
          setLoading(false);
          setError(true);
        }
        return;
      }

      setLoading(true);
      setError(false);
      hasTriedSignedUrl.current = false;

      const isValidUrl = src.startsWith('http://') || src.startsWith('https://') || src.startsWith('data:');
      
      if (!isValidUrl) {
        if (mounted) {
          setLoading(false);
          setError(true);
          onError?.(new Error('Invalid URL format'));
        }
        return;
      }

      const directLoadSuccess = await tryLoadImage(src);
      
      if (directLoadSuccess && mounted) {
        setImageUrl(src);
        setLoading(false);
        onLoaded?.();
        return;
      }

      if (templateId && !hasTriedSignedUrl.current && mounted) {
        hasTriedSignedUrl.current = true;
        
        const signedUrl = await getSignedUrl();
        
        if (signedUrl && mounted) {
          const signedLoadSuccess = await tryLoadImage(signedUrl);
          
          if (signedLoadSuccess) {
            setImageUrl(signedUrl);
            setLoading(false);
            onLoaded?.();
            return;
          }
        }
      }

      if (mounted) {
        setLoading(false);
        setError(true);
        onError?.(new Error('Failed to load image'));
      }
    };

    loadImage();

    return () => {
      mounted = false;
    };
  }, [src, templateId, tryLoadImage, getSignedUrl, onLoaded, onError]);

  const handleRetry = useCallback(() => {
    if (retryCount < maxRetries) {
      setRetryCount(prev => prev + 1);
      setError(false);
      setLoading(true);
      hasTriedSignedUrl.current = false;
    }
  }, [retryCount, maxRetries]);

  if (loading) {
    return (
      <div className={`supabase-image-loading ${className}`} style={style}>
        <div className="loading-spinner" />
      </div>
    );
  }

  if (error || !imageUrl) {
    if (fallback) {
      return <>{fallback}</>;
    }

    return (
      <div 
        className={`supabase-image-error ${className}`} 
        style={style}
        onClick={handleRetry}
        title={retryCount < maxRetries ? '点击重试' : '加载失败'}
      >
        <span className="error-icon">📄</span>
        <span className="error-text">
          {retryCount < maxRetries ? '点击重试' : '加载失败'}
        </span>
      </div>
    );
  }

  return (
    <img
      src={imageUrl}
      alt={alt}
      className={`supabase-image ${className}`}
      style={style}
      onError={() => {
        setError(true);
        setLoading(false);
        onError?.(new Error('Image load error'));
      }}
    />
  );
};

export const buildSupabaseImageUrl = (
  supabaseUrl: string,
  bucket: string,
  path: string,
  isPublic: boolean = false
): string => {
  const baseUrl = supabaseUrl.replace(/\/$/, '');
  
  if (isPublic) {
    return `${baseUrl}/storage/v1/object/public/${bucket}/${path}`;
  }
  
  return `${baseUrl}/storage/v1/object/sign/${bucket}/${path}`;
};

export const isSupabaseStorageUrl = (url: string): boolean => {
  return url.includes('.supabase.co/storage/');
};

export const extractPathFromUrl = (url: string): { bucket: string; path: string } | null => {
  try {
    const urlObj = new URL(url);
    const pathMatch = urlObj.pathname.match(/\/storage\/v1\/object\/(public|sign)\/([^\/]+)\/(.+)$/);
    
    if (pathMatch) {
      return {
        bucket: pathMatch[2],
        path: pathMatch[3]
      };
    }
    
    return null;
  } catch {
    return null;
  }
};

export default SupabaseImage;
