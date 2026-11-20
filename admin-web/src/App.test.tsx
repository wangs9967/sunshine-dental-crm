import { renderToStaticMarkup } from 'react-dom/server';
import { expect, test } from 'vitest';
import App from './App';

test('renders the admin shell title', () => {
  expect(renderToStaticMarkup(<App />)).toContain('阳光口腔管理后台');
});
