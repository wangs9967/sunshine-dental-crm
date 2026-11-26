import { Button, Card, Descriptions, Input, Select, Space, Table } from 'antd';
import { useState } from 'react';
import type { Navigate } from '../App';
import { EmptyState, ErrorState, LoadingState, StatusTag } from '../components/page';
import { OpenStaff, StaffAccount } from '../components/staff';
import type { Staff } from '../components/staff';
import type { AdminSession } from '../session';
import { useAdminRead as useRead } from '../useAdminRead';

type Member = {
  id: string; name: string; member_no: string; birthday: string; phone_masked: string;
  registered_at: string; status: string;
};
type MemberDetail = Member & {
  source_employee_name: string | null; current_staff_name: string | null;
  visit_status: string | null; consume_status: string | null; deal_status: string | null;
};
type RecordPage<T> = { items: T[]; page: number; page_size: number; total: number };
type Base = '/members' | '/employees';
type Filters = { q: string; status?: string; staff_id?: string; role?: string };
type PageProps = { path: string; base: Base; navigate: Navigate; session?: AdminSession; onExpired: () => void };
const roles: Record<string, string> = { employee: '员工', manager: '店长', admin: '管理员' };
const operational: Record<string, string> = {
  visited: '已到店', not_visited: '未到店', consumed: '已消费', not_consumed: '未消费',
  dealt: '已成交', not_dealt: '未成交',
};
const dateTime = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short',
});

function ReadError({ error, expired, retry, onExpired }: {
  error: string; expired?: boolean; retry: () => void; onExpired: () => void;
}) {
  return <Space direction="vertical">
    <ErrorState title={error} />
    <Button onClick={expired ? onExpired : retry}>{expired ? '重新登录' : '重试'}</Button>
  </Space>;
}

function roleLabel(role: string) {
  return roles[role] ?? role;
}

function ProfileStatus({ status, member }: { status: string; member: boolean }) {
  return <StatusTag>{status === 'active' ? (member ? '正常' : '在职')
    : status === 'disabled' ? '停用' : status}</StatusTag>;
}

function DirectoryList({ base, session, navigate, onExpired }: Omit<PageProps, 'path' | 'session'> & { session: AdminSession }) {
  const member = base === '/members';
  const apiPath = member ? '/members' : '/staff';
  const [draft, setDraft] = useState<Filters>({ q: '' });
  const [search, setSearch] = useState({ filters: draft, page: 1, pageSize: 20 });
  const [staffSearch, setStaffSearch] = useState('');
  const params = new URLSearchParams({ page: String(search.page), page_size: String(search.pageSize) });
  for (const [key, value] of Object.entries(search.filters)) if (value?.trim()) params.set(key, value.trim());
  const list = useRead<RecordPage<Member | Staff>>(session, apiPath + '?' + params.toString());
  const staff = useRead<RecordPage<Staff>>(session, member ? '/staff?' + new URLSearchParams({ q: staffSearch }) : undefined);
  const staffOptions = staff.data?.items.map((item) => ({
    value: item.id, label: item.employee_no ? item.display_name + '（' + item.employee_no + '）' : item.display_name,
  }));
  return <>
    <Card className="search-panel">
      <form onSubmit={(event) => {
        event.preventDefault();
        setSearch({ ...search, filters: draft, page: 1 });
      }}>
        <Space wrap>
          <label htmlFor="directory-query">关键词</label>
          <Input id="directory-query" value={draft.q} maxLength={80}
            placeholder={member ? '姓名、会员编号或完整手机号' : '姓名或员工编号'}
            onChange={(event) => setDraft({ ...draft, q: event.target.value })} />
          <Select allowClear aria-label={member ? '会员状态' : '任职状态'} placeholder={member ? '会员状态' : '任职状态'}
            style={{ minWidth: 110 }} value={draft.status} onChange={(status) => setDraft({ ...draft, status })}
            options={[{ value: 'active', label: member ? '正常' : '在职' }, { value: 'disabled', label: '停用' }]} />
          {member ? <Select allowClear showSearch filterOption={false} aria-label="当前负责人" placeholder="当前负责人"
            style={{ minWidth: 170 }} value={draft.staff_id} options={staffOptions}
            loading={!staff.data && !staff.error} onSearch={(value) => setStaffSearch(value.trim().slice(0, 80))}
            onChange={(staff_id) => setDraft({ ...draft, staff_id })}
            notFoundContent={staff.error ? <Button type="link" onClick={staff.retry}>读取失败，重试</Button> : '未找到员工'} />
            : <Select allowClear aria-label="角色" placeholder="角色" style={{ minWidth: 110 }}
              value={draft.role} onChange={(role) => setDraft({ ...draft, role })}
              options={Object.entries(roles).map(([value, label]) => ({ value, label }))} />}
          <Button htmlType="submit" type="primary">查询</Button>
          <Button onClick={() => {
            setDraft({ q: '' });
            setStaffSearch('');
            setSearch({ ...search, filters: { q: '' }, page: 1 });
          }}>重置</Button>
          {!member && <OpenStaff session={session} onExpired={onExpired}
            onCreated={(staff) => navigate(base + '/' + staff.id)} />}
        </Space>
      </form>
    </Card>
    {list.error ? <ReadError {...list} error={list.error} onExpired={onExpired} />
      : <Table<Member | Staff> rowKey="id" loading={!list.data} dataSource={list.data?.items ?? []}
          locale={{ emptyText: list.data && <EmptyState description="没有符合条件的记录" /> }}
          pagination={{
            current: search.page, pageSize: search.pageSize, total: list.data?.total, showSizeChanger: true,
            onChange: (page, pageSize) => setSearch({ ...search, page, pageSize }),
          }}
          columns={[
            { title: member ? '会员编号' : '员工编号', render: (_, row) => 'member_no' in row ? row.member_no : row.employee_no ?? '—' },
            { title: '姓名', render: (_, row) => {
              const target = base + '/' + row.id;
              return <a href={target} onClick={(event) => navigate(target, event)}>{'name' in row ? row.name : row.display_name}</a>;
            } },
            member ? { title: '脱敏手机号', render: (_, row) => 'phone_masked' in row && row.phone_masked }
              : { title: '角色', render: (_, row) => 'role' in row && roleLabel(row.role) },
            { title: member ? '会员状态' : '任职状态', render: (_, row) => <ProfileStatus status={row.status} member={member} /> },
            ...(!member ? [{ title: '微信绑定', render: (_: unknown, row: Member | Staff) =>
              'wechat_bound' in row && (row.wechat_bound ? '已绑定' : '未绑定') }] : []),
            ...(member ? [{ title: '注册时间', render: (_: unknown, row: Member | Staff) =>
              'registered_at' in row && dateTime.format(new Date(row.registered_at)) }] : []),
          ]} />}
  </>;
}

function DirectoryDetail({ base, path, session, navigate, onExpired }: Omit<PageProps, 'session'> & { session: AdminSession }) {
  const member = base === '/members';
  const id = path.slice(base.length + 1);
  const validId = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id);
  const result = useRead<MemberDetail | Staff>(session, validId ? (member ? '/members/' : '/staff/') + id : undefined);
  const row = result.data;
  return <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
    <a href={base} onClick={(event) => navigate(base, event)}>返回列表</a>
    {!validId ? <ErrorState title="该资料不存在。" />
      : result.error ? <ReadError {...result} error={result.error} onExpired={onExpired} />
      : row ? <Card>
        {'member_no' in row ? <Descriptions column={{ xs: 1, sm: 2 }} title="会员资料">
          <Descriptions.Item label="会员编号">{row.member_no}</Descriptions.Item>
          <Descriptions.Item label="姓名">{row.name}</Descriptions.Item>
          <Descriptions.Item label="生日">{row.birthday}</Descriptions.Item>
          <Descriptions.Item label="脱敏手机号">{row.phone_masked}</Descriptions.Item>
          <Descriptions.Item label="注册时间">{dateTime.format(new Date(row.registered_at))}</Descriptions.Item>
          <Descriptions.Item label="会员状态"><ProfileStatus status={row.status} member /></Descriptions.Item>
          <Descriptions.Item label="来源员工">{row.source_employee_name ?? '未关联'}</Descriptions.Item>
          <Descriptions.Item label="当前负责人">{row.current_staff_name ?? '未分配'}</Descriptions.Item>
          <Descriptions.Item label="到店状态">{operational[row.visit_status ?? ''] ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="消费状态">{operational[row.consume_status ?? ''] ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="成交状态">{operational[row.deal_status ?? ''] ?? '—'}</Descriptions.Item>
        </Descriptions> : <Descriptions column={{ xs: 1, sm: 2 }} title="员工档案">
          <Descriptions.Item label="员工编号">{row.employee_no ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="姓名">{row.display_name}</Descriptions.Item>
          <Descriptions.Item label="角色">{roleLabel(row.role)}</Descriptions.Item>
        </Descriptions>}
      </Card> : <LoadingState />}
    {row && 'wechat_bound' in row && <StaffAccount key={row.id} initial={row} session={session} onExpired={onExpired} />}
  </Space>;
}

export default function DirectoryPage(props: PageProps) {
  const { session } = props;
  if (!session) return <EmptyState description="请使用后台账号登录后查看资料" />;
  return props.path === props.base ? <DirectoryList {...props} session={session} />
    : <DirectoryDetail {...props} session={session} />;
}
