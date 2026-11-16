import { readFile, writeFile } from 'node:fs/promises';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { build } from 'esbuild';
import { Button } from '@astryxdesign/core/Button';
import { Link } from '@astryxdesign/core/Link';
import { Text } from '@astryxdesign/core/Text';

const icon = path => h('svg', {
  className: 'pb-control-icon', viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round',
  strokeLinejoin: 'round', 'aria-hidden': true,
}, h('path', { d: path }));

const entries = [
  ['overview', 'Mở tổng quan', 'Xem chỉ số thị trường. Lọc theo hoạt chất, quốc gia, loại giá hoặc đơn vị.'],
  ['lookup', 'Tra cứu thuốc', 'Tìm theo tên, hoạt chất hoặc số đăng ký. Chạm kết quả để mở hồ sơ.'],
  ['market-forecast', 'Đọc dự báo', 'Chọn kỳ 3, 6 hoặc 12 tháng và đối chiếu với dữ liệu lịch sử.'],
];

function guideLinks() {
  return entries.map(([view, label, description], index) => h('li', { key: view },
    h(Link, { href: '/?view=' + view, color: 'inherit', className: 'guide-card' },
      h(Text, { 'aria-hidden': true, className: 'guide-step' }, String(index + 1).padStart(2, '0')),
      h('strong', null, label, icon('M5 12h14m-6-6 6 6-6 6')),
      h('small', null, description))));
}

function workspaceShortcuts() {
  return [
    ['lookup', 'Tra cứu thuốc', 'M16 16l5 5m-3-11a7 7 0 1 1-14 0 7 7 0 0 1 14 0'],
    ['market-forecast', 'Dự báo', 'm3 17 6-6 4 3 8-10m-5 0h5v5'],
    ['reports', 'Thống kê', 'M5 3h14v18H5z M8 16v-3m4 3V8m4 8v-5'],
  ].map(([view, label, path]) => h(Button, {
    key: view, label, variant: 'secondary', size: 'lg', width: '100%', 'data-view': view,
    icon: h(Text, { 'aria-hidden': true, className: 'shortcut-icon' }, icon(path)),
  }));
}

const indexPath = new URL('../index.html', import.meta.url);
let html = await readFile(indexPath, 'utf8');
for (const [name, render] of [['start-guide', guideLinks], ['overview-shortcuts', workspaceShortcuts]]) {
  const start = '<!-- astryx:' + name + ' -->';
  const end = '<!-- /astryx:' + name + ' -->';
  const before = html.indexOf(start) + start.length;
  const after = html.indexOf(end, before);
  if (before < start.length || after < 0) throw new Error('Missing Astryx markers: ' + name);
  html = html.slice(0, before) + '\n' + renderToStaticMarkup(render()) + '\n' + html.slice(after);
}

await build({
  stdin: {
    contents: "@import '@astryxdesign/core/reset.css'; @import '@astryxdesign/core/astryx.css'; @import '@astryxdesign/theme-neutral/theme.css';",
    loader: 'css',
    resolveDir: process.cwd(),
  },
  bundle: true,
  minify: true,
  outfile: 'assets/astryx-ui.css',
});
await writeFile(indexPath, html);
