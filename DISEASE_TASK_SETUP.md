# Task: Dự đoán bệnh từ mô tả

Mở `/?view=disease-predict`. Task mới nằm trong dashboard Pharmacy, giữ nguyên trang Start 3D, Logout và các task hiện tại.

## Luồng người dùng

1. Nhập mô tả Việt / Anh (5–4.000 ký tự). Không nhập thông tin nhận dạng cá nhân.
2. API Vercel gọi Render bằng khóa ở phía máy chủ. Render gọi Modal predict, đọc checkpoint đã promote trên Hugging Face.
3. Hiển thị tối đa 5 nhãn cùng điểm softmax, thang cố định 0–100%. Điểm chưa hiệu chỉnh, không phải xác suất mắc bệnh.
4. Chọn nhãn để tìm các ứng viên tên bệnh trong danh mục ICD. Người dùng tự đối chiếu, chọn mã phù hợp; không tự gán ICD bằng độ giống tên.
5. Đọc bằng chứng thuốc qua API disease-lookup hiện có: ICD-10-CM khớp đúng → MEDI → RxNorm → DAV qua SCD được chấp nhận. Không tạo thuốc, liều dùng hoặc chỉ định nếu thiếu dữ liệu.

Tab **Mô hình hóa & đánh giá → Nhận diện nhãn bệnh · Transformer** hiển thị validation / test của checkpoint được promote: Macro-F1, Top-1, balanced accuracy, Top-3, Top-5; kèm phiên bản model, dữ liệu và benchmark. Không dùng số mô phỏng khi chưa train.

## Cấu hình trước khi sử dụng

Các token training của GitHub/Modal và khóa API của website là những cấu hình riêng.

| Nơi cấu hình | Tên biến | Giá trị / mục đích |
| --- | --- | --- |
| GitHub Actions Secrets | MODAL_TOKEN_ID, MODAL_TOKEN_SECRET | Kích hoạt deploy / train Modal |
| Modal Secret `disease-training` trong môi trường main | HF_TOKEN | Đọc dataset và ghi model Hugging Face |
| Render service chạy `disease_monthly_pipeline/server.py` | API_KEY | Khóa tự tạo của API bệnh |
| Render service | MODAL_TOKEN_ID, MODAL_TOKEN_SECRET | Gọi các function `predict` / `report` |
| Render service | INFERENCE_BACKEND | `modal` |
| Render service | MODAL_APP_NAME | `disease-monthly-pipeline` |
| Vercel project Pharmacy · Production (và Preview nếu cần thử) | DISEASE_API_URL | URL HTTPS gốc của Render service bệnh, dạng `https://<service>.onrender.com` |
| Vercel project Pharmacy · cùng environment | DISEASE_API_KEY | Cùng giá trị API_KEY của Render service bệnh |
| Vercel · giữ nguyên | DATABASE_URL | Neon Gold phục vụ ICD / MEDI / RxNorm / DAV |

Không đặt khóa trong JavaScript, URL, biến public, mã nguồn hoặc chat. `ML_PRICE_API_URL` / `ML_API_KEY` tiếp tục phục vụ giá thuốc; không thay bằng dịch vụ bệnh.

## Thứ tự kích hoạt

1. Merge PR chứa pipeline và task vào main để workflow theo tháng có hiệu lực.
2. Cấu hình GitHub Secrets và Modal Secret như trên, chạy Actions **Disease model - monthly refresh**. GitHub báo gửi job thành công chưa có nghĩa train xong; theo dõi Modal cho đến khi checkpoint được promote. Model repo cần có `deployment.json` và thư mục `versions/<run>/best_model`.
3. Deploy Render bằng Blueprint riêng `disease_monthly_pipeline/render.yaml`, chọn workspace và đặt các biến. Không sửa hoặc thay thế dịch vụ giá thuốc hiện có. Nếu service bệnh đã chạy, deploy lại commit chứa endpoint `/report`.
4. Đặt 2 biến DISEASE_API_URL / DISEASE_API_KEY trên Vercel và redeploy commit mới. Biến chỉ trong GitHub hoặc Modal không tự truyền sang Vercel/Render.
5. Mở task, thử mô tả, kiểm tra phiên bản model và danh sách ICD; chọn mã để kiểm tra thuốc liên quan. Mở tab Transformer để xem chỉ số checkpoint thực tế.

## Kiểm tra khi chưa có kết quả

- `DISEASE_API_NOT_CONFIGURED`: thiếu/sai URL HTTPS Render hoặc khóa riêng trong Vercel; redeploy sau khi lưu biến.
- `DISEASE_SERVICE_UNAVAILABLE`: kiểm tra riêng log Render, Modal và checkpoint đã promote; API không trả chi tiết có thể chứa thông tin nội bộ cho trình duyệt.
- `MODEL_TIMEOUT`: lần suy luận đầu có thể khởi động lâu; thử lại. Vercel dừng chờ sau 50 giây; việc dừng chờ ở trình duyệt không bảo đảm hủy lời gọi Modal đã gửi.
- Báo cáo `not_trained`: chưa có pointer checkpoint; không dùng model giả làm dự phòng.
- Không có ICD / thuốc: chưa có bằng chứng đủ điều kiện trong Gold; không đồng nghĩa không có bệnh hay không có phương pháp điều trị.

## Giới hạn nghiên cứu

Mô hình phân loại tập nhãn đóng, dữ liệu mô tả tổng hợp / theo mẫu; test cùng nguồn không thay thế kiểm định lâm sàng ngoài nguồn. Chưa có hiệu chỉnh xác suất hay phát hiện ngoài phân phối đã kiểm định. Quan hệ thuốc–bệnh MEDI và liên kết DAV không xác nhận chỉ định, chống chỉ định, liều hoặc độ phù hợp với người dùng. Người dùng cần đánh giá của nhân viên y tế; giao diện chỉ hỗ trợ đọc dữ liệu.

Giao diện giữ mô tả trong bộ nhớ trang khi đổi task, có nút Xóa; không ghi localStorage. API không chủ động ghi văn bản triệu chứng vào log. Cần rà soát chính sách log và quyền truy cập hạ tầng trước khi vận hành với thông tin người bệnh thực tế. Endpoint công khai có thể phát sinh chi phí suy luận; khi mở cho số lượng người dùng lớn, cấu hình kiểm soát truy cập và giới hạn tần suất phù hợp trên hạ tầng.
