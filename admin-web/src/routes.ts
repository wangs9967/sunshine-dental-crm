const menu = [
  { path: '/dashboard', title: '数据总览', group: '工作台', icon: 'dashboard' },
  { path: '/members', title: '会员管理', group: '客户运营', icon: 'members' },
  { path: '/employees', title: '员工管理', group: '客户运营', icon: 'staff' },
  { path: '/assignments', title: '客户归属', group: '客户运营', icon: 'assignment' },
  { path: '/followups', title: '客户跟进', group: '客户运营', icon: 'followup' },
  { path: '/points/accounts', title: '积分管理', group: '积分商城', icon: 'points' },
  { path: '/mall/products', title: '商品管理', group: '积分商城', icon: 'product' },
  { path: '/mall/orders', title: '兑换订单', group: '积分商城', icon: 'orders' },
  { path: '/mall/verifications', title: '核销记录', group: '积分商城', icon: 'verify' },
  { path: '/settings', title: '系统设置', group: '系统管理', icon: 'settings' },
  { path: '/roles', title: '角色权限', group: '系统管理', icon: 'roles' },
  { path: '/audit-logs', title: '操作日志', group: '系统管理', icon: 'audit' },
] as const;

export { menu };
export type MenuEntry = (typeof menu)[number];

const secondaryRoutes = [
  [/^\/members\/[^/]+$/, '/members', '会员详情'],
  [/^\/employees\/[^/]+$/, '/employees', '员工详情'],
  [/^\/tasks$/, '/followups', '回访提醒'],
  [/^\/points\/records$/, '/points/accounts', '积分流水'],
  [/^\/mall\/products\/new$/, '/mall/products', '新增商品'],
  [/^\/mall\/products\/[^/]+\/edit$/, '/mall/products', '编辑商品'],
  [/^\/mall\/products\/[^/]+\/stock$/, '/mall/products', '库存调整'],
  [/^\/mall\/products\/[^/]+$/, '/mall/products', '商品详情'],
  [/^\/mall\/orders\/[^/]+$/, '/mall/orders', '订单详情'],
  [/^\/mall\/verify$/, '/mall/verifications', '凭证核销'],
] as const;

export function resolveRoute(path: string): { entry: MenuEntry; title: string } | undefined {
  const canonical = routePath(path) === '/' ? '/dashboard' : routePath(path);
  const entry = menu.find((item) => item.path === canonical);
  if (entry) return { entry, title: entry.title };

  const secondary = secondaryRoutes.find(([pattern]) => pattern.test(canonical));
  if (!secondary) return undefined;
  const parent = menu.find((item) => item.path === secondary[1]);
  return parent && { entry: parent, title: secondary[2] };
}

export const relatedRoutes: Readonly<Record<string, readonly { path: string; title: string }[]>> = {
  '/followups': [{ path: '/tasks', title: '回访提醒' }],
  '/points/accounts': [{ path: '/points/records', title: '积分流水' }],
  '/mall/products': [
    { path: '/mall/products/new', title: '新增商品' },
    { path: '/mall/products/demo-product', title: '商品详情示例' },
    { path: '/mall/products/demo-product/edit', title: '编辑商品示例' },
    { path: '/mall/products/demo-product/stock', title: '库存调整示例' },
  ],
  '/mall/orders': [{ path: '/mall/orders/demo-order', title: '订单详情示例' }],
  '/mall/verifications': [{ path: '/mall/verify', title: '凭证核销' }],
};

export function routePath(url: string): string {
  return url.split(/[?#]/, 1)[0].replace(/\/+$/, '') || '/';
}

export function loginReturnPath(target: string | null): string {
  return target && /^\/(?!\/)/.test(target) && !/[\\\u0000-\u0020]/.test(target) && resolveRoute(target)
    ? (routePath(target) === '/' ? '/dashboard' : target)
    : '/dashboard';
}
