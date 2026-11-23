import { apiOrigin } from '../config/environment';
import { memberRegistrationRoute, workspacePath } from '../config/navigation';

type Session = {
  access_token: string;
  refresh_token: string;
  selected_role: 'member' | null;
  registration_required: boolean;
};

type Result<T> = { success: true; data: T } | { success: false; error: { code: string; message: string } };
type Registration = { name: string; birthday: string; phone: string };
type RegistrationResult = { session: Session; source_status: 'none' | 'bound' | 'invalid' };
type Points = { balance: string };

export type MemberProfile = {
  id: string;
  member_no: string;
  name: string;
  birthday: string;
  phone_masked: string;
  status: string;
  registered_at: string;
};

export class RequestError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

let session: Session | undefined;
let sceneToken: string | undefined;
let refresh: Promise<Session> | undefined;
const restorePreference = 'sunshine-member-restore';

export function shouldRestoreMember(): boolean {
  try {
    return wx.getStorageSync(restorePreference) === true;
  } catch {
    return false;
  }
}

function rememberMemberLogin(enabled: boolean) {
  try {
    if (enabled) wx.setStorageSync(restorePreference, true);
    else wx.removeStorageSync(restorePreference);
  } catch {
    // Storage is optional. The current authenticated session remains in memory.
  }
}

function clearSession() {
  session = undefined;
  rememberMemberLogin(false);
}

export function rememberScene(value?: string) {
  if (!value || session?.selected_role === 'member') return;
  try {
    sceneToken = decodeURIComponent(value);
  } catch {
    sceneToken = value;
  }
  // Preserve the supplied-source indicator even if the input cannot be a valid source token.
  if (sceneToken.length > 256) sceneToken = '!';
}

export function memberState() {
  return session?.registration_required ? 'registration' : session?.selected_role;
}

function request<T>(path: string, method: 'GET' | 'POST', data?: WechatMiniprogram.IAnyObject,
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

async function authorized<T>(path: string, method: 'GET' | 'POST', data?: WechatMiniprogram.IAnyObject): Promise<T> {
  const active = session;
  if (!active) throw new RequestError(401, 'INVALID_SESSION', '请重新微信登录。');
  try {
    return await request<T>(path, method, data, active.access_token);
  } catch (error) {
    if (!(error instanceof RequestError) || error.status !== 401 || !session) throw error;
    if (session === active) {
      refresh ??= request<Session>('/auth/refresh', 'POST', { refresh_token: active.refresh_token })
        .then((updated) => {
          if (session === active) session = updated;
          return updated;
        })
        .finally(() => { refresh = undefined; });
      try {
        await refresh;
      } catch (cause) {
        if (cause instanceof RequestError && cause.status === 401 && session === active) clearSession();
        throw cause;
      }
    }
    const renewed = session;
    if (!renewed) throw new RequestError(401, 'INVALID_SESSION', '请重新微信登录。');
    try {
      return await request<T>(path, method, data, renewed.access_token);
    } catch (cause) {
      if (cause instanceof RequestError && cause.status === 401 && session === renewed) clearSession();
      throw cause;
    }
  }
}

export async function loginWithWechat(): Promise<string> {
  const code = await new Promise<string>((resolve, reject) => wx.login({
    success: (result) => result.code ? resolve(result.code) : reject(new Error('未取得微信登录凭据，请重试。')),
    fail: () => reject(new Error('微信登录失败，请重试。')),
  }));
  session = await request<Session>('/auth/wechat/login', 'POST', { code, scene_token: sceneToken });
  rememberMemberLogin(session.selected_role === 'member' && !session.registration_required);
  if (!session.registration_required) sceneToken = undefined;
  return session.registration_required ? memberRegistrationRoute : workspacePath('member');
}

export async function submitRegistration(form: Registration): Promise<RegistrationResult['source_status']> {
  const result = await authorized<RegistrationResult>('/members/register', 'POST', { ...form, scene_token: sceneToken });
  session = result.session;
  rememberMemberLogin(true);
  sceneToken = undefined;
  return result.source_status;
}

export async function loadPoints(): Promise<string> {
  return (await authorized<Points>('/members/me/points', 'GET')).balance;
}

export function loadMemberProfile(): Promise<MemberProfile> {
  return authorized<MemberProfile>('/members/me', 'GET');
}

export async function logoutMember(): Promise<void> {
  try {
    await authorized('/auth/logout', 'POST');
  } catch (error) {
    if (!(error instanceof RequestError) || error.status !== 401) throw error;
  }
  clearSession();
  sceneToken = undefined;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请重试。';
}
