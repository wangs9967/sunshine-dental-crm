import { Alert, Button, Card, Descriptions, Input, Select, Space, Table } from 'antd';
import { useState } from 'react';
import { ConfirmDialog, EmptyState, ErrorState, LoadingState } from '../components/page';
import { AdminRequestError } from '../session';
import type { AdminSession } from '../session';
import { useAdminRead } from '../useAdminRead';

type Page<T> = { items: T[]; total: number };
type Member = { id: string; name: string; member_no: string };
type MemberDetail = { source_employee_name: string | null };
type Candidate = { id: string; display_name: string };
type Assignment = {
  id: string; staff_id: string; staff_name: string; started_at: string; ended_at: string | null;
  change_reason: string | null;
};
type Notice = { type: 'success' | 'error' | 'warning'; message: string; expired?: boolean };
type Props = { session?: AdminSession; onExpired: () => void };
const pageSize = 20;
const dateTime = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short',
});

function ReadFailure({ result, onExpired }: {
  result: { error?: string; expired?: boolean; retry: () => void }; onExpired: () => void;
}) {
  if (!result.error) return null;
  return <Space direction="vertical">
    <ErrorState title={result.error} />
    <Button size="small" onClick={result.expired ? onExpired : result.retry}>
      {result.expired ? '重新登录' : '重试'}
    </Button>
  </Space>;
}

function memberLabel(member: Member) {
  return member.name + '（' + member.member_no + '）';
}

function AssignmentDetail({ member, session, onExpired }: {
  member: Member; session: AdminSession; onExpired: () => void;
}) {
  const [revision, setRevision] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [staffSearch, setStaffSearch] = useState('');
  const [target, setTarget] = useState<Candidate>();
  const [reason, setReason] = useState('');
  const [notice, setNotice] = useState<Notice>();
  const [saving, setSaving] = useState(false);
  const [confirmation, setConfirmation] = useState<{
    target: Candidate; reason: string; current: Assignment | null;
  }>();

  const query = new URLSearchParams({ member_id: member.id });
  const profile = useAdminRead<MemberDetail>(session, '/members/' + encodeURIComponent(member.id));
  const currentRead = useAdminRead<Page<Assignment>>(session, '/assignments?' + query + '&is_current=true', revision);
  const history = useAdminRead<Page<Assignment>>(
    session, '/assignments?' + query + '&is_current=false&page=' + historyPage + '&page_size=' + pageSize, revision,
  );
  const candidates = useAdminRead<Page<Candidate>>(
    session, currentRead.data ? '/assignments/candidates?' + new URLSearchParams({ q: staffSearch }) : undefined, revision,
  );
  const current = currentRead.data?.items[0] ?? null;

  function refreshAssignments() {
    setHistoryPage(1);
    setRevision((n) => n + 1);
  }

  async function submit() {
    if (!confirmation || saving) return;
    setSaving(true);
    setNotice(undefined);
    try {
      await session.transferCustomer(member.id, {
        to_staff_id: confirmation.target.id,
        expected_assignment_id: confirmation.current?.id ?? null,
        reason: confirmation.reason,
      });
      setNotice({ type: 'success', message: confirmation.current ? '客户已转移。' : '客户已分配。' });
      setReason('');
      setStaffSearch('');
      refreshAssignments();
    } catch (error) {
      if (error instanceof AdminRequestError && error.status === 401) {
        setNotice({ type: 'error', message: error.message, expired: true });
      } else if (error instanceof AdminRequestError && error.status === 403) {
        setNotice({ type: 'error', message: '当前身份没有分配或转移权限。' });
      } else if (error instanceof AdminRequestError && error.status === 409) {
        setNotice({ type: 'warning', message: '客户归属发生冲突。请在刷新后核对当前负责人，再重新选择员工并确认。' });
        refreshAssignments();
      } else if (error instanceof AdminRequestError && error.code === 'STAFF_NOT_ELIGIBLE') {
        setNotice({ type: 'error', message: '所选员工已不可分配，请重新选择在职员工。' });
        candidates.retry();
      } else {
        setNotice({ type: 'warning', message: '未能确认提交结果，请核对刷新后的客户归属再决定是否重试。' });
        refreshAssignments();
      }
    } finally {
      setConfirmation(undefined);
      setTarget(undefined);
      setSaving(false);
    }
  }

  return <>
    <Card title={memberLabel(member)}>
      <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
        {notice && <Alert showIcon type={notice.type} message={notice.message} action={notice.expired &&
          <Button size="small" onClick={onExpired}>重新登录</Button>} />}
        {currentRead.error ? <ReadFailure result={currentRead} onExpired={onExpired} /> :
          !currentRead.data ? <LoadingState /> :
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="当前负责人">{current?.staff_name ?? '未分配'}</Descriptions.Item>
            <Descriptions.Item label="首次来源员工">{profile.error ?
              <ReadFailure result={profile} onExpired={onExpired} /> :
              profile.data ? profile.data.source_employee_name ?? '未关联' : '正在读取…'}</Descriptions.Item>
            {current && <Descriptions.Item label="开始时间">
              {dateTime.format(new Date(current.started_at))}
            </Descriptions.Item>}
          </Descriptions>}
        {currentRead.data && <form onSubmit={(event) => {
          event.preventDefault();
          if (target && reason.trim() && !saving && !notice?.expired) {
            setConfirmation({ target, reason: reason.trim(), current });
          }
        }}>
          <Space direction="vertical" style={{ display: 'flex', maxWidth: 520 }}>
            <label htmlFor="assignment-employee">目标员工</label>
            <Select<{ value: string; label: string }> id="assignment-employee" showSearch filterOption={false} allowClear labelInValue
              placeholder="搜索在职员工姓名" loading={!candidates.data && !candidates.error}
              value={target && { value: target.id, label: target.display_name }}
              onSearch={(value) => setStaffSearch(value.trim().slice(0, 80))}
              onChange={(option) => setTarget(option && { id: option.value, display_name: String(option.label) })}
              options={candidates.data?.items.filter((staff) => staff.id !== current?.staff_id).map((staff) => ({
                value: staff.id, label: staff.display_name + '（' + staff.id.slice(-8) + '）',
              }))}
              notFoundContent={candidates.error ? '员工列表读取失败' : '没有符合条件的员工'}
              style={{ width: '100%' }} />
            <ReadFailure result={candidates} onExpired={onExpired} />
            <label htmlFor="assignment-reason">变更原因</label>
            <Input.TextArea id="assignment-reason" value={reason} maxLength={500} rows={2}
              onChange={(event) => setReason(event.target.value)} />
            <Button type="primary" htmlType="submit" loading={saving} disabled={!target || !reason.trim() || notice?.expired}>
              {current ? '转移客户' : '分配客户'}
            </Button>
          </Space>
        </form>}
      </Space>
    </Card>
    <Card title="历史归属">
      {history.error ? <ReadFailure result={history} onExpired={onExpired} /> :
        <Table<Assignment> rowKey="id" size="small" loading={!history.data} dataSource={history.data?.items ?? []}
          locale={{ emptyText: <EmptyState description="暂无历史归属" /> }}
          pagination={{ current: historyPage, pageSize, total: history.data?.total, onChange: setHistoryPage, showSizeChanger: false }}
          columns={[
            { title: '负责人', dataIndex: 'staff_name' },
            { title: '开始时间', render: (_, row) => dateTime.format(new Date(row.started_at)) },
            { title: '结束时间', render: (_, row) => row.ended_at ? dateTime.format(new Date(row.ended_at)) : '—' },
            { title: '归属原因', render: (_, row) => row.change_reason ?? '—' },
          ]} scroll={{ x: 600 }} />}
    </Card>
    <ConfirmDialog open={!!confirmation} title={confirmation?.current ? '确认转移客户' : '确认分配客户'} loading={saving}
      onCancel={() => { if (!saving) setConfirmation(undefined); }} onConfirm={submit}>
      {confirmation && <Descriptions size="small" column={1}>
        <Descriptions.Item label="会员">{memberLabel(member)}</Descriptions.Item>
        <Descriptions.Item label="当前负责人">{confirmation.current?.staff_name ?? '未分配'}</Descriptions.Item>
        <Descriptions.Item label="新负责人">{confirmation.target.display_name}</Descriptions.Item>
        <Descriptions.Item label="变更原因">{confirmation.reason}</Descriptions.Item>
      </Descriptions>}
    </ConfirmDialog>
  </>;
}

function AssignmentsWorkspace({ session, onExpired }: { session: AdminSession; onExpired: () => void }) {
  const [search, setSearch] = useState('');
  const [member, setMember] = useState<Member>();
  const list = useAdminRead<Page<Member>>(session, '/members?' + new URLSearchParams({ q: search }));
  return <>
    <Card title="选择会员">
      <Space direction="vertical" style={{ display: 'flex', maxWidth: 520 }}>
        <Select<{ value: string; label: string }> aria-label="搜索会员" placeholder="输入姓名、会员编号或完整手机号" showSearch allowClear filterOption={false}
          labelInValue loading={!list.data && !list.error} value={member && { value: member.id, label: memberLabel(member) }}
          onSearch={(value) => setSearch(value.trim().slice(0, 80))}
          onChange={(option) => setMember(list.data?.items.find((item) => item.id === option?.value))}
          options={list.data?.items.map((item) => ({ value: item.id, label: memberLabel(item) }))}
          notFoundContent={list.error ? '会员列表读取失败' : '没有符合条件的会员'} style={{ width: '100%' }} />
        <ReadFailure result={list} onExpired={onExpired} />
      </Space>
    </Card>
    {member && <AssignmentDetail key={member.id} member={member} session={session} onExpired={onExpired} />}
  </>;
}

export default function AssignmentsPage({ session, onExpired }: Props) {
  return session ? <AssignmentsWorkspace session={session} onExpired={onExpired} /> :
    <EmptyState description="请使用后台账号登录后管理客户归属" />;
}
