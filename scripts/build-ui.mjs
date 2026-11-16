import { readFile, writeFile } from 'node:fs/promises';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { build } from 'esbuild';
import { Button } from '@astryxdesign/core/Button';
import { Link } from '@astryxdesign/core/Link';
import { Heading } from '@astryxdesign/core/Heading';
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

const taskGroups=[
    {id:'market',label:'Thị trường',views:['overview','pricing','competition','portfolio','market-forecast']},
    {id:'lookup',label:'Tra cứu & dự đoán',views:['lookup','disease-predict','feature-price']},
    {id:'data',label:'Khám phá dữ liệu',views:['quality','reports','eda','preparation']},
    {id:'research',label:'Nghiên cứu',views:['business','workflow','modeling']}
  ];
const navLabels={overview:'Tổng quan',lookup:'Tra cứu thuốc','disease-predict':'Dự đoán bệnh','market-forecast':'Dự báo thị trường','feature-price':'Dự đoán giá',business:'Đề tài nghiên cứu',workflow:'Nguồn & tích hợp',reports:'Thống kê dữ liệu',modeling:'Mô hình & đánh giá'};
const taskIcons={
  overview:'M4 4h6v7H4z M14 4h6v4h-6z M4 15h6v5H4z M14 12h6v8h-6z',
  pricing:'M3 12V5a2 2 0 0 1 2-2h7l9 9-9 9z M7.5 7.5h.01',
  competition:'M4 20h16M5 16v-4m7 4V4m7 12V8',
  portfolio:'m12 3 9 5-9 5-9-5z M3 12l9 5 9-5M3 16l9 5 9-5',
  'market-forecast':'M4 19V5m0 14h16M7 14l4-4 4 2 5-6m-4 0h4v4',
  lookup:'M21 21l-5-5m2-6a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  'disease-predict':'M5 4h14v16H5z M12 8v8m-4-4h8',
  'feature-price':'M5 3h14v18H5z M8 7h8m-8 5h1m6 0h1m-8 4h1m6 0h1',
  quality:'m12 3 7 3v5c0 4-2.7 7.4-7 10-4.3-2.6-7-6-7-10V6z M9 12l2 2 4-4',
  reports:'M6 3h8l4 4v14H6z M14 3v5h4M9 12h6m-6 4h6',
  eda:'M4 20V4m0 16h16M8 14h.01M11 10h.01M15 13h.01M18 7h.01',
  preparation:'M4 6h16M4 12h16M4 18h16M8 4v4m8 2v4m-6 2v4',
  business:'M9 5H5v16h14V5h-4M9 3h6v4H9z M8 12h8m-8 4h6',
  workflow:'M4 3h6v6H4z M14 15h6v6h-6z M7 9v9h7 M10 6h7v9',
  modeling:'m12 3 9 5v8l-9 5-9-5V8z M3 8l9 5 9-5m-9 5v8'
};
const taskTitles={
  "overview": "Tổng quan thị trường",
  "lookup": "Tra cứu thuốc",
  "disease-predict": "Dự đoán bệnh từ mô tả",
  "market-forecast": "Dự báo thị trường thuốc",
  "feature-price": "Dự đoán giá theo đặc trưng",
  "pricing": "Phân tích giá thuốc",
  "competition": "Phân tích cạnh tranh",
  "portfolio": "Danh mục sản phẩm",
  "quality": "Chất lượng dữ liệu",
  "business": "Đề tài & mục tiêu nghiên cứu",
  "workflow": "Nguồn dữ liệu & tích hợp",
  "reports": "Phân tích thống kê dữ liệu",
  "eda": "EDA dữ liệu",
  "preparation": "Làm sạch dữ liệu",
  "modeling": "Mô hình hóa & đánh giá"
};

function taskButton(id,label,props) {
  return h(Button, {
    key:id,label,variant:'ghost',width:'100%',
    icon:icon(taskIcons[id]), ...props,
  });
}

function taskNavigation() {
  return taskGroups.map(({id,label,views})=>h('section',{
    key:id,className:'task-nav-group','data-group':id,'aria-labelledby':'tasks-'+id,
  },
    h(Heading,{level:2,id:'tasks-'+id,className:'nav-caption'},label),
    h('div',{className:'task-nav-tiles'},views.map(view=>taskButton(view,navLabels[view]||taskTitles[view],{
      className:'nav-button','data-view':view,'aria-label':taskTitles[view],
    })))));
}

function mobileNavigation() {
  return [
    taskButton('overview','Tổng quan',{'data-view':'overview'}),
    taskButton('lookup','Tra cứu',{'data-view':'lookup'}),
    taskButton('market-forecast','Dự báo',{'data-view':'market-forecast'}),
    taskButton('portfolio','Tác vụ',{'data-mobile-menu':'','aria-label':'Mở tất cả tác vụ'}),
  ];
}

function marketActions() {
  return h(Button,{label:'Cập nhật báo cáo',variant:'secondary',className:'market-refresh',
    'data-market-reload':'',icon:icon('M20 7v5h-5M4.6 10a8 8 0 0 1 13.9-4l1.5 1M4 17v-5h5M19.4 14a8 8 0 0 1-13.9 4L4 17')});
}

const indexPath = new URL('../index.html', import.meta.url);
let html = await readFile(indexPath, 'utf8');
for (const [name, render] of [['start-guide', guideLinks], ['overview-shortcuts', workspaceShortcuts],
    ['task-navigation', taskNavigation], ['mobile-navigation', mobileNavigation], ['market-actions', marketActions],
    ['workspace-title', () => h(Heading,{level:1,id:'page-title',tabIndex:-1},'Tổng quan thị trường')],
    ['workspace-export', () => h(Button,{id:'export',label:'Xuất CSV',variant:'secondary',className:'button secondary'})],
    ['lookup-submit', () => h(Button,{label:'Tìm thuốc',variant:'primary',type:'submit',className:'lookup-submit','aria-label':'Tìm thuốc',
      icon:icon('M5 12h14m-6-6 6 6-6 6')})]]) {
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
