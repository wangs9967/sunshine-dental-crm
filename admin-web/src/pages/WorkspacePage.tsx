import { Card } from 'antd';
import { useState } from 'react';
import { EmptyState, SearchPanel } from '../components/page';
import { menu } from '../routes';
import { NavigationIcon } from '../components/NavigationIcon';
import type { Navigate } from '../App';

export default function WorkspacePage({ title, dashboard, searchable, navigate }: {
  title: string;
  dashboard: boolean;
  searchable: boolean;
  navigate: Navigate;
}) {
  const [keyword, setKeyword] = useState('');
  const [query, setQuery] = useState('');

  if (dashboard) {
    const shortcuts = menu.filter(({ path }) => path === '/members' || path === '/followups' || path === '/mall/orders');
    return (
      <>
        <Card className="shortcut-card" title="常用入口">
          <div className="shortcut-grid">
            {shortcuts.map(({ path, title, icon }) => (
              <a key={path} className="shortcut" href={path} onClick={(event) => navigate(path, event)}>
                <span className="shortcut-icon"><NavigationIcon name={icon} /></span>
                <strong>{title}</strong><span aria-hidden="true" className="shortcut-arrow">›</span>
              </a>
            ))}
          </div>
        </Card>
        <Card className="placeholder-card" title="运营概况">
          <EmptyState description="暂无运营数据" />
        </Card>
      </>
    );
  }

  return (
    <>
      {searchable && <SearchPanel value={keyword} onChange={setKeyword} onSearch={() => setQuery(keyword.trim())}
        onReset={() => { setKeyword(''); setQuery(''); }} />}
      <Card className="placeholder-card" title={title}>
        <EmptyState description={query ? '没有符合条件的记录' : '暂无数据'} />
      </Card>
    </>
  );
}
