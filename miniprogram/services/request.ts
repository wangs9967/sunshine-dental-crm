import { apiOrigin } from '../config/environment';

type Result<T> = { success: true; data: T } | { success: false; error: { code: string; message: string } };

export class RequestError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

export function request<T>(path: string, method: 'GET' | 'POST', data?: WechatMiniprogram.IAnyObject,
  token?: string): Promise<T> {
  const origin = apiOrigin();
  if (!origin) return Promise.reject(new Error('尚未配置小程序服务地址，请联系门诊。'));
  return new Promise((resolve, reject) => {
    wx.request<Result<T>>({
      url: origin + '/api/v1' + path, method, data, timeout: 10000,
      header: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      success: ({ data: result, statusCode }) => {
        if (statusCode >= 200 && statusCode < 300 && result?.success === true) {
          resolve(result.data);
        } else {
          const issue = result?.success === false ? result.error : undefined;
          reject(new RequestError(statusCode, issue?.code ?? 'REQUEST_FAILED',
            issue?.message ?? '服务暂时不可用，请稍后重试。'));
        }
      },
      fail: () => reject(new Error('网络连接失败，请检查网络后重试。')),
    });
  });
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请重试。';
}
