export type DemoRole = 'member' | 'employee';

export const entryRoute = '/pages/auth/index';

export const navigation = {
  member: {
    label: '会员端',
    links: [
      { url: '/pages/member/home', label: '会员首页', description: '查看会员服务入口' },
      { url: '/pages/points/index', label: '我的积分', description: '查看积分与变动记录' },
      { url: '/pages/member/profile', label: '个人中心', description: '查看会员资料入口' },
    ],
  },
  employee: {
    label: '员工端',
    links: [
      { url: '/pages/staff/dashboard', label: '员工工作台', description: '查看日常工作入口' },
      { url: '/pages/staff/tasks', label: '回访任务', description: '查看客户回访待办' },
      { url: '/pages/staff/profile', label: '员工资料', description: '查看员工身份入口' },
    ],
  },
} as const;

export function isDemoRole(value: unknown): value is DemoRole {
  return value === 'member' || value === 'employee';
}
