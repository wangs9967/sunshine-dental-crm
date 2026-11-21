import { Alert, Breadcrumb, Button, Card, Empty, Input, Modal, Space, Spin, Tag, Typography } from 'antd';
import type { FormEvent, ReactNode } from 'react';

export function PageHeader({ title, parents, actions }: {
  title: string;
  parents: { title: ReactNode }[];
  actions?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <Breadcrumb items={[...parents, { title }]} />
      <div className="page-title-row">
        <Typography.Title level={1}>{title}</Typography.Title>
        {actions}
      </div>
    </header>
  );
}

export function PageContainer({ children }: { children: ReactNode }) {
  return <section className="page-content">{children}</section>;
}

export function SearchPanel({ value, onChange, onSearch, onReset }: {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  onReset: () => void;
}) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch();
  }
  return (
    <Card className="search-panel">
      <form onSubmit={submit}>
        <Space wrap size={12}>
          <label htmlFor="page-keyword">关键词</label>
          <Input id="page-keyword" value={value} onChange={(event) => onChange(event.target.value)} placeholder="输入关键词" />
          <Button type="primary" htmlType="submit">查询</Button>
          <Button onClick={onReset}>重置</Button>
        </Space>
      </form>
    </Card>
  );
}

export function StatusTag({ children }: { children: ReactNode }) {
  return <Tag color="blue" className="session-tag">{children}</Tag>;
}

export function EmptyState({ description = '暂无数据' }: { description?: string }) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />;
}

export function LoadingState() {
  return <div className="loading-state" role="status"><Spin /> 正在加载页面</div>;
}

export function ErrorState({ title }: { title: string }) {
  return <Alert type="error" showIcon message={title} />;
}

export function ConfirmDialog({ open, onConfirm, onCancel, title, children }: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <Modal open={open} onOk={onConfirm} onCancel={onCancel} title={title} okText="确认" cancelText="取消">
      {children}
    </Modal>
  );
}
