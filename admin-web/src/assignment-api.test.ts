import { afterEach, expect, test, vi } from 'vitest';
import { AdminSession } from './session';

afterEach(() => vi.unstubAllGlobals());

const success = (data: unknown) => Response.json({ success: true, data });
const session = (role = 'admin', token = 'initial') => success({
  selected_role: role, access_token: token, refresh_token: 'refresh-' + token, expires_in: 600,
});
const failure = (status: number, code: string) => Response.json({
  success: false, error: { code, message: '', details: {} },
}, { status });

test.each(['admin', 'manager'])('%s uses the assignment API contract for reads and writes', async (role) => {
  const page = { items: [], page: 1, page_size: 20, total: 0 };
  const fetch = vi.fn().mockResolvedValueOnce(session(role))
    .mockImplementation((_, init: RequestInit) => Promise.resolve(success(init.method === 'POST'
      ? { current_assignment: { id: 'current' }, previous_assignment_id: null }
      : page)));
  vi.stubGlobal('fetch', fetch);
  const client = await AdminSession.login('test-user', 'test-password');
  const { signal } = new AbortController();
  await expect(client.read('/assignments?member_id=member&is_current=true', signal)).resolves.toEqual(page);
  await client.read('/assignments?member_id=member&is_current=false&page=1', signal);
  await client.read('/assignments/candidates?q=employee', signal);
  for (const expected_assignment_id of [null, 'current']) {
    await client.transferCustomer('member', { to_staff_id: 'target', expected_assignment_id, reason: '交接' });
  }
  expect(fetch.mock.calls.slice(1).map(([url]) => url)).toEqual([
    '/api/v1/admin/assignments?member_id=member&is_current=true',
    '/api/v1/admin/assignments?member_id=member&is_current=false&page=1',
    '/api/v1/admin/assignments/candidates?q=employee',
    '/api/v1/customers/member/transfer',
    '/api/v1/customers/member/transfer',
  ]);
  for (const [index, expected_assignment_id] of [[4, null], [5, 'current']] as const) {
    const init = fetch.mock.calls[index][1];
    expect(init).toMatchObject({
      method: 'POST', headers: { Authorization: 'Bearer initial', 'Content-Type': 'application/json' },
    });
    expect(JSON.parse(init.body)).toEqual({ to_staff_id: 'target', expected_assignment_id, reason: '交接' });
  }
});

test('rotates once after a transfer receives 401, preserving the confirmed assignment ID', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(session()).mockResolvedValueOnce(failure(401, 'INVALID_SESSION'))
    .mockResolvedValueOnce(session('admin', 'rotated')).mockResolvedValueOnce(failure(409, 'ASSIGNMENT_CHANGED'));
  vi.stubGlobal('fetch', fetch);
  const client = await AdminSession.login('test-user', 'test-password');
  await expect(client.transferCustomer('member', {
    to_staff_id: 'target', expected_assignment_id: 'confirmed', reason: '交接',
  })).rejects.toMatchObject({ status: 409, code: 'ASSIGNMENT_CHANGED' });
  expect(fetch.mock.calls[2][0]).toBe('/api/v1/auth/refresh');
  expect(fetch.mock.calls[3][1].body).toBe(fetch.mock.calls[1][1].body);
  expect(fetch.mock.calls[3][1].headers.Authorization).toBe('Bearer rotated');
  expect(fetch).toHaveBeenCalledTimes(4);
});

test('passes 403, invalid sessions and ambiguous network errors to the caller without replaying writes', async () => {
  const offline = new TypeError('Network error');
  const fetch = vi.fn().mockResolvedValueOnce(session()).mockResolvedValueOnce(failure(403, 'FORBIDDEN'))
    .mockRejectedValueOnce(offline).mockResolvedValueOnce(failure(401, 'INVALID_SESSION'))
    .mockResolvedValueOnce(failure(401, 'INVALID_SESSION'));
  vi.stubGlobal('fetch', fetch);
  const client = await AdminSession.login('test-user', 'test-password');
  const data = { to_staff_id: 'target', expected_assignment_id: null, reason: '初次分配' };
  await expect(client.transferCustomer('member', data)).rejects.toMatchObject({ status: 403, code: 'FORBIDDEN' });
  await expect(client.transferCustomer('member', data)).rejects.toBe(offline);
  await expect(client.transferCustomer('member', data)).rejects.toMatchObject({ status: 401 });
  expect(fetch.mock.calls.slice(1).map(([url]) => url)).toEqual([
    '/api/v1/customers/member/transfer', '/api/v1/customers/member/transfer',
    '/api/v1/customers/member/transfer', '/api/v1/auth/refresh',
  ]);
});
