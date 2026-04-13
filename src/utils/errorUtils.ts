export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string,
    public detail?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let detail: any = null;
    let message = `HTTP ${response.status}: ${response.statusText}`;

    try {
      const contentType = response.headers.get('content-type');
      if (contentType?.includes('application/json')) {
        const errorData = await response.json();
        detail = errorData;
        
        if (errorData.detail) {
          if (typeof errorData.detail === 'string') {
            message = errorData.detail;
          } else if (Array.isArray(errorData.detail)) {
            message = errorData.detail.map((err: any) => {
              const loc = err.loc?.join('.') || 'unknown';
              const msg = err.msg || '验证失败';
              return `${loc}: ${msg}`;
            }).join('; ');
          } else {
            message = JSON.stringify(errorData.detail);
          }
        }
      } else {
        const textData = await response.text();
        detail = textData;
        if (textData) {
          message = textData;
        }
      }
    } catch (parseError) {
      console.error('[ApiError] 解析错误响应失败:', parseError);
    }

    return new ApiError(message, response.status, response.statusText, detail);
  }

  toLogString(): string {
    const parts = [
      `[API错误] ${this.message}`,
      `状态码: ${this.status} ${this.statusText}`,
    ];
    
    if (this.detail) {
      parts.push(`详细信息: ${JSON.stringify(this.detail, null, 2)}`);
    }
    
    return parts.join('\n');
  }
}

export function logError(context: string, error: unknown): void {
  if (error instanceof ApiError) {
    console.error(`[${context}] ${error.toLogString()}`);
  } else if (error instanceof Error) {
    console.error(`[${context}] 错误:`, {
      name: error.name,
      message: error.message,
      stack: error.stack,
    });
  } else {
    console.error(`[${context}] 未知错误:`, JSON.stringify(error, null, 2));
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  if (typeof error === 'string') {
    return error;
  }
  
  return '发生未知错误，请稍后重试';
}

export function isNetworkError(error: unknown): boolean {
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return true;
  }
  
  if (error instanceof Error) {
    return (
      error.message.includes('网络') ||
      error.message.includes('network') ||
      error.message.includes('timeout') ||
      error.message.includes('超时')
    );
  }
  
  return false;
}

export function isAuthError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 401 || error.status === 403;
  }
  return false;
}

export function isValidationError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 422 || error.status === 400;
  }
  return false;
}
