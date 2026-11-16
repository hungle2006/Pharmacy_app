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
const taskIcons={'disease-predict':'M4 3h16v18H4z M8 8h8 M8 12h3 M14 12h2 M8 16h8','feature-price':'M4 3v18h17 M7 15l4-5 4 2 5-7 M7 18h1 M12 17h1 M17 15h1',overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',lookup:'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',pricing:'M3 18l5-5 4 2 8-10 M15 5h5v5',competition:'M4 21V9h5v12 M10 21V3h5v18 M16 21v-8h5v8',portfolio:'M3 7l9-4 9 4-9 4z M3 12l9 4 9-4 M3 17l9 4 9-4',quality:'M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6z M8 12l3 3 5-6',business:'M4 4h16v16H4z M8 8h8 M8 12h8 M8 16h5',workflow:'M4 3h6v6H4z M14 15h6v6h-6z M7 9v9h7 M10 6h7v9',reports:'M4 3h16v18H4z M8 16v-4 M12 16V7 M16 16v-6',eda:'M4 19V5 M4 19h17 M8 14l4-6 4 3 4-6',preparation:'M4 7h16 M7 3v8 M4 17h16 M16 13v8',modeling:'M3 17l5-7 5 4 7-10 M3 21h18','market-forecast':'M3 17l6-6 4 3 8-10 M16 4h5v5'};
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
