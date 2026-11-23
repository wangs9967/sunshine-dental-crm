import { lazy, Suspense, useEffect, useState } from 'react';
import type { MouseEvent } from 'react';
import { Alert, Avatar, ConfigProvider, Dropdown, Layout, Menu, Space } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { Brand } from './components/Brand';
import { NavigationIcon } from './components/NavigationIcon';
import { ConfirmDialog, ErrorState, LoadingState, PageContainer, PageHeader, StatusTag } from './components/page';
import { loginReturnPath, menu, relatedRoutes, resolveRoute, routePath } from './routes';
import { AdminLogin, DemoLogin } from './pages/Login';
import { demoEnabled, readDemoRole, roles, writeDemoRole } from './session';
import type { AdminRole, AdminSession } from './session';
import { theme } from './theme';
import './styles.css';

const WorkspacePage = lazy(() => import('./pages/WorkspacePage'));
const DirectoryPage = lazy(() => import('./pages/DirectoryPage'));
type Navigate = (path: string, event?: MouseEvent<HTMLAnchorElement>) => void;
export type { Navigate };

function AdminLayout({ role, path, navigate, onLogout, session, onExpired }: {
  role: AdminRole;
  path: string;
  navigate: Navigate;
  onLogout: () => Promise<void>;
  session?: AdminSession;
  onExpired: () => void;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
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
            {demoEnabled && <StatusTag>演示环境</StatusTag>}
            <Dropdown trigger={['click']} menu={{ items: [{ key: 'logout', label: '退出登录' }], onClick: () => {
              setLogoutError(false);
              setConfirmOpen(true);
            } }}>
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
                {route.entry.path === '/members' || route.entry.path === '/employees'
                  ? <DirectoryPage key={path} path={path} base={route.entry.path} session={session}
                      navigate={navigate} onExpired={onExpired} />
                  : <WorkspacePage key={path} title={title} dashboard={route.entry.path === '/dashboard'}
                      searchable={route.title === route.entry.title && route.entry.path !== '/settings'} navigate={navigate} />}
              </Suspense>
            ) : <ErrorState title="该页面不存在，请从左侧菜单选择页面。" />}
          </PageContainer>
        </main>
      </Layout>
      <ConfirmDialog open={confirmOpen} title="退出登录" loading={loggingOut}
        onCancel={() => { if (!loggingOut) setConfirmOpen(false); }}
        onConfirm={async () => {
          if (loggingOut) return;
          setLoggingOut(true);
          setLogoutError(false);
          try {
            await onLogout();
          } catch {
            setLogoutError(true);
          } finally {
            setLoggingOut(false);
          }
        }}>
        {logoutError ? <Alert showIcon type="error" message="退出失败，请重试。" /> : '退出后将返回登录页。'}
      </ConfirmDialog>
    </Layout>
  );
}

export default function App() {
  const [demoRole, setDemoRole] = useState(readDemoRole);
  const [session, setSession] = useState<AdminSession>();
  const [notice, setNotice] = useState('');
  const role = demoEnabled ? demoRole : session?.role;
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

  useEffect(() => {
    if (!session) return;
    let active = true;
    let timer: number;
    function schedule(current: AdminSession) {
      timer = window.setTimeout(async () => {
        try {
          await current.refresh();
          if (active) schedule(current);
        } catch {
          if (active) {
            setSession(undefined);
            setNotice('当前会话已结束，请重新登录。');
          }
        }
      }, current.refreshInMs);
    }
    schedule(session);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [session]);

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
      {role ? <AdminLayout role={role} path={path} navigate={navigate} session={session}
        onExpired={() => { setSession(undefined); setNotice('当前会话已结束，请重新登录。'); }} onLogout={async () => {
        if (session) await session.logout();
        writeDemoRole();
        setDemoRole(undefined);
        setSession(undefined);
        window.history.replaceState(null, '', '/login');
        setUrl('/login');
      }} /> : demoEnabled ? <DemoLogin onLogin={(selected) => {
        writeDemoRole(selected);
        setDemoRole(selected);
      }} /> : <AdminLogin notice={notice} onLogin={(authenticated) => {
        setNotice('');
        setSession(authenticated);
      }} />}
    </ConfigProvider>
  );
}
