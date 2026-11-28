import { afterEach, expect, test, vi } from 'vitest';
import { AdminSession } from './session';

afterEach(() => vi.unstubAllGlobals());

test.each(['admin', 'manager'])('%s uses the followup API and preserves conflicts', async (role) => {
  const success = (data: unknown) => Response.json({ success: true, data });
  const page = { items: [], page: 1, page_size: 20, total: 0 };
  const fetch = vi.fn()
    .mockResolvedValueOnce(success({ selected_role: role, access_token: 'test-access', refresh_token: 'test-refresh', expires_in: 600 }))
    .mockResolvedValueOnce(success(page))
    .mockResolvedValueOnce(success(page))
    .mockResolvedValueOnce(success({ id: 'task' }))
    .mockResolvedValueOnce(Response.json({
      success: false, error: { code: 'TASK_TERMINAL', message: '任务已结束', details: {} },
    }, { status: 409 }));
  vi.stubGlobal('fetch', fetch);
  const session = await AdminSession.login('test', 'test');
  const { signal } = new AbortController();
  await expect(session.read('/followups?member_id=member&page=2', signal)).resolves.toEqual(page);
  await expect(session.followupTasks('page=2', signal)).resolves.toEqual(page);
  const body = { member_id: 'member', assigned_staff_id: 'staff', title: '测试回访', scheduled_at: '2030-04-05T09:00:00+08:00' };
  await session.writeFollowupTask('', body);
  await expect(session.writeFollowupTask('/task/ignore', { result: '已交接' }))
    .rejects.toMatchObject({ status: 409, code: 'TASK_TERMINAL' });
  expect(fetch.mock.calls.slice(1).map(([path]) => path)).toEqual([
    '/api/v1/admin/followups?member_id=member&page=2',
    '/api/v1/followup-tasks?page=2',
    '/api/v1/followup-tasks',
    '/api/v1/followup-tasks/task/ignore',
  ]);
  expect(JSON.parse(fetch.mock.calls[3][1].body)).toEqual(body);
  expect(fetch.mock.calls[4][1].headers.Authorization).toBe('Bearer test-access');
});
