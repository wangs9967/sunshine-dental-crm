import { useState } from 'react';
import { Alert, Button, Input, Select } from 'antd';
import { Brand } from '../components/Brand';
import { AdminSession, loginErrorMessage } from '../session';
import type { AdminRole } from '../session';

function LoginLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="login">
      <aside className="login-brand"><Brand login /></aside>
      <div className="login-card">{children}</div>
    </main>
  );
}

export function DemoLogin({ onLogin }: { onLogin: (role: AdminRole) => void }) {
  const [role, setRole] = useState<AdminRole>('admin');
  return (
    <LoginLayout>
      <h1>管理后台演示</h1>
      <p>选择演示身份，进入工作台。</p>
      <form onSubmit={(event) => { event.preventDefault(); onLogin(role); }}>
        <label htmlFor="demo-role">演示身份</label>
        <Select id="demo-role" value={role} onChange={setRole} options={[
          { value: 'admin', label: '管理员' },
          { value: 'manager', label: '店长' },
        ]} />
        <Button type="primary" size="large" htmlType="submit" block>进入演示</Button>
      </form>
    </LoginLayout>
  );
}

export function AdminLogin({ onLogin, notice }: { onLogin: (session: AdminSession) => void; notice: string }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function submit() {
    if (submitting) return;
    setSubmitting(true);
    setError('');
    try {
      onLogin(await AdminSession.login(username, password));
    } catch (cause) {
      setError(loginErrorMessage(cause));
    } finally {
      setPassword('');
      setSubmitting(false);
    }
  }

  return (
    <LoginLayout>
      <h1>登录管理后台</h1>
      <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        {(error || notice) && <Alert showIcon type={error ? 'error' : 'info'} message={error || notice} />}
        <label htmlFor="username">用户名</label>
        <Input id="username" autoComplete="username" required maxLength={64}
          value={username} onChange={(event) => setUsername(event.target.value)} />
        <label htmlFor="password">密码</label>
        <Input.Password id="password" autoComplete="current-password" required maxLength={256}
          value={password} onChange={(event) => setPassword(event.target.value)} />
        <Button type="primary" size="large" htmlType="submit" loading={submitting} block>登录</Button>
      </form>
    </LoginLayout>
  );
}
