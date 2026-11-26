import { RequestError, request, wechatCode } from './request';

type EmployeeSession = { access_token: string; selected_role: 'employee'; refresh_token?: string };
export type StaffProfile = { id: string; employee_no: string | null; display_name: string; status: string; role: string };
const restorePreference = 'sunshine-staff-restore';
let session: EmployeeSession | undefined;
let rotation: { from: EmployeeSession; promise: Promise<EmployeeSession> } | undefined;

export function shouldRestoreEmployee(): boolean {
  try {
    return wx.getStorageSync(restorePreference) === true;
  } catch {
    return false;
  }
}

function rememberEmployee(enabled: boolean) {
  try {
    if (enabled) wx.setStorageSync(restorePreference, true);
    else wx.removeStorageSync(restorePreference);
  } catch {
    // Storage is optional. Credentials stay in memory.
  }
}

export function setStaffCustomerSession(issued?: EmployeeSession) {
  rotation = undefined;
  session = issued?.selected_role === 'employee' ? issued : undefined;
  if (!session) rememberEmployee(false);
}

export function employeeSignedIn(): boolean {
  return !!session;
}

function checkedSession(issued: EmployeeSession): EmployeeSession {
  if (issued.selected_role !== 'employee' || !issued.access_token || !issued.refresh_token) {
    throw new RequestError(401, 'INVALID_SESSION', '员工会话无效，请重新登录。');
  }
  return issued;
}

export async function loginEmployee(): Promise<void> {
  const code = await wechatCode();
  setStaffCustomerSession(checkedSession(await request<EmployeeSession>('/auth/wechat/login', 'POST', { code, role: 'employee' })));
  rememberEmployee(true);
}

export function scanStaffInvitation(): Promise<string | undefined> {
  return new Promise((resolve, reject) => wx.scanCode({
    onlyFromCamera: true,
    scanType: ['qrCode'],
    success: ({ result }) => {
      if (/^sunshine-staff-bind:v1:[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/.test(result)) resolve(result);
      else reject(new Error('请扫描管理员现场出示的员工绑定二维码。'));
    },
    fail: ({ errMsg }) => {
      if (errMsg.includes('cancel')) resolve(undefined);
      else reject(new Error('无法扫描二维码，请检查相机权限后重试。'));
    },
  }));
}

export async function bindEmployee(invitation: string): Promise<void> {
  const code = await wechatCode();
  await request('/auth/wechat/staff-bind', 'POST', { code, invitation });
}

function expired(error: unknown) {
  return error instanceof RequestError && error.status === 401;
}

function invalidSession() {
  return new RequestError(401, 'INVALID_SESSION', '员工会话已失效，请重新登录。');
}

async function staffRequest<T>(path: string, method: 'GET' | 'POST', data?: Record<string, string | number>): Promise<T> {
  const active = session;
  if (!active) throw invalidSession();
  try {
    const result = await request<T>(path, method, data, active.access_token);
    if (session !== active && rotation?.from !== active) throw invalidSession();
    return result;
  } catch (error) {
    if (!expired(error) || !active.refresh_token || (session !== active && rotation?.from !== active)) {
      if (expired(error) && session === active) setStaffCustomerSession();
      throw error;
    }
    let refreshed: EmployeeSession | undefined;
    try {
      if (rotation?.from !== active) {
        rotation = {
          from: active,
          promise: request<EmployeeSession>('/auth/refresh', 'POST', { refresh_token: active.refresh_token })
            .then(checkedSession)
            .then((updated) => {
              if (session === active) session = updated;
              return updated;
            }),
        };
      }
      const attempt = rotation;
      try {
        refreshed = await attempt.promise;
      } catch (cause) {
        if (rotation === attempt) rotation = undefined;
        throw cause;
      }
      if (session !== refreshed) throw invalidSession();
      const result = await request<T>(path, method, data, refreshed.access_token);
      if (session !== refreshed) throw invalidSession();
      return result;
    } catch (cause) {
      if (expired(cause) && (session === active || session === refreshed)) setStaffCustomerSession();
      throw cause;
    }
  }
}

export function readEmployee<T>(path: string, data?: Record<string, string | number>): Promise<T> {
  return staffRequest(path, 'GET', data);
}

export function loadStaffProfile(): Promise<StaffProfile> {
  return readEmployee('/staff/me');
}

export async function logoutEmployee() {
  try {
    await staffRequest('/auth/logout', 'POST');
  } catch (error) {
    if (!expired(error)) throw error;
  }
  setStaffCustomerSession();
}
