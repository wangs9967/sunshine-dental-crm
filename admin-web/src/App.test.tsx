import { renderToStaticMarkup } from 'react-dom/server';
import { expect, test } from 'vitest';
import App from './App';
import { loginReturnPath, menu, relatedRoutes, resolveRoute } from './routes';
import { isDemoRole } from './session';

test('renders the demo login without a session', () => {
  const html = renderToStaticMarkup(<App />);
  expect(html).toContain('登录管理后台');
  expect(html).toContain('进入后台');
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

test('only manager and admin identities can start a demo session', () => {
  expect(isDemoRole('manager')).toBe(true);
  expect(isDemoRole('admin')).toBe(true);
  expect(isDemoRole('employee')).toBe(false);
  expect(isDemoRole(null)).toBe(false);
});

test('each linked secondary page resolves to its owning menu', () => {
  for (const [parent, links] of Object.entries(relatedRoutes)) {
    for (const link of links) expect(resolveRoute(link.path)?.entry.path).toBe(parent);
  }
});

test('returns to a known local deep link with its query and hash after demo sign-in', () => {
  expect(loginReturnPath('/members/demo-member/?tab=summary#notes')).toBe('/members/demo-member/?tab=summary#notes');
  expect(resolveRoute('/members/demo-member/?tab=summary#notes')?.title).toBe('会员详情');
  for (const path of ['//example.org/members', '/\\example.org/members', 'https://example.org', '/login', '/missing', null]) {
    expect(loginReturnPath(path)).toBe('/dashboard');
  }
});
