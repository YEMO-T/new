import { ApiError } from './errorUtils';

interface RequestConfig {
  timeout?: number;
  enableCache?: boolean;
  cacheKey?: string;
}

class RequestManager {
  private pendingRequests = new Map<string, Promise<any>>();
  private abortControllers = new Map<string, AbortController>();
  private cache = new Map<string, { data: any; timestamp: number }>();
  private readonly CACHE_TTL = 5 * 60 * 1000;

  createRequestKey(url: string, options?: RequestInit): string {
    const method = options?.method || 'GET';
    const body = options?.body;
    return `${method}:${url}:${body ? JSON.stringify(body) : ''}`;
  }

  async fetchWithTimeout(
    url: string,
    options: RequestInit,
    config: RequestConfig = {}
  ): Promise<Response> {
    const {
      timeout = 30000,
      enableCache = false,
      cacheKey
    } = config;

    const key = cacheKey || this.createRequestKey(url, options);

    if (enableCache) {
      const cached = this.cache.get(key);
      if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
        console.log(`[请求管理器] 使用缓存: ${key.substring(0, 50)}...`);
        return new Response(JSON.stringify(cached.data), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    }

    if (this.pendingRequests.has(key)) {
      console.log(`[请求管理器] 复用现有请求: ${key.substring(0, 50)}...`);
      const pendingPromise = this.pendingRequests.get(key)!;
      
      const response = await pendingPromise;
      return response.clone();
    }

    const controller = new AbortController();
    this.abortControllers.set(key, controller);

    const timeoutId = setTimeout(() => {
      controller.abort();
      console.error(`[请求管理器] 请求超时 (${timeout}ms): ${url}`);
    }, timeout);

    const requestPromise = (async () => {
      try {
        const response = await fetch(url, {
          ...options,
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw await ApiError.fromResponse(response);
        }

        if (enableCache) {
          const clonedResponse = response.clone();
          const data = await clonedResponse.json();
          this.cache.set(key, { data, timestamp: Date.now() });
        }

        return response;
      } catch (error: any) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
          throw new Error(`请求超时（${timeout / 1000}秒），请检查网络或稍后重试`);
        }
        
        throw error;
      } finally {
        this.pendingRequests.delete(key);
        this.abortControllers.delete(key);
      }
    })();

    this.pendingRequests.set(key, requestPromise);

    return requestPromise;
  }

  cancelRequest(key: string): boolean {
    const controller = this.abortControllers.get(key);
    if (controller) {
      controller.abort();
      this.abortControllers.delete(key);
      this.pendingRequests.delete(key);
      console.log(`[请求管理器] 已取消请求: ${key}`);
      return true;
    }
    return false;
  }

  cancelAllRequests(): void {
    console.log(`[请求管理器] 取消所有请求，共 ${this.abortControllers.size} 个`);
    this.abortControllers.forEach((controller, key) => {
      controller.abort();
    });
    this.abortControllers.clear();
    this.pendingRequests.clear();
  }

  clearCache(): void {
    this.cache.clear();
    console.log('[请求管理器] 缓存已清空');
  }

  getPendingCount(): number {
    return this.pendingRequests.size;
  }
}

export const requestManager = new RequestManager();

export function createAbortController(): AbortController {
  return new AbortController();
}
