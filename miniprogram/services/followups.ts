import { entryRoute } from '../config/navigation';
import { readEmployee, writeEmployee, employeeSignedIn } from './staff-session';
import { RequestError, errorMessage } from './request';

export const contacts = ['phone', 'wechat', 'store_visit', 'other', 'home_visit'] as const;
export const contactNames = ['电话', '微信', '到店回访', '其他', '家访'];
const states: Record<string, string> = { pending: '待回访', postponed: '已延期', completed: '已完成', ignored: '已忽略' };
type Page<T> = { items: T[]; total: number };
type RecordView = { id: string; contact_type: typeof contacts[number]; content: string; followup_at: string };
type Task = { id: string; member_id: string; member_name: string; title: string; status: string; planned_at: string };
export const defaultDate = () => new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10);

function timeLabel(value: string) {
  return new Date(new Date(value).getTime() + 8 * 3600000).toISOString().slice(0, 16).replace('T', ' ');
}

export function failure(error: unknown) {
  if (error instanceof RequestError && error.status === 401 && !employeeSignedIn()) {
    wx.reLaunch({ url: entryRoute + '?employeeExpired=1' });
  }
  return errorMessage(error);
}

export function history(member: string, page: number, home: boolean) {
  return readEmployee<Page<RecordView>>('/customers/' + encodeURIComponent(member) + '/followups',
    home ? { page, contact_type: 'home_visit' } : { page });
}

export function followup(member: string, contact: string, content: string) {
  return writeEmployee('/customers/' + encodeURIComponent(member) + '/followups', { contact_type: contact, content });
}

export async function tasks(page: number) {
  const data = await readEmployee<Page<Task>>('/followup-tasks', { page });
  return { ...data, items: data.items.map(row => ({
    ...row, planned: timeLabel(row.planned_at), statusName: states[row.status],
    editable: row.status === 'pending' || row.status === 'postponed',
  })) };
}

export function changeTask(id: string, action: string, result: string, date: string, time: string) {
  const body: Record<string, string> = {};
  if (result.trim()) body.result = result.trim();
  if (action === 'postpone') body.postponed_until = date + 'T' + time + ':00+08:00';
  return writeEmployee('/followup-tasks/' + encodeURIComponent(id) + '/' + action, body);
}

export function presentFollowup(row: RecordView) {
  return { ...row, time: timeLabel(row.followup_at), typeName: contactNames[contacts.indexOf(row.contact_type)] };
}

export function validMemberId(id: string): boolean {
  return /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id);
}
