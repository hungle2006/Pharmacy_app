# Ước tính giá kê khai từ đặc trưng thuốc

Task `?view=feature-price` bổ sung hồi quy giá theo cấu hình, bên cạnh task dự báo biến động toàn thị trường 3/6/12 tháng.

## Đầu vào và mục tiêu

- Sáu đặc trưng phân loại: hoạt chất, hàm lượng, dạng bào chế, nhà sản xuất, quốc gia và quy cách đóng gói.
- Mỗi cặp **loại giá × đơn vị nguồn** có mô hình riêng; không lấy mô hình viên để dự đoán lọ hoặc ống.
- Mục tiêu là giá kê khai VND dương đã quan sát trong snapshot. Kết quả không phải giá bán lẻ hiện tại hoặc dự báo giá tại ngày tương lai.
- Tên thuốc, giá thật, số đăng ký, ID và mã mapping không là feature. Số đăng ký chỉ dùng để chống trùng thuốc giữa các tập.

## Thiết kế kiểm định

1. SELECT trực tiếp Gold `dav_product JOIN price_record`; không thay đổi DB.
2. Loại giá không hữu hạn, không dương, ngày thiếu/tương lai và thiếu hoạt chất. Chuẩn hóa Unicode NFC, chữ thường và khoảng trắng; không tự gộp ngữ nghĩa hoặc quy đổi liều.
3. Trong mỗi loại giá/đơn vị, giữ giá có ngày gần nhất theo số đăng ký; hồ sơ thiếu số đăng ký dùng ID DAV. Nếu cùng ngày, ưu tiên Silver.
4. Chia theo ngày thành train/validation/calibration/test, mục tiêu 60/15/10/15%. Không cắt một ngày sang hai tập; số đăng ký không trùng giữa các tập. Cần ít nhất 500 sản phẩm, 200 train và 40 ở mỗi tập còn lại.
5. Ba CatBoost: RMSE trên log1p giá, MAE trên log1p giá, MAE trên giá VND. Depth 6, tối đa 650 iterations, early stopping 55, seed 42.
6. Baseline chỉ học từ train: trung vị hoạt chất+hàm lượng+dạng, lùi về hoạt chất+dạng, hoạt chất rồi trung vị chung. Chọn ứng viên và tỷ trọng CatBoost 0/25/50/75/100% bằng MAE validation. Không chọn bằng test.
7. Calibration riêng lấy phân vị có hiệu chỉnh cỡ mẫu của sai số tuyệt đối trong log1p, tạo khoảng danh nghĩa 90%. Đo độ bao phủ thật trên test; không khẳng định luôn đạt 90% khi dữ liệu dịch chuyển theo thời gian.
8. Test đo MAE, RMSE, Median AE, R², RMSLE, WAPE, Median APE và tỷ lệ trong ±20%/±50%. Bootstrap 600 lần theo các hồ sơ số đăng ký độc lập để ước lượng khoảng 95% của mức giảm MAE.
9. Nhãn `approved` chỉ có nghĩa MAE giảm ít nhất 1% so baseline và cận dưới bootstrap lớn hơn 0. Nó không xác nhận mô hình đủ chính xác cho mọi thuốc. Các kết quả còn lại hiển thị nhãn thử nghiệm. Không refit sau khi đo test.

## Kết quả thực nghiệm đầu tiên

Phiên bản **20261029T055900Z**, đọc **51.246 quan sát nguồn**, có **181 cặp loại giá/đơn vị**. Đánh giá được **15 nhóm**, trong đó **5 nhóm** vượt mốc so sánh baseline. 166 nhóm chưa đủ dữ liệu vẫn được liệt kê, không tạo số liệu thay thế.

Ví dụ **KK trong nước / viên**: 8.294 sản phẩm sau xử lý, test 1.252 hồ sơ trong 2025-10-08 đến 2025-11-24. MAE 6.954,25 VND/viên so baseline 7.349,98, giảm 5,384%. R² -0,00789; chỉ 21,49% nằm trong ±20% giá thật. Vì vậy kết quả là khả thi ở mức thử nghiệm và so baseline, chưa chứng minh độ chính xác cao. Chỉ 26,68% thuốc test có hoạt chất đã có trong train.

Dashboard lấy kết quả từ báo cáo đang chạy, không hardcode những con số này. Gợi ý đầu vào lấy từ train; ví dụ đối chiếu lấy từ test và ghi rõ giá giữ riêng.

## Phục vụ và cập nhật

- GitHub Actions `Train Feature Price Estimator` chạy kiểm thử, huấn luyện trên Gold, lưu artifact báo cáo 30 ngày và đăng bundle vào private R2 `ml/feature-price/versions/<version>/…`. Chỉ đổi con trỏ `ml/feature-price/latest.json` sau khi upload đủ file.
- Không thay con trỏ hoặc artifact của mô hình thị trường.
- Render: `GET /feature-price/report`; `POST /feature-price/predict` dùng `X-API-Key` hiện có.
- Vercel: `GET /api/feature-price` lấy báo cáo; `POST /api/feature-price` kiểm tra input rồi proxy. Khóa chỉ ở phía server. Endpoint cũ `/api/forecast-price` vẫn ngừng hoạt động vì thuộc dự báo tương lai từng thuốc trước đây.
- Cache tối đa ba bundle; kiểm tra version, schema, segment và feature trước khi nạp mô hình. Không log các đặc trưng người dùng nhập.
- Hoạt chất ngoài từ vựng train bị từ chối. Các trường khác chưa từng xuất hiện được cảnh báo; ô trống được chuẩn hóa `UNKNOWN`. Giá trị ước tính luôn kèm trạng thái, sai số test, số mẫu, khoảng hiệu chỉnh, độ bao phủ thực tế và version.
- Mục **Mô hình hóa & đánh giá** có hai phần riêng: hồi quy giá theo đặc trưng và dự báo biến động thị trường. Giữ thuật toán, kết quả và cách đánh giá tương ứng từng bài toán.
