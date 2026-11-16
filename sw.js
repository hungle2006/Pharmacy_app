/* Let the server own all data requests. Only navigation receives an offline fallback. */
self.addEventListener('fetch', event => {
  if (event.request.mode !== 'navigate' || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(fetch(event.request).catch(() => new Response(
    '<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PharmaBiz · Đang ngoại tuyến</title><body style="background:#1b1536;color:#fff;font:1rem/1.6 system-ui;padding:2rem"><main><h1>PharmaBiz đang ngoại tuyến</h1><p>Kết nối Internet để mở ứng dụng và truy cập dữ liệu mới nhất.</p><a style="color:#ddf49c" href="/">Thử lại</a></main></body></html>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  )));
});
