const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.resolve(__dirname, '..');
const realSession = {
  access_token: 'fixture-access', refresh_token: 'fixture-refresh',
  selected_role: 'member', registration_required: false,
};
const signup = { ...realSession, selected_role: null, registration_required: true };

function harness(responses, storage = new Map(), scanResult = '') {
  const routes = [];
  const requests = [];
  const modals = [];
  const cache = new Map();
  let definition;
  const context = vm.createContext({
    wx: {
      getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
      login: (options) => options.success({ code: 'fixture-code' }),
      scanCode: (options) => options.success({ result: scanResult }),
      getStorageSync: (key) => storage.get(key),
      setStorageSync: (key, value) => storage.set(key, value),
      removeStorageSync: (key) => storage.delete(key),
      request: (request) => {
        requests.push(request);
        const result = responses.shift();
        assert.ok(result, 'Unexpected request: ' + request.url);
        if (result.offline) request.fail();
        else request.success({
          statusCode: result.status ?? 200,
          data: result.error ? { success: false, error: result.error } : { success: true, data: result.data },
        });
      },
      reLaunch: ({ url, success }) => { routes.push(url); success?.(); },
      redirectTo: ({ url }) => routes.push(url),
      showToast: () => {},
      showModal: ({ content, complete }) => { modals.push(content); complete(); },
    },
    Page: (page) => { definition = page; },
    Component: (component) => { definition = component; },
  });

  function load(file) {
    if (cache.has(file)) return cache.get(file);
    const module = { exports: {} };
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
    }).outputText;
    const run = vm.runInContext('(function(exports, require) {' + source + '\n})', context, { filename: file });
    run(module.exports, (specifier) => load(path.resolve(path.dirname(file), specifier + '.ts')));
    cache.set(file, module.exports);
    return module.exports;
  }

  function page(name) {
    load(path.join(root, name));
    const instance = { ...definition, ...definition.methods, data: { ...definition.data } };
    instance.setData = (data) => Object.assign(instance.data, data);
    return instance;
  }

  return { page, routes, requests, modals, storage, session: load(path.join(root, 'services/member-session.ts')),
    staff: load(path.join(root, 'services/staff-customers.ts')),
    employee: load(path.join(root, 'services/staff-session.ts')) };
}

const employeeSession = { ...realSession, selected_role: 'employee' };

test('employee binds from a scanned invitation then explicitly logs in, restores and logs out', async () => {
  const qr = 'sunshine-staff-bind:v1:11111111-1111-1111-1111-111111111111.' + 'A'.repeat(43);
  const env = harness([{ data: { wechat_bound: true } }, { data: employeeSession }], new Map(), qr);
  const entry = env.page('pages/auth/index.ts');
  await entry.staffBind();
  assert.match(env.requests[0].url, /\/auth\/wechat\/staff-bind$/);
  assert.equal(env.requests[0].data.invitation, qr);
  assert.equal(env.requests[0].data.code, 'fixture-code');
  assert.match(entry.data.notice, /已绑定/);
  assert.equal(env.storage.size, 0);
  await entry.staffLogin();
  assert.equal(env.requests[1].data.role, 'employee');
  assert.equal(env.routes.at(-1), '/pages/staff/dashboard');
  assert.deepEqual([...env.storage], [['sunshine-staff-restore', true]]);
  const restarted = harness([
    { data: employeeSession }, { data: { display_name: '验收员工', role: 'employee' } }, { data: { logged_out: true } },
  ], env.storage);
  restarted.page('pages/index/index.ts').onLoad();
  assert.equal(restarted.routes.at(-1), '/pages/auth/index?restore=employee');
  await restarted.page('pages/auth/index.ts').onLoad({ restore: 'employee' });
  assert.equal(restarted.requests[0].data.role, 'employee');
  assert.equal(restarted.routes.at(-1), '/pages/staff/dashboard');
  assert.equal((await restarted.employee.loadStaffProfile()).display_name, '验收员工');
  await restarted.employee.logoutEmployee();
  assert.match(restarted.requests.at(-1).url, /\/auth\/logout$/);
  assert.equal(restarted.storage.size, 0);
  assert.equal(restarted.employee.employeeSignedIn(), false);
});

test('staff refresh coalesces and rejected staff refresh returns customer list to login', async () => {
  const unauthorized = { status: 401, error: { code: 'INVALID_SESSION', message: '登录失效' } };
  const env = harness([{ data: employeeSession }, unauthorized, unauthorized,
    { data: { ...employeeSession, access_token: 'rotated' } }, { data: {} }, { data: {} },
    unauthorized, unauthorized]);
  await env.page('pages/auth/index.ts').staffLogin();
  await Promise.all([env.employee.loadStaffProfile(), env.employee.loadStaffProfile()]);
  assert.equal(env.requests.filter(({ url }) => url.endsWith('/auth/refresh')).length, 1);
  assert.equal(env.requests[4].header.Authorization, 'Bearer rotated');
  await env.page('pages/staff/customers.ts').onShow();
  assert.equal(env.employee.employeeSignedIn(), false);
  assert.equal(env.routes.at(-1), '/pages/auth/index?employeeExpired=1');
  assert.equal(env.storage.size, 0);
});

test('staff list requires a staff session and sends searches and status filters to the API', async () => {
  const customer = {
    id: '11111111-1111-1111-1111-111111111111', name: '测试客户', phone_masked: '199****0000',
    visit_status: 'visited', consume_status: 'not_consumed', deal_status: 'not_dealt',
  };
  const pageResult = { items: [customer], page: 1, page_size: 20, total: 1 };
  const env = harness([{ data: pageResult }, { data: pageResult }, { data: customer }, {
    status: 404, error: { code: 'NOT_FOUND', message: '客户不存在' },
  }]);
  const list = env.page('pages/staff/customers.ts');
  await list.onShow();
  assert.equal(list.data.loginRequired, true);
  assert.equal(env.requests.length, 0);
  env.staff.setStaffCustomerSession({ selected_role: 'employee', access_token: 'test-staff-token' });
  await list.onShow();
  assert.equal(list.data.customers[0].phone_masked, '199****0000');
  list.changeKeyword({ detail: { value: ' 测试 ' } });
  await list.changeStatus({ currentTarget: { dataset: { index: 0 } }, detail: { value: '2' } });
  assert.match(env.requests[1].url, /\/staff\/me\/customers$/);
  assert.equal(env.requests[1].data.q, '测试');
  assert.equal(env.requests[1].data.visit_status, 'visited');
  assert.equal(env.requests[1].header.Authorization, 'Bearer test-staff-token');
  const detail = env.page('pages/staff/customer-detail.ts');
  detail.onLoad({ id: customer.id });
  await detail.onShow();
  assert.equal(detail.data.customer.statuses[0], '已到店');
  detail.onHide();
  await detail.onShow();
  assert.equal(detail.data.customer, null);
  assert.equal(detail.data.unavailable, true);
});

test('registered login sends only the wx.login code and opens member home', async () => {
  const env = harness([{ data: realSession }]);
  const entry = env.page('pages/auth/index.ts');
  await entry.login();
  assert.equal(env.requests[0].data.code, 'fixture-code');
  assert.equal('openid' in env.requests[0].data, false);
  assert.deepEqual(env.routes, ['/pages/member/home']);
});

test('new member is routed to registration and only a valid form submits', async () => {
  const env = harness([{ data: signup }, { status: 201, data: { source_status: 'bound', session: realSession } }]);
  env.session.rememberScene('example%2Dscene');
  await env.page('pages/auth/index.ts').login();
  assert.deepEqual(env.routes, ['/pages/member/register']);
  const registration = env.page('pages/member/register.ts');
  registration.onLoad();
  await registration.submit();
  assert.match(registration.data.error, /姓名/);
  registration.setData({ name: '测试甲', birthday: '2020-02-30', phone: '123' });
  await registration.submit();
  assert.match(registration.data.error, /出生日期/);
  registration.setData({ birthday: '2000-01-02' });
  await registration.submit();
  assert.match(registration.data.error, /手机号/);
  assert.equal(env.requests.length, 1);
  registration.setData({ phone: '19900000000' });
  await registration.submit();
  assert.equal(env.requests[1].data.scene_token, 'example-scene');
  assert.equal(env.requests[1].header.Authorization, 'Bearer fixture-access');
  assert.equal(env.routes.at(-1), '/pages/member/home');
  assert.equal(env.session.memberState(), 'member');
});

test('a login error stays visible and an invalid source still opens home after registration', async () => {
  const env = harness([
    { status: 400, error: { code: 'WECHAT_CODE_INVALID', message: '微信登录凭据已失效' } },
    { data: signup }, { status: 201, data: { source_status: 'invalid', session: realSession } },
  ]);
  const entry = env.page('pages/auth/index.ts');
  await entry.login();
  assert.match(entry.data.error, /凭据已失效/);
  assert.deepEqual(env.routes, []);
  await entry.login();
  const registration = env.page('pages/member/register.ts');
  registration.setData({ name: '测试甲', birthday: '2000-01-02', phone: '19900000000' });
  await registration.submit();
  assert.match(env.modals[0], /来源码无效/);
  assert.equal(env.routes.at(-1), '/pages/member/home');
});

test('points come from the API and logout revokes the session before returning to entry', async () => {
  const env = harness([{ data: realSession }, { data: { balance: '0' } }, { data: { logged_out: true } }]);
  await env.page('pages/auth/index.ts').login();
  assert.equal(await env.session.loadPoints(), '0');
  const workspace = env.page('components/workspace/workspace.ts');
  workspace.setData({ realMember: true });
  await workspace.returnToEntry();
  assert.match(env.requests[2].url, /\/api\/v1\/auth\/logout$/);
  assert.equal(env.session.memberState(), undefined);
  assert.equal(env.routes.at(-1), '/pages/auth/index');
});

const memberProfile = {
  id: 'fixture-id', member_no: 'fixture-member-no', name: '测试会员',
  birthday: '2000-04-05', phone_masked: '199****0000', status: 'active',
  registered_at: '2026-11-23T01:00:00Z',
};

test('profile shows loading then reads the current member details with Bearer auth', async () => {
  const env = harness([{ data: realSession }, { data: memberProfile }]);
  await env.page('pages/auth/index.ts').login();
  const page = env.page('pages/member/profile-details.ts');
  const loading = page.onLoad();
  assert.equal(page.data.loading, true);
  await loading;
  assert.equal(page.data.loading, false);
  assert.deepEqual(page.data.profile, memberProfile);
  assert.match(env.requests[1].url, /\/api\/v1\/members\/me$/);
  assert.equal(env.requests[1].method, 'GET');
  assert.equal(env.requests[1].header.Authorization, 'Bearer fixture-access');
});

test('profile shows a network error, then recovers on retry', async () => {
  const env = harness([{ data: realSession }, { offline: true }, { data: memberProfile }]);
  await env.page('pages/auth/index.ts').login();
  const page = env.page('pages/member/profile-details.ts');
  await page.onLoad();
  assert.match(page.data.error, /网络连接失败/);
  assert.equal(page.data.profile, null);
  await page.loadProfile();
  assert.equal(page.data.error, '');
  assert.deepEqual(page.data.profile, memberProfile);
});

test('profile prompts for login when the existing session and refresh are rejected', async () => {
  const denied = { status: 401, error: { code: 'INVALID_SESSION', message: '会话已失效' } };
  const env = harness([{ data: realSession }, denied, denied]);
  await env.page('pages/auth/index.ts').login();
  const page = env.page('pages/member/profile-details.ts');
  await page.onLoad();
  assert.equal(page.data.expired, true);
  assert.equal(page.data.profile, null);
  assert.equal(env.session.memberState(), undefined);
  assert.match(env.requests[2].url, /\/api\/v1\/auth\/refresh$/);
  page.returnToLogin();
  assert.equal(env.routes.at(-1), '/pages/auth/index');
});

test('profile does not request member data from a page opened without a member session', async () => {
  const env = harness([]);
  const page = env.page('pages/member/profile-details.ts');
  await page.onLoad();
  assert.equal(page.data.expired, true);
  assert.equal(env.requests.length, 0);
});

test('cold startup gets a fresh WeChat code without persisting session tokens', async () => {
  const initial = harness([{ data: realSession }]);
  await initial.page('pages/auth/index.ts').login();
  assert.deepEqual([...initial.storage.values()], [true]);

  const cold = harness([{ data: realSession }, { data: { logged_out: true } }], initial.storage);
  assert.equal(cold.session.memberState(), undefined);
  cold.page('pages/index/index.ts').onLoad();
  assert.equal(cold.routes.at(-1), '/pages/auth/index?restore=1');
  await cold.page('pages/auth/index.ts').onLoad({ restore: '1' });
  assert.equal(cold.requests[0].data.code, 'fixture-code');
  assert.equal(cold.requests[0].header.Authorization, undefined);
  assert.equal(cold.routes.at(-1), '/pages/member/home');
  await cold.session.logoutMember();
  const signedOut = harness([], cold.storage);
  signedOut.page('pages/index/index.ts').onLoad();
  await signedOut.page('pages/auth/index.ts').onLoad({ restore: '1' });
  assert.equal(signedOut.routes.at(-1), '/pages/auth/index');
  assert.equal(signedOut.requests.length, 0);
});

test('cold startup with an unavailable API remains on login and allows retry', async () => {
  const initial = harness([{ data: realSession }]);
  await initial.page('pages/auth/index.ts').login();
  const cold = harness([{ offline: true }, { data: realSession }], initial.storage);
  const entry = cold.page('pages/auth/index.ts');
  await entry.onLoad({ restore: '1' });
  assert.match(entry.data.error, /网络连接失败/);
  assert.equal(entry.data.opening, false);
  assert.equal(cold.session.memberState(), undefined);
  assert.deepEqual(cold.routes, []);
  await entry.login();
  assert.equal(cold.routes.at(-1), '/pages/member/home');
});

test('home visit submits the fixed type and refreshes the filtered history', async () => {
  const id = '11111111-1111-1111-1111-111111111111';
  const env = harness([{ data: employeeSession }, { status: 201, data: {} }, { data: {
    items: [{ id, contact_type: 'home_visit', content: '家访测试', followup_at: '2030-04-05T01:00:00Z' }], total: 1,
  } }]);
  await env.page('pages/auth/index.ts').staffLogin();
  const form = env.page('pages/staff/home-visit.ts');
  form.onLoad({ id });
  await form.submit();
  assert.match(form.data.error, /沟通内容/);
  form.changeContent({ detail: { value: ' 家访测试 ' } });
  await form.submit();
  assert.equal(env.requests[1].data.contact_type, 'home_visit');
  assert.equal(env.requests[1].data.content, '家访测试');
  assert.equal(env.routes.at(-1), '/pages/staff/followup-history?id=' + id + '&home=1');
  const history = env.page('pages/staff/followup-history.ts');
  history.onLoad({ id, home: '1' });
  await history.load(1);
  assert.equal(env.requests[2].data.contact_type, 'home_visit');
  assert.equal(history.data.items[0].time, '2030-04-05 09:00');
});

test('postponing a staff task refreshes its displayed time', async () => {
  const item = { id: 'task', title: '回访', status: 'pending', planned_at: '2030-04-05T01:00:00Z' };
  const env = harness([{ data: employeeSession }, { data: { items: [item], total: 1 } }, { data: {} }, {
    data: { items: [{ ...item, status: 'postponed', planned_at: '2030-04-06T01:00:00Z' }], total: 1 },
  }]);
  await env.page('pages/auth/index.ts').staffLogin();
  const task = env.page('pages/staff/tasks.ts');
  await task.load(1);
  task.choose({ currentTarget: { dataset: { id: 'task', action: 'postpone' } } });
  task.setData({ date: '2030-04-06', time: '09:00' });
  await task.submit();
  assert.match(env.requests[2].url, /\/followup-tasks\/task\/postpone$/);
  assert.equal(env.requests[2].data.postponed_until, '2030-04-06T09:00:00+08:00');
  assert.equal(task.data.items[0].statusName, '已延期');
  assert.equal(task.data.items[0].planned, '2030-04-06 09:00');
});
