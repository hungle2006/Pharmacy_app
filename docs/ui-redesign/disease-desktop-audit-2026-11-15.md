# Pharmacy App — bố cục Dự đoán bệnh trên laptop (15/11/2026)

## Lỗi kiểm tra từ ảnh và mã nguồn
- Cột nhập liệu cao hơn phần kết quả; khung kết quả dùng `position: sticky` nên bị lệch trong quá trình cuộn.
- Thanh tìm kiếm chung không cần thiết tại task có form nhập triệu chứng riêng.
- Mô tả, bộ đếm, nút và thông báo cảnh báo xếp dài, tạo cảm giác mất cân đối.
- Kiểm tra form rỗng hiện tooltip trình duyệt che chữ bên dưới.

## Thay đổi
- Thêm `assets/disease-desktop.css` áp dụng riêng desktop, hai card cùng đỉnh và cao bằng nhau khi màn hình rộng từ 961px; bỏ sticky khung kết quả.
- Form textarea cao hợp lý, trợ giúp và bộ đếm nằm cùng một hàng với độ rộng tự thích ứng; nút và cảnh báo căn thẳng hàng.
- Giữ khu hướng dẫn và đánh giá mô hình dưới dạng mục mở rộng; không cắt bỏ thông tin chuyên môn.
- `novalidate` cho form triệu chứng để dùng cảnh báo nội tuyến đã có trong `predict()`, focus ô nhập khi dữ liệu dưới 5 hoặc quá 4.000 ký tự.
- Giữ nguyên toàn bộ mô hình, API, dữ liệu bệnh, hạn chế lâm sàng, Start 3D và CSS điện thoại.

## Kiểm chứng Chromium
- 1920×1080, 1552×877, 1440×900: không cuộn trang ở trạng thái ban đầu; hai cột cùng Y và cùng chiều cao.
- 1280×720, 1152×768, 1120×768, 1024×768: hai cột giữ đúng chiều rộng; khi nội dung dài hơn màn hình vẫn có cuộn.
- 960×800, 768×900: một cột để tránh chữ/nút bị ép.
- 390×844, 320×568: test điện thoại không thay đổi breakpoint desktop.
- 0 tràn ngang tài liệu và 0 pageerror ở các kích thước thử nghiệm.
- Kiểm tra form trống hiện thông báo trực tiếp và đưa focus về textarea, không bật tooltip che nội dung.
- `npm run check`: pass; `npm test`: 69/69 pass.

Lưu ý: môi trường thử nghiệm là local Chromium, chưa xác minh dữ liệu suy luận live của API hoặc trình duyệt Safari vật lý.
