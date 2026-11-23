import type { MemberProfile } from './member-session';
import { RequestError, request } from './request';

export const customerStatuses = [
  { field: 'visit_status', labels: ['全部到店状态', '未到店', '已到店'], values: ['', 'not_visited', 'visited'] },
  { field: 'consume_status', labels: ['全部消费状态', '未消费', '已消费'], values: ['', 'not_consumed', 'consumed'] },
  { field: 'deal_status', labels: ['全部成交状态', '未成交', '已成交'], values: ['', 'not_dealt', 'dealt'] },
] as const;

type StatusField = (typeof customerStatuses)[number]['field'];
export type Customer = MemberProfile & Record<StatusField, string> & {
  last_effective_contact_at: string | null;
  next_recall_at: string | null;
  current_staff_id: string | null;
};

export function presentCustomer(customer: Customer) {
  return {
    ...customer,
    statuses: customerStatuses.map(({ field, labels, values }) => {
      const value = customer[field];
      return labels.find((_, index) => index > 0 && values[index] === value) ?? '状态未记录';
    }),
  };
}

type CustomerPage = { items: Customer[]; page: number; page_size: number; total: number };
type StaffSession = { access_token: string; selected_role: 'employee' };
let session: StaffSession | undefined;

// Consumes a server-issued employee session. The employee sign-in flow is pending approval.
export function setStaffCustomerSession(issued?: StaffSession): void {
  session = issued?.selected_role === 'employee' ? issued : undefined;
}

async function read<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const active = session;
  if (!active) throw new RequestError(401, 'INVALID_SESSION', '请先使用员工身份登录。');
  try {
    const data = await request<T>(path, 'GET', params, active.access_token);
    if (session === active) return data;
  } catch (error) {
    if (session === active && error instanceof RequestError && error.status === 401) {
      setStaffCustomerSession();
    }
    throw error;
  }
  throw new RequestError(401, 'INVALID_SESSION', '员工会话已切换。');
}

export function loadCustomers(q: string, selections: number[], page: number): Promise<CustomerPage> {
  const params: Record<string, string | number> = { page, page_size: 20 };
  if (q.trim()) params.q = q.trim();
  customerStatuses.forEach(({ field, values }, index) => {
    const value = values[selections[index]];
    if (value) params[field] = value;
  });
  return read('/staff/me/customers', params);
}

export function loadCustomer(id: string): Promise<Customer> {
  return read('/customers/' + encodeURIComponent(id));
}
