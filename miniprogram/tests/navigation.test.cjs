const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { memberRegistrationRoute, navigation, routes, routeUrl, workspaceLinks, workspacePath } = require('../config/navigation.ts');
const app = require('../app.json');

test('every workspace page is registered, present and reachable from its own entrance', () => {
  assert.equal(new Set(app.pages).size, app.pages.length);
  assert.deepEqual(new Set(app.pages.slice(2).map((page) => `/${page}`)),
    new Set([...Object.keys(routes), memberRegistrationRoute]));

  for (const [role, { tabs }] of Object.entries(navigation)) {
    const visited = new Set();
    const remaining = [workspacePath(role), ...tabs.map(({ path }) => path)];
    while (remaining.length) {
      const page = remaining.pop();
      if (visited.has(page)) continue;
      visited.add(page);
      const route = routes[page];
      assert.equal(route.role, role, page);
      if (route.back) assert.equal(routes[route.back].role, role, page);
      remaining.push(...route.links.map((link) => link.path));
      for (const suffix of ['.ts', '.json', '.wxml']) {
        assert.ok(fs.existsSync(path.join(__dirname, '..', page.slice(1) + suffix)), page + suffix);
      }
    }
    assert.equal(visited.size, Object.values(routes).filter((route) => route.role === role).length);
  }
});

test('member exchange replaces confirmation and reopens orders without a product back stack', () => {
  const [detail] = workspaceLinks('/pages/mall/index');
  assert.equal(detail.url, '/pages/mall/detail?id=demo-product');
  assert.deepEqual(workspaceLinks('/pages/mall/detail', 'p_123')[0], {
    label: '查看兑换确认', url: '/pages/mall/confirm?id=p_123', mode: 'navigate',
  });
  assert.equal(workspaceLinks('/pages/mall/confirm', 'p_123')[0].mode, 'redirect');
  assert.equal(workspaceLinks('/pages/mall/success', 'o_123')[0].url, '/pages/orders/detail?id=o_123');
  assert.equal(workspaceLinks('/pages/mall/success', 'o_123')[0].mode, 'reLaunch');
  assert.equal(routes['/pages/orders/detail'].back, '/pages/orders/index');
});

test('each staff detail link retains the same customer ID and supports a parent fallback', () => {
  const links = workspaceLinks('/pages/staff/customer-detail', 'customer_3');
  assert.equal(links.length, 3);
  for (const { url, mode } of links) {
    const [page, query] = url.split('?');
    assert.equal(query, 'id=customer_3');
    assert.equal(mode, 'navigate');
    assert.equal(routes[page].back, '/pages/staff/customer-detail');
  }
  assert.equal(routeUrl('/pages/staff/customer-detail', 'a&role=staff'), '/pages/staff/customer-detail');
});
