import { allowsDemoSession } from '../config/environment';
import type { DemoRole } from '../config/navigation';

let activeRole: DemoRole | null = null;

export function startDemoSession(role: DemoRole): boolean {
  if (!allowsDemoSession()) return false;
  activeRole = role;
  return true;
}

export function getDemoRole(): DemoRole | null {
  return allowsDemoSession() ? activeRole : null;
}

export function endDemoSession(): void {
  activeRole = null;
}
