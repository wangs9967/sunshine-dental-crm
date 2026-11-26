import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, expect, test, vi } from 'vitest';
import { OpenStaff, StaffAccount } from './components/staff';
import { AdminSession } from './session';

afterEach(() => vi.unstubAllGlobals());

const staff = {
  id: 'staff-id', employee_no: 'E-01', role: 'employee', status: 'active', display_name: '验收员工', wechat_bound: false,
};
const envelope = (data: unknown) => Response.json({ success: true, data });
const authenticated = (role: string) => envelope({
  selected_role: role, access_token: 'local-fixture', refresh_token: 'local-refresh', expires_in: 600,
});

test.each(['admin', 'manager'])('%s sees its permitted staff controls', async (role) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(authenticated(role)));
  const session = await AdminSession.login('fixture', 'test-only');
  const props = { session, onExpired: vi.fn() };
  const page = renderToStaticMarkup(<>
    <OpenStaff {...props} onCreated={vi.fn()} />
    <StaffAccount {...props} initial={staff} />
  </>);
  expect(page).toContain('微信未绑定');
  for (const action of ['开通员工', '生成绑定二维码', '停用员工']) {
    expect(page.includes(action)).toBe(role === 'admin');
  }
  const stopped = renderToStaticMarkup(<StaffAccount {...props} initial={{ ...staff, status: 'disabled', wechat_bound: true }} />);
  expect(stopped).toContain('微信已绑定');
  expect(stopped.includes('重新启用')).toBe(role === 'admin');
  expect(stopped).not.toContain('生成绑定二维码');
});

test('staff writes share the authenticated API client and submit only approved fields', async () => {
  const fetch = vi.fn()
    .mockResolvedValueOnce(authenticated('admin'))
    .mockResolvedValueOnce(envelope(staff))
    .mockResolvedValueOnce(envelope({ qr_payload: 'fixture-invitation', expires_at: '2030-01-01T00:00:00Z' }))
    .mockResolvedValueOnce(envelope({ ...staff, status: 'disabled' }));
  vi.stubGlobal('fetch', fetch);
  const session = await AdminSession.login('fixture', 'test-only');
  const body = { display_name: staff.display_name, employee_no: staff.employee_no };
  await expect(session.writeStaff('', 'POST', body)).resolves.toEqual(staff);
  await expect(session.writeStaff('/staff-id/wechat-invitation', 'POST')).resolves.toMatchObject({ qr_payload: 'fixture-invitation' });
  await expect(session.writeStaff('/staff-id', 'PATCH', { status: 'disabled' })).resolves.toMatchObject({ status: 'disabled' });
  expect(fetch.mock.calls.slice(1).map(([url, init]) => [url, init.method, init.body])).toEqual([
    ['/api/v1/admin/staff', 'POST', JSON.stringify(body)],
    ['/api/v1/admin/staff/staff-id/wechat-invitation', 'POST', undefined],
    ['/api/v1/admin/staff/staff-id', 'PATCH', '{"status":"disabled"}'],
  ]);
});
