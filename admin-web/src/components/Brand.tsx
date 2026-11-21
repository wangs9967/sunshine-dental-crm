export function Brand({ login = false }: { login?: boolean }) {
  return (
    <div className="brand">
      <div aria-hidden="true" className="brand-mark" />
      <div><strong>阳光口腔</strong><span>{login ? '会员运营管理系统' : '管理后台'}</span></div>
    </div>
  );
}
