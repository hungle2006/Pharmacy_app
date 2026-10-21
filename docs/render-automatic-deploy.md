# Tự động triển khai Render ML API từ GitHub Actions

GitHub workflow [Deploy PharmaBiz ML API to Render](../.github/workflows/deploy-render-ml.yml)
đợi workflow **Train Pharmacy Price Model** hoàn tất **thành công** trên `main`
sau một lần push mã ML. Sau đó GitHub gọi **Render Deploy Hook** để tự
triển khai service `pharmabiz-price-ml`. Workflow không chạy với pull request
hoặc nhánh không phải `main`.

## Thiết lập một lần

1. Trên Render, mở service `pharmabiz-price-ml`, chọn **Settings** và tìm
   **Deploy Hook**. Sao chép URL bí mật của hook. *Không commit URL, không gửi
   ảnh màn hình chứa URL đó.*
2. Trên GitHub, mở
   `https://github.com/hungle2006/Pharmacy_app/settings/secrets/actions`.
   Chọn **New repository secret**, đặt tên chính xác
   `RENDER_DEPLOY_HOOK_URL` và dán URL Deploy Hook vào giá trị.
3. Trên GitHub **Actions**, mở **Deploy PharmaBiz ML API to Render**,
   chọn **Run workflow** trên nhánh `main` để kiểm thử lần đầu.
4. Kiểm tra **Render > Deploys** và xác nhận trạng thái **Live**.

Sau khi thiết lập, thao tác push thay đổi trong `ml_price/**` hoặc
`.github/workflows/train-price-model.yml` lên `main` sẽ kích hoạt
workflow train; nếu train + kiểm thử thành công, workflow deploy gọi Render.
Không cần bấm **Manual Deploy**.

**Lưu ý:** đây là một cơ chế dự phòng cho tích hợp Git auto-deploy của Render.
Nếu Render's **Auto-Deploy: On Commit** hoạt động trở lại, nó có thể tạo thêm
một lượt deploy khi GitHub Actions gọi hook. Sau khi kiểm tra GitHub workflow
hoạt động ổn định, có thể chuyển Auto-Deploy của Render sang **Off** để
chỉ GitHub Actions quyết định khi nào deploy (vẫn giữ repo và branch `main`).
Các bản cập nhật dữ liệu giá / R2 không thay đổi mã nguồn thường không yêu cầu
redeploy Render, vì API tự làm mới danh mục model từ R2 định kỳ.

Đọc thêm: https://render.com/docs/deploy-hooks
