const paths: Record<string, string> = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  members: 'M4 20v-2a4 4 0 0 1 4-4h5a4 4 0 0 1 4 4v2 M14 5a4 4 0 1 1-7 3 4 4 0 0 1 7-3 M21 20v-2a4 4 0 0 0-3-4',
  staff: 'M4 7h16v13H4z M9 7V4h6v3 M4 12h16 M10 12v2h4v-2',
  assignment: 'M4 8h15m-4-4 4 4-4 4 M20 16H5m4-4-4 4 4 4',
  followup: 'M4 4h16v12H9l-5 4z M8 8h8m-8 4h5',
  points: 'm12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',
  product: 'm3 7 9-4 9 4v10l-9 4-9-4z M3 7l9 4 9-4 M12 11v10',
  orders: 'M6 3h12v18l-3-2-3 2-3-2-3 2z M9 8h6m-6 4h6',
  verify: 'M3 8V3h5m8 0h5v5m0 8v5h-5m-8 0H3v-5m5-4 3 3 5-6',
  settings: 'M4 6h16M4 12h16M4 18h16 M8 4v4m8 2v4m-5 2v4',
  roles: 'M12 3 4 6v6c0 4 4 7 8 9 4-2 8-5 8-9V6z M9 12l2 2 4-4',
  audit: 'M5 3h10l4 4v14H5z M9 10h6m-6 4h6m-6 4h4',
};

export function NavigationIcon({ name }: { name: string }) {
  return (
    <svg aria-hidden="true" className="navigation-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name]} />
    </svg>
  );
}
