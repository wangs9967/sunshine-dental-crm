const sessionKey = 'sunshine-admin-demo-role';
export const roles = { manager: '店长', admin: '管理员' } as const;
export type AdminRole = keyof typeof roles;
export const demoEnabled = import.meta.env.DEV && import.meta.env.VITE_ADMIN_DEMO === 'true';

export function isAdminRole(value: unknown): value is AdminRole {
  return value === 'manager' || value === 'admin';
}

export function readDemoRole(): AdminRole | undefined {
  if (!demoEnabled || typeof window === 'undefined') return undefined;
  const stored = window.sessionStorage.getItem(sessionKey);
  return isAdminRole(stored) ? stored : undefined;
}

export function writeDemoRole(role?: AdminRole) {
  if (!demoEnabled) return;
  if (role) window.sessionStorage.setItem(sessionKey, role);
  else window.sessionStorage.removeItem(sessionKey);
}

type SessionData = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  selected_role: AdminRole;
};

class AuthError extends Error {
  constructor(readonly status: number) {
    super(status === 401 ? '用户名或密码错误。'
      : status === 429 ? '登录尝试过于频繁，请稍后再试。'
      : '认证服务暂时不可用，请重试。');
  }
}

async function authRequest(path: string, body?: object, accessToken?: string): Promise<unknown> {
  const response = await fetch(`/api/v1/auth/${path}`, {
    method: 'POST',
    cache: 'no-store',
    credentials: 'omit',
    redirect: 'error',
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new AuthError(response.status);
  const result = await response.json();
  if (result?.success !== true) throw new AuthError(503);
  return result.data;
}

function sessionData(data: unknown): SessionData {
  const value = data as Partial<SessionData> | undefined;
  if (!isAdminRole(value?.selected_role) || typeof value.access_token !== 'string' || !value.access_token
    || typeof value.refresh_token !== 'string' || !value.refresh_token
    || typeof value.expires_in !== 'number' || !Number.isFinite(value.expires_in) || value.expires_in <= 0) {
    throw new AuthError(503);
  }
  return value as SessionData;
}

export function loginErrorMessage(error: unknown): string {
  return error instanceof AuthError ? error.message : '认证服务暂时不可用，请重试。';
}

export class AdminReadError extends Error {
  constructor(readonly status: number) {
    super(status === 401 ? '当前会话已结束，请重新登录。'
      : status === 403 ? '当前身份没有查看权限。'
      : status === 404 ? '该资料不存在。'
      : status === 422 ? '查询条件无效。' : '读取失败，请重试。');
  }
}

export class AdminSession {
  #session: SessionData;
  #refreshAt: number;
  #refresh?: Promise<void>;
  #loggingOut = false;

  private constructor(data: SessionData) {
    this.#session = data;
    this.#refreshAt = this.refreshTime(data);
  }

  static async login(username: string, password: string): Promise<AdminSession> {
    return new AdminSession(sessionData(await authRequest('admin/login', { username, password })));
  }

  get role(): AdminRole {
    return this.#session.selected_role;
  }

  get refreshInMs(): number {
    return Math.max(250, this.#refreshAt - Date.now());
  }

  private refreshTime(data: SessionData): number {
    return Date.now() + data.expires_in * 1000 - Math.min(5000, data.expires_in * 100);
  }

  private rotate(): Promise<void> {
    this.#refresh ??= authRequest('refresh', { refresh_token: this.#session.refresh_token })
      .then((data) => {
        this.#session = sessionData(data);
        this.#refreshAt = this.refreshTime(this.#session);
      })
      .finally(() => { this.#refresh = undefined; });
    return this.#refresh;
  }

  async refresh(): Promise<void> {
    if (!this.#loggingOut) await this.rotate();
  }

  async read<T>(path: string, signal: AbortSignal): Promise<T> {
    const get = (token: string) => fetch('/api/v1/admin' + path, {
      cache: 'no-store', credentials: 'omit', redirect: 'error', signal,
      headers: { Authorization: `Bearer ${token}` },
    });
    const firstToken = this.#session.access_token;
    let response = await get(firstToken);
    if (response.status === 401 && !this.#loggingOut && !signal.aborted) {
      try {
        if (this.#session.access_token === firstToken) await this.rotate();
      } catch (error) {
        if (error instanceof AuthError) throw new AdminReadError(error.status);
        throw error;
      }
      response = await get(this.#session.access_token);
    }
    if (!response.ok) throw new AdminReadError(response.status);
    const result = await response.json();
    if (result?.success !== true) throw new AdminReadError(503);
    return result.data as T;
  }

  async logout(): Promise<void> {
    this.#loggingOut = true;
    try {
      try {
        await this.#refresh;
        await authRequest('logout', undefined, this.#session.access_token);
      } catch (error) {
        if (!(error instanceof AuthError && error.status === 401)) throw error;
        await this.rotate();
        await authRequest('logout', undefined, this.#session.access_token);
      }
    } catch (error) {
      if (!(error instanceof AuthError && error.status === 401)) throw error;
    } finally {
      this.#loggingOut = false;
    }
  }
}
