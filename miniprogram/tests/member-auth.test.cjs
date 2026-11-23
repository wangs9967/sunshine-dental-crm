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

function harness(responses) {
  const routes = [];
  const requests = [];
  const modals = [];
  const cache = new Map();
  let definition;
  const context = vm.createContext({
    wx: {
      getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
      login: (options) => options.success({ code: 'fixture-code' }),
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

  return { page, routes, requests, modals, session: load(path.join(root, 'services/member-session.ts')) };
}

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
