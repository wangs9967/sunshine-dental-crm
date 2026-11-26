import { Alert, Button, Card, Form, Input, Modal, QRCode, Space } from 'antd';
import { useEffect, useState } from 'react';
import { AdminRequestError } from '../session';
import type { AdminSession } from '../session';
import { ConfirmDialog, StatusTag } from './page';

export type Staff = { id: string; display_name: string; employee_no: string | null; role: string; status: string; wechat_bound: boolean };
type Invitation = { qr_payload: string; expires_at: string };
type Props = { session: AdminSession; onExpired: () => void };
const expiryFormat = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'medium',
});

function operationError(error: unknown) {
  if (!(error instanceof AdminRequestError)) return '网络异常，请核对员工状态后重试。';
  if (error.code === 'EMPLOYEE_NO_EXISTS') return '该工号已存在。';
  if (error.code === 'STAFF_INVITATION_NOT_AVAILABLE') return '该员工已绑定或不在职，请刷新档案后查看。';
  if (error.status === 403) return '当前身份没有员工管理权限。';
  if (error.status === 422) return '请检查填写内容。';
  if (error.status === 401) return error.message;
  return '员工管理请求失败，请核对员工状态后重试。';
}

export function OpenStaff({ session, onExpired, onCreated }: Props & { onCreated: (staff: Staff) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [form] = Form.useForm<{ display_name: string; employee_no: string }>();
  if (session.role !== 'admin') return null;
  return <>
    <Button type="primary" onClick={() => { form.resetFields(); setError(''); setOpen(true); }}>开通员工</Button>
    <Modal open={open} title="开通员工" okText="开通" cancelText="取消" confirmLoading={busy}
      onCancel={() => { if (!busy) setOpen(false); }} onOk={() => form.submit()}>
      {error && <Alert showIcon type="error" message={error} />}
      <Form form={form} layout="vertical" disabled={busy} onFinish={async (values) => {
        if (busy) return;
        setBusy(true);
        setError('');
        try {
          const staff = await session.writeStaff<Staff>('', 'POST', {
            employee_no: values.employee_no.trim(), display_name: values.display_name.trim(),
          });
          setOpen(false);
          onCreated(staff);
        } catch (cause) {
          if (cause instanceof AdminRequestError && cause.status === 401) onExpired();
          else setError(operationError(cause));
        } finally {
          setBusy(false);
        }
      }}>
        <Form.Item label="姓名" name="display_name" rules={[{ required: true, whitespace: true, message: '请输入姓名' }]}>
          <Input maxLength={80} />
        </Form.Item>
        <Form.Item label="工号" name="employee_no" rules={[{ required: true, whitespace: true, message: '请输入工号' }]}>
          <Input maxLength={32} />
        </Form.Item>
      </Form>
    </Modal>
  </>;
}

export function StaffAccount({ initial, session, onExpired }: Props & { initial: Staff }) {
  const [staff, setStaff] = useState(initial);
  const [invite, setInvite] = useState<Invitation>();
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState('');
  const path = '/' + encodeURIComponent(staff.id);
  const canWrite = session.role === 'admin' && staff.role === 'employee';

  useEffect(() => {
    if (!invite) return;
    const controller = new AbortController();
    const expires = window.setTimeout(() => setInvite(undefined), Math.max(0, Date.parse(invite.expires_at) - Date.now()));
    let poll: number;
    async function check() {
      try {
        const fresh = await session.read<Staff>('/staff' + path, controller.signal);
        if (controller.signal.aborted) return;
        setStaff(fresh);
        if (fresh.wechat_bound || fresh.status !== 'active') {
          setInvite(undefined);
          return;
        }
      } catch (cause) {
        if (controller.signal.aborted) return;
        if (cause instanceof AdminRequestError && (cause.status === 401 || cause.status === 403)) {
          setError(operationError(cause));
          setInvite(undefined);
          return;
        }
      }
      poll = window.setTimeout(check, 4000);
    }
    poll = window.setTimeout(check, 4000);
    return () => {
      controller.abort();
      window.clearTimeout(poll);
      window.clearTimeout(expires);
    };
  }, [invite, session, path]);

  async function write(action: 'invitation' | 'status') {
    if (busy) return;
    setBusy(true);
    setError('');
    setInvite(undefined);
    try {
      if (action === 'invitation') {
        setInvite(await session.writeStaff<Invitation>(path + '/wechat-invitation', 'POST'));
      } else {
        setStaff(await session.writeStaff<Staff>(path, 'PATCH', { status: staff.status === 'active' ? 'disabled' : 'active' }));
        setConfirm(false);
      }
    } catch (cause) {
      if (cause instanceof AdminRequestError && cause.status === 401) onExpired();
      else {
        setConfirm(false);
        setError(operationError(cause));
      }
    } finally {
      setBusy(false);
    }
  }

  const active = staff.status === 'active';
  return <Card title="账号状态">
    <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
      {error && <Alert showIcon type="error" message={error} />}
      <Space wrap>
        <StatusTag>{active ? '在职' : '停用'}</StatusTag>
        <StatusTag>{staff.wechat_bound ? '微信已绑定' : '微信未绑定'}</StatusTag>
      </Space>
      {canWrite && <Space wrap>
        {active && !staff.wechat_bound && <Button type="primary" disabled={busy} onClick={() => write('invitation')}>
          {invite ? '重新生成绑定二维码' : '生成绑定二维码'}
        </Button>}
        <Button danger={active} disabled={busy} onClick={() => setConfirm(true)}>{active ? '停用员工' : '重新启用'}</Button>
      </Space>}
      {invite && <Space direction="vertical">
        <QRCode value={invite.qr_payload} />
        <span>请员工本人在门诊用小程序「扫描员工绑定二维码」。</span>
        <span>失效时间 {expiryFormat.format(new Date(invite.expires_at))}</span>
      </Space>}
    </Space>
    <ConfirmDialog open={confirm} title={active ? '确认停用员工' : '确认重新启用员工'} loading={busy}
      onCancel={() => { if (!busy) setConfirm(false); }} onConfirm={() => write('status')}>
      {active ? '停用后员工会话立即失效，同账号的会员身份继续有效。' : '员工须重新微信登录，原员工会话继续失效。'}
    </ConfirmDialog>
  </Card>;
}
