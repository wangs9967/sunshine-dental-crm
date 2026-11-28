import { Alert, Button, Card, DatePicker, Form, Input, Modal, Select, Space, Table } from 'antd';
import { useState } from 'react';
import { EmptyState, ErrorState, StatusTag } from '../components/page';
import { AdminRequestError } from '../session';
import type { AdminSession } from '../session';
import { useAdminRead } from '../useAdminRead';

type Page<T> = { items: T[]; total: number };
type Person = { id: string; name?: string; member_no?: string; display_name?: string; employee_no?: string };
type MemberDetail = { current_staff_id: string | null; current_staff_name: string | null };
type RecordView = { id: string; member_name: string; staff_name: string; contact_type: string; content: string; followup_at: string };
type Task = {
  id: string; title: string; member_name: string; staff_name: string | null; planned_at: string; status: string;
};
type Filters = { member_id?: string; staff_id?: string; from?: string; to?: string };
type Props = { tasks: boolean; session?: AdminSession; onExpired: () => void };
const contacts: Record<string, string> = { phone: '电话', wechat: '微信', home_visit: '家访', store_visit: '到店回访', other: '其他' };
const states: Record<string, string> = { pending: '待回访', postponed: '已延期', completed: '已完成', ignored: '已忽略' };
const formatter = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short' });
const formatTime = (value: string) => formatter.format(new Date(value));
const pageSize = 20;

function PersonSelect({ session, staff, value, onChange, onExpired }: {
  session: AdminSession; staff?: boolean; value?: string; onChange: (id?: string) => void; onExpired: () => void;
}) {
  const [q, setQ] = useState('');
  const result = useAdminRead<Page<Person>>(session, (staff ? '/staff?' : '/members?') + new URLSearchParams({ q }));
  return <Space direction="vertical" style={{ display: 'flex', minWidth: 200 }}>
    <Select<string> aria-label={staff ? '员工' : '会员'} placeholder={staff ? '搜索员工' : '搜索会员'} value={value}
      allowClear showSearch filterOption={false} style={{ width: '100%' }} onSearch={(text) => setQ(text.trim().slice(0, 80))}
      onChange={onChange} loading={!result.data && !result.error}
      options={result.data?.items.map((row) => ({
        value: row.id, label: (row.name ?? row.display_name) + '（' + (row.member_no ?? row.employee_no ?? row.id.slice(-8)) + '）',
      }))} />
    {result.error && <Button size="small" onClick={result.expired ? onExpired : result.retry}>
      {result.expired ? '重新登录' : '候选读取失败，重试'}
    </Button>}
  </Space>;
}

function operationError(error: unknown) {
  if (!(error instanceof AdminRequestError)) return '网络异常，提交结果未确认。请核对刷新后的列表。';
  if (error.code === 'ASSIGNMENT_CHANGED') return '客户归属已变更，请核对当前负责人后重试。';
  if (error.status === 409) return '该任务已结束，请核对刷新后的列表。';
  if (error.status === 403) return '当前身份没有操作权限。';
  if (error.status === 404) return '客户或任务不存在。';
  return error.message;
}

function CreateTask({ session, onExpired, onSaved }: { session: AdminSession; onExpired: () => void; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [member, setMember] = useState<string>();
  const [title, setTitle] = useState('');
  const [when, setWhen] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const owner = useAdminRead<MemberDetail>(session, open && member ? '/members/' + encodeURIComponent(member) : undefined);
  const ownerId = owner.data?.current_staff_id;
  return <>
    <Button type="primary" onClick={() => { setMember(undefined); setTitle(''); setWhen(''); setError(''); setOpen(true); }}>
      创建人工任务
    </Button>
    <Modal open={open} title="创建人工回访任务" destroyOnHidden confirmLoading={busy} onCancel={() => { if (!busy) setOpen(false); }}
      okButtonProps={{ disabled: busy || !ownerId || !title.trim() || !when }} okText="创建" cancelText="取消"
      onOk={async () => {
        if (busy || !member || !ownerId || !title.trim() || !when) return;
        setBusy(true);
        setError('');
        try {
          await session.writeFollowupTask('', { member_id: member, assigned_staff_id: ownerId, title: title.trim(),
            scheduled_at: when.replace(' ', 'T') + ':00+08:00' });
          setOpen(false);
          onSaved();
        } catch (cause) {
          if (cause instanceof AdminRequestError && cause.status === 401) onExpired();
          else {
            setError(operationError(cause));
            owner.retry();
            onSaved();
          }
        } finally {
          setBusy(false);
        }
      }}>
      <Form layout="vertical" disabled={busy}>
        {(error || owner.error) && <Alert type="error" showIcon message={error || owner.error} action={owner.error &&
          <Button size="small" onClick={owner.expired ? onExpired : owner.retry}>{owner.expired ? '重新登录' : '重试'}</Button>} />}
        <Form.Item label="会员"><PersonSelect session={session} value={member} onChange={setMember} onExpired={onExpired} /></Form.Item>
        <Form.Item label="当前负责人">
          {owner.data ? owner.data.current_staff_name ?? '未分配' : member ? (owner.error ? '读取失败' : '正在读取…') : '请选择会员'}
        </Form.Item>
        <Form.Item label="任务标题"><Input value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} /></Form.Item>
        <Form.Item label="计划回访时间（北京时间）"><DatePicker showTime format="YYYY-MM-DD HH:mm"
          onChange={(value) => setWhen(value?.format('YYYY-MM-DD HH:mm') ?? '')} /></Form.Item>
      </Form>
    </Modal>
  </>;
}

function Results({ tasks, session, onExpired }: Props & { session: AdminSession }) {
  const [draft, setDraft] = useState<Filters>({});
  const [filters, setFilters] = useState<Filters>({});
  const [dateKey, setDateKey] = useState(0);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<Task>();
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
  const data = useAdminRead<Page<RecordView | Task>>(session, tasks ? undefined : '/followups?' + params, revision,
    tasks ? params.toString() : undefined);
  const reload = () => setRevision((number) => number + 1);
  const pagination = { current: page, pageSize, total: data.data?.total, showSizeChanger: false, onChange: setPage };
  return <>
    {tasks ? <Card><CreateTask session={session} onExpired={onExpired} onSaved={() => { setPage(1); reload(); }} /></Card> :
      <Card className="search-panel">
        <Space wrap align="start">
          <PersonSelect session={session} value={draft.member_id} onExpired={onExpired}
            onChange={(member_id) => setDraft((old) => ({ ...old, member_id }))} />
          <PersonSelect staff session={session} value={draft.staff_id} onExpired={onExpired}
            onChange={(staff_id) => setDraft((old) => ({ ...old, staff_id }))} />
          <DatePicker.RangePicker key={dateKey} placeholder={['开始日期', '结束日期']} onChange={(range) => setDraft((old) => ({
            ...old,
            from: range?.[0] ? range[0].format('YYYY-MM-DD') + 'T00:00:00+08:00' : undefined,
            to: range?.[1] ? range[1].add(1, 'day').format('YYYY-MM-DD') + 'T00:00:00+08:00' : undefined,
          }))} />
          <Button type="primary" onClick={() => { setFilters(draft); setPage(1); }}>查询</Button>
          <Button onClick={() => { setDraft({}); setFilters({}); setDateKey((n) => n + 1); setPage(1); }}>重置</Button>
        </Space>
      </Card>}
    {notice && <Alert type="warning" showIcon message={notice} />}
    {data.error ? <Space direction="vertical"><ErrorState title={data.error} />
      <Button onClick={data.expired ? onExpired : data.retry}>{data.expired ? '重新登录' : '重试'}</Button></Space> :
      tasks ? <Table<Task> rowKey="id" loading={!data.data} pagination={pagination}
        dataSource={data.data?.items as Task[] | undefined} scroll={{ x: 650 }}
        locale={{ emptyText: <EmptyState description="暂无回访任务" /> }} columns={[
          { title: '客户', dataIndex: 'member_name' }, { title: '负责人', render: (_, row) => row.staff_name ?? '未指派' },
          { title: '任务', dataIndex: 'title' }, { title: '计划时间', render: (_, row) => formatTime(row.planned_at) },
          { title: '状态', render: (_, row) => <StatusTag>{states[row.status]}</StatusTag> },
          { title: '操作', render: (_, row) => (row.status === 'pending' || row.status === 'postponed') &&
            <Button type="link" onClick={() => { setReason(''); setNotice(''); setSelected(row); }}>忽略</Button> },
        ]} /> : <Table<RecordView> rowKey="id" loading={!data.data} pagination={pagination}
          dataSource={data.data?.items as RecordView[] | undefined} scroll={{ x: 650 }}
          locale={{ emptyText: <EmptyState description="暂无跟进记录" /> }} columns={[
            { title: '会员', dataIndex: 'member_name' }, { title: '员工', dataIndex: 'staff_name' },
            { title: '类型', render: (_, row) => contacts[row.contact_type] },
            { title: '时间', render: (_, row) => formatTime(row.followup_at) },
            { title: '沟通内容', dataIndex: 'content', ellipsis: true },
          ]} expandable={{ expandedRowRender: (row) => <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{row.content}</div> }} />}
    <Modal title="忽略回访任务" open={!!selected} okText="确认忽略" cancelText="取消" confirmLoading={busy}
      onCancel={() => { if (!busy) setSelected(undefined); }} okButtonProps={{ disabled: !reason.trim() || busy }}
      onOk={async () => {
        if (!selected || busy || !reason.trim()) return;
        setBusy(true);
        try {
          await session.writeFollowupTask(`/${encodeURIComponent(selected.id)}/ignore`, { result: reason.trim() });
        } catch (cause) {
          if (cause instanceof AdminRequestError && cause.status === 401) onExpired();
          else setNotice(operationError(cause));
        } finally {
          setBusy(false);
          setSelected(undefined);
          reload();
        }
      }}>
      <p>{selected?.member_name} · {selected?.title}</p>
      <Input.TextArea aria-label="忽略原因" placeholder="填写处理结果" value={reason} onChange={(event) => setReason(event.target.value)} />
    </Modal>
  </>;
}

export default function FollowupPage(props: Props) {
  return props.session ? <Results {...props} session={props.session} /> : <EmptyState description="请使用后台账号登录后查看" />;
}
