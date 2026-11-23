import { memberRegistrationRoute, workspacePath } from '../config/navigation';
import { RequestError, request } from './request';

export { errorMessage, RequestError } from './request';

type Session = {
  access_token: string;
  refresh_token: string;
  selected_role: 'member' | null;
  registration_required: boolean;
};

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
