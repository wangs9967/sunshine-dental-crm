import { lazy, Suspense, useEffect, useState } from 'react';
import type { MouseEvent } from 'react';
import { Avatar, Button, ConfigProvider, Dropdown, Layout, Menu, Select, Space } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { Brand } from './components/Brand';
import { NavigationIcon } from './components/NavigationIcon';
import { ConfirmDialog, ErrorState, LoadingState, PageContainer, PageHeader, StatusTag } from './components/page';
import { loginReturnPath, menu, relatedRoutes, resolveRoute, routePath } from './routes';
import { readDemoRole, roles, writeDemoRole } from './session';
import type { DemoRole } from './session';
import { theme } from './theme';
import './styles.css';

const WorkspacePage = lazy(() => import('./pages/WorkspacePage'));
type Navigate = (path: string, event?: MouseEvent<HTMLAnchorElement>) => void;
export type { Navigate };

function Login({ onLogin }: { onLogin: (role: DemoRole) => void }) {
  const [role, setRole] = useState<DemoRole>('admin');
  return (
    <main className="login">
      <aside className="login-brand"><Brand login /></aside>
      <div className="login-card">
        <h1>登录管理后台</h1>
        <p>选择演示身份，进入工作台。</p>
        <form onSubmit={(event) => { event.preventDefault(); onLogin(role); }}>
          <label htmlFor="demo-role">演示身份</label>
          <Select id="demo-role" value={role} onChange={setRole} options={[
            { value: 'admin', label: '管理员' },
            { value: 'manager', label: '店长' },
          ]} />
          <Button type="primary" size="large" htmlType="submit" block>进入后台</Button>
        </form>
      </div>
    </main>
  );
}

function AdminLayout({ role, path, navigate, onLogout }: {
  role: DemoRole;
  path: string;
  navigate: Navigate;
  onLogout: () => void;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const route = resolveRoute(path);
  const groups = [...new Set(menu.map((item) => item.group))];
  const menuItems = groups.map((group) => ({
    type: 'group' as const,
    label: group,
    children: menu.filter((item) => item.group === group).map((item) => ({
      key: item.path,
      icon: <NavigationIcon name={item.icon} />,
      label: <a href={item.path} onClick={(event) => navigate(item.path, event)}>{item.title}</a>,
    })),
  }));
  const title = route?.title ?? '页面未找到';
  const secondary = route && relatedRoutes[routePath(path)];

  function link(url: string, label: string) {
    return <a href={url} onClick={(event) => navigate(url, event)}>{label}</a>;
  }

  const parents = route?.entry.path === '/dashboard' ? [{ title: '工作台' }] : [
    { title: link('/dashboard', '工作台') },
    ...(route ? [{ title: route.entry.group }] : []),
    ...(route && route.title !== route.entry.title ? [{ title: link(route.entry.path, route.entry.title) }] : []),
  ];

  return (
    <Layout className="admin-layout">
      <aside className="sidebar">
        <Brand />
        <nav aria-label="后台导航">
          <Menu mode="inline" items={menuItems} selectedKeys={route ? [route.entry.path] : []}
            onClick={({ key, domEvent }) => {
              if (domEvent.target instanceof Element && !domEvent.target.closest('a')) navigate(key);
            }} />
        </nav>
      </aside>
      <Layout>
        <header className="topbar">
          <span className="topbar-title">运营工作台</span>
          <div className="user-area">
            <StatusTag>演示环境</StatusTag>
            <Dropdown trigger={['click']} menu={{ items: [{ key: 'logout', label: '退出登录' }], onClick: () => setConfirmOpen(true) }}>
              <button className="user-button" type="button" aria-label={`${roles[role]}账户菜单`}>
                <Avatar size={32}>{roles[role].slice(0, 1)}</Avatar>
                <span>{roles[role]}</span><span aria-hidden="true" className="user-chevron">⌄</span>
              </button>
            </Dropdown>
          </div>
        </header>
        <main className="main-area">
          <PageHeader title={title} parents={parents} actions={secondary && (
            <Space wrap size={16}>
              {secondary.map(({ path: url, title: label }) => <span key={url}>{link(url, label)}</span>)}
            </Space>
          )} />
          <PageContainer>
            {route ? (
              <Suspense fallback={<LoadingState />}>
                <WorkspacePage key={path} title={title} dashboard={route.entry.path === '/dashboard'}
                  searchable={route.title === route.entry.title && route.entry.path !== '/settings'} navigate={navigate} />
              </Suspense>
            ) : <ErrorState title="该页面不存在，请从左侧菜单选择页面。" />}
          </PageContainer>
        </main>
      </Layout>
      <ConfirmDialog open={confirmOpen} title="退出登录" onCancel={() => setConfirmOpen(false)} onConfirm={onLogout}>
        退出后将返回登录页。
      </ConfirmDialog>
    </Layout>
  );
}

export default function App() {
  const [role, setRole] = useState(readDemoRole);
  function currentUrl() {
    if (typeof window === 'undefined') return '/login';
    const { pathname, search, hash } = window.location;
    return pathname + search + hash;
  }
  const [url, setUrl] = useState(currentUrl);
  const path = routePath(url);

  useEffect(() => {
    const onPopState = () => setUrl(currentUrl());
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    if (!role && path !== '/login') {
      const target = path === '/' ? '/login' : `/login?next=${encodeURIComponent(url)}`;
      window.history.replaceState(null, '', target);
      setUrl(target);
    } else if (role && (path === '/' || path === '/login')) {
      const target = loginReturnPath(new URLSearchParams(window.location.search).get('next'));
      window.history.replaceState(null, '', target);
      setUrl(target);
    }
  }, [path, role, url]);

  const navigate: Navigate = (url, event) => {
    if (event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
    }
    if (currentUrl() !== url) window.history.pushState(null, '', url);
    setUrl(url);
  };

  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      {role ? <AdminLayout role={role} path={path} navigate={navigate} onLogout={() => {
        writeDemoRole();
        setRole(undefined);
        window.history.replaceState(null, '', '/login');
        setUrl('/login');
      }} /> : <Login onLogin={(selected) => {
        writeDemoRole(selected);
        setRole(selected);
        const target = loginReturnPath(new URLSearchParams(window.location.search).get('next'));
        window.history.replaceState(null, '', target);
        setUrl(target);
      }} />}
    </ConfigProvider>
  );
}
