export type DemoRole = 'member' | 'employee';
type Identifier = 'product' | 'order' | 'customer';
type NavigationMode = 'navigate' | 'redirect' | 'reLaunch';

type Link = { path: string; label: string; id?: Identifier; mode?: NavigationMode };
type WorkspaceRoute = {
  role: DemoRole;
  title: string;
  empty?: string;
  back?: string;
  id?: Identifier;
  links: readonly Link[];
};

export const entryRoute = '/pages/auth/index';

export const navigation = {
  member: {
    label: '会员端',
    tabs: [
      { path: '/pages/member/home', label: '首页' },
      { path: '/pages/points/index', label: '积分' },
      { path: '/pages/mall/index', label: '商城' },
      { path: '/pages/orders/index', label: '订单' },
      { path: '/pages/member/profile', label: '我的' },
    ],
  },
  employee: {
    label: '员工端',
    tabs: [
      { path: '/pages/staff/dashboard', label: '工作台' },
      { path: '/pages/staff/customers', label: '客户' },
      { path: '/pages/staff/tasks', label: '回访' },
      { path: '/pages/staff/profile', label: '我的' },
    ],
  },
} as const;

export const routes: Readonly<Record<string, WorkspaceRoute>> = {
  '/pages/member/home': {
    role: 'member', title: '会员首页',
    links: [
      { path: '/pages/points/index', label: '我的积分' },
      { path: '/pages/mall/index', label: '积分商城' },
      { path: '/pages/orders/index', label: '我的订单' },
      { path: '/pages/member/profile', label: '个人中心' },
    ],
  },
  '/pages/points/index': {
    role: 'member', title: '我的积分', empty: '暂无积分记录',
    links: [],
  },
  '/pages/mall/index': {
    role: 'member', title: '积分商城',
    links: [
      { path: '/pages/mall/detail', label: '查看演示商品', id: 'product' },
    ],
  },
  '/pages/mall/detail': {
    role: 'member', title: '商品详情', back: '/pages/mall/index', id: 'product',
    links: [
      { path: '/pages/mall/confirm', label: '查看兑换确认', id: 'product' },
    ],
  },
  '/pages/mall/confirm': {
    role: 'member', title: '兑换确认', back: '/pages/mall/detail', id: 'product',
    links: [
      { path: '/pages/mall/success', label: '预览兑换成功页', id: 'order', mode: 'redirect' },
    ],
  },
  '/pages/mall/success': {
    role: 'member', title: '兑换成功', empty: '此页为流程演示，未生成实际订单', back: '/pages/mall/index', id: 'order',
    links: [
      { path: '/pages/orders/detail', label: '查看演示订单', id: 'order', mode: 'reLaunch' },
      { path: '/pages/orders/index', label: '返回我的订单', mode: 'reLaunch' },
    ],
  },
  '/pages/orders/index': {
    role: 'member', title: '我的订单',
    links: [
      { path: '/pages/orders/detail', label: '查看演示订单', id: 'order' },
    ],
  },
  '/pages/orders/detail': {
    role: 'member', title: '订单详情', empty: '暂无订单数据', back: '/pages/orders/index', id: 'order',
    links: [],
  },
  '/pages/member/profile': {
    role: 'member', title: '个人中心',
    links: [
      { path: '/pages/member/profile-details', label: '会员资料' },
    ],
  },
  '/pages/member/profile-details': {
    role: 'member', title: '会员资料', empty: '暂无会员资料', back: '/pages/member/profile',
    links: [],
  },
  '/pages/staff/dashboard': {
    role: 'employee', title: '员工工作台',
    links: [
      { path: '/pages/staff/customers', label: '客户列表' },
      { path: '/pages/staff/tasks', label: '回访任务' },
      { path: '/pages/staff/profile', label: '员工资料' },
    ],
  },
  '/pages/staff/customers': {
    role: 'employee', title: '客户列表',
    links: [
      { path: '/pages/staff/customer-detail', label: '查看演示客户', id: 'customer' },
    ],
  },
  '/pages/staff/customer-detail': {
    role: 'employee', title: '客户详情', back: '/pages/staff/customers', id: 'customer',
    links: [
      { path: '/pages/staff/followup-create', label: '跟进记录', id: 'customer' },
      { path: '/pages/staff/home-visit', label: '家访记录', id: 'customer' },
      { path: '/pages/staff/followup-history', label: '跟进历史', id: 'customer' },
    ],
  },
  '/pages/staff/followup-create': {
    role: 'employee', title: '跟进记录', empty: '暂无跟进数据', back: '/pages/staff/customer-detail', id: 'customer',
    links: [],
  },
  '/pages/staff/tasks': {
    role: 'employee', title: '回访任务', empty: '暂无回访任务',
    links: [],
  },
  '/pages/staff/home-visit': {
    role: 'employee', title: '家访记录', empty: '暂无家访记录', back: '/pages/staff/customer-detail', id: 'customer',
    links: [],
  },
  '/pages/staff/followup-history': {
    role: 'employee', title: '跟进历史', empty: '暂无跟进历史', back: '/pages/staff/customer-detail', id: 'customer',
    links: [],
  },
  '/pages/staff/profile': {
    role: 'employee', title: '员工资料', empty: '暂无员工资料',
    links: [],
  },
};

const demoIds: Record<Identifier, string> = {
  product: 'demo-product',
  order: 'demo-order',
  customer: 'demo-customer',
};

export function isDemoRole(value: unknown): value is DemoRole {
  return value === 'member' || value === 'employee';
}

export function workspacePath(role: DemoRole): string {
  return navigation[role].tabs[0].path;
}

export function routeUrl(path: string, id?: unknown): string {
  return typeof id === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(id)
    ? `${path}?id=${encodeURIComponent(id)}`
    : path;
}

export function workspaceLinks(path: string, id?: unknown) {
  const route = routes[path];
  if (!route) return [];
  return route.links.map((link) => ({
    label: link.label,
    url: routeUrl(link.path, link.id && (link.id === route.id && id ? id : demoIds[link.id])),
    mode: link.mode ?? (routes[link.path].back ? 'navigate' : 'reLaunch'),
  }));
}
