const sessionKey = 'sunshine-admin-demo-role';
export const roles = { manager: '店长', admin: '管理员' } as const;
export type DemoRole = keyof typeof roles;

export function isDemoRole(value: unknown): value is DemoRole {
  return value === 'manager' || value === 'admin';
}

export function readDemoRole(): DemoRole | undefined {
  if (typeof window === 'undefined') return undefined;
  const stored = window.sessionStorage.getItem(sessionKey);
  return isDemoRole(stored) ? stored : undefined;
}

export function writeDemoRole(role?: DemoRole) {
  if (role) window.sessionStorage.setItem(sessionKey, role);
  else window.sessionStorage.removeItem(sessionKey);
}
