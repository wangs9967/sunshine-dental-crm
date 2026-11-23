import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';
import { loginReturnPath, menu, relatedRoutes, resolveRoute } from './routes';
import { AdminSession, isAdminRole } from './session';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

test('renders the real login by default without a session', () => {
  const html = renderToStaticMarkup(<App />);
  expect(html).toContain('登录管理后台');
  expect(html).toMatch(/autocomplete="current-password"/i);
  expect(html).not.toContain('演示身份');
  expect(html).not.toContain('后台导航');
});

test('maps reviewed menu and detail routes to the active menu entry', () => {
  expect(menu).toHaveLength(12);
  for (const entry of menu) expect(resolveRoute(entry.path)?.entry).toBe(entry);
  expect(resolveRoute('/tasks')?.entry.path).toBe('/followups');
  expect(resolveRoute('/mall/products/new')?.title).toBe('新增商品');
  expect(resolveRoute('/mall/products/example/stock')?.entry.path).toBe('/mall/products');
  expect(resolveRoute('/mall/verify')?.entry.path).toBe('/mall/verifications');
  expect(resolveRoute('/unknown')).toBeUndefined();
});

test('only manager and admin identities can enter the admin workspace', () => {
  expect(isAdminRole('manager')).toBe(true);
  expect(isAdminRole('admin')).toBe(true);
  expect(isAdminRole('employee')).toBe(false);
  expect(isAdminRole(null)).toBe(false);
});

test('each linked secondary page resolves to its owning menu', () => {
  for (const [parent, links] of Object.entries(relatedRoutes)) {
    for (const link of links) expect(resolveRoute(link.path)?.entry.path).toBe(parent);
  }
});

test('returns to a known local deep link with its query and hash after sign-in', () => {
  expect(loginReturnPath('/members/demo-member/?tab=summary#notes')).toBe('/members/demo-member/?tab=summary#notes');
  expect(resolveRoute('/members/demo-member/?tab=summary#notes')?.title).toBe('会员详情');
  for (const path of ['//example.org/members', '/\\example.org/members', 'https://example.org', '/login', '/missing', null]) {
    expect(loginReturnPath(path)).toBe('/dashboard');
  }
});

test('production mode ignores a forged demo role and a demo flag', async () => {
  vi.stubEnv('DEV', false);
  vi.stubEnv('VITE_ADMIN_DEMO', 'true');
  const getItem = vi.fn().mockReturnValue('admin');
  vi.stubGlobal('window', {
    sessionStorage: { getItem },
    location: { pathname: '/members/test', search: '', hash: '' },
  });
  vi.resetModules();
  const { demoEnabled, readDemoRole } = await import('./session');
  expect(demoEnabled).toBe(false);
  expect(readDemoRole()).toBeUndefined();
  expect(getItem).not.toHaveBeenCalled();
});

test('rotates once for concurrent refreshes and calls logout with the latest access token', async () => {
  const session = (suffix: number) => ({
    access_token: `access-${suffix}`, refresh_token: `refresh-${suffix}`, selected_role: 'manager', expires_in: 600,
  });
  const success = (data: object) => Response.json({ success: true, data });
  const fetch = vi.fn().mockResolvedValueOnce(success(session(1))).mockResolvedValueOnce(success(session(2)))
    .mockResolvedValueOnce(success({ logged_out: true }));
  const setItem = vi.fn();
  vi.stubGlobal('fetch', fetch);
  vi.stubGlobal('window', { sessionStorage: { setItem } });
  const auth = await AdminSession.login('test-user', 'test-input');
  expect(auth.role).toBe('manager');
  await Promise.all([auth.refresh(), auth.refresh()]);
  await auth.logout();
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    '/api/v1/auth/admin/login', '/api/v1/auth/refresh', '/api/v1/auth/logout',
  ]);
  expect(fetch.mock.calls[1][1].body).toBe(JSON.stringify({ refresh_token: 'refresh-1' }));
  expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer access-2');
  expect(setItem).not.toHaveBeenCalled();
});
