import type { MemberProfile } from './member-session';
import { readEmployee } from './staff-session';

export { setStaffCustomerSession } from './staff-session';

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

export function loadCustomers(q: string, selections: number[], page: number): Promise<CustomerPage> {
  const params: Record<string, string | number> = { page, page_size: 20 };
  if (q.trim()) params.q = q.trim();
  customerStatuses.forEach(({ field, values }, index) => {
    const value = values[selections[index]];
    if (value) params[field] = value;
  });
  return readEmployee('/staff/me/customers', params);
}

export function loadCustomer(id: string): Promise<Customer> {
  return readEmployee('/customers/' + encodeURIComponent(id));
}
