# PharmaBiz · DAV market-wide price outlook

**Thay thế mô hình dự báo giá từng thuốc bằng dashboard xu hướng toàn thị trường.**

## Dữ liệu và phạm vi

- Nguồn thực: Neon Gold `dav_product` JOIN `price_record` (chỉ truy vấn SELECT).
- Giá chỉ được so sánh giữa những lần kê khai của **cùng số đăng ký, cùng loại giá, cùng đơn vị**. Không cộng/so sánh giá tuyệt đối giữa viên, lọ, ống hay hộp.
- Ghép các cặp ngày gốc và ngày kê khai tiếp theo cách nhau gần 3, 6, 12 tháng (các cửa sổ: 91±35, 183±50, 365±50 ngày). Không tự điền giá ở ngày không kê khai.
- Dữ liệu không được cân theo doanh số. Nhiều loại thuốc thiếu lịch sử giá, nên đây là chỉ số **trên tập thuốc có giá kê khai lặp lại**, không phải chỉ số giá của toàn bộ ngành dược.
- Thống kê mô tả: trung vị và trung bình biến động %, phân vị P10–P90, tỷ trọng tăng hơn 1%, giảm hơn 1%, gần như giữ nguyên; biểu đồ theo năm. Mỗi số đăng ký có trọng số ngang nhau trong các thẻ thống kê.

## Phương pháp kiểm định dự báo chung

`ml_price/market_forecast.py` tạo giá trị thay đổi theo **log của tỷ số giá tương lai/giá gốc**. Tập train/validation/test được tách theo thời gian; nhãn cuối train kết thúc trước validation, nhãn cuối validation kết thúc trước test.

- Baseline: **giá không thay đổi**.
- Mô hình thống kê chung: log tỷ lệ biến động đã làm bền vững với ngoại lệ trong quá khứ, được co trọng số (shrinkage) chọn trên validation.
- Kiểm định test riêng cho từng thời hạn: sai số tuyệt đối trong thang log cải thiện ít nhất 1% so với baseline và số quan sát tối thiểu.
- Nếu không đạt, `forecast_change_pct` bắt buộc là `null`. Dashboard chỉ hiển thị các tỷ lệ **đã quan sát trong lịch sử**, không tự gọi đó là dự báo tương lai.
- Với một nhóm thuốc cụ thể, xu hướng thị trường không được coi là dự báo cho riêng thuốc đó.

## Pipeline tự động

GitHub workflow [Train Pharmacy Price Model](https://github.com/hungle2006/Pharmacy_app/actions/workflows/train-price-model.yml) giữ nguyên tên để workflow triển khai Render hoạt động:

1. Kiểm thử Python và JS.
2. Đọc Neon Gold và tạo báo cáo `models/market/report.json` với 3 thời hạn.
3. Luôn lưu artifact để kiểm tra.
4. Khi chạy trên `main`, đăng báo cáo phiên bản mới vào private R2 `ml/market/trends/versions/<version>/report.json`, sau đó cập nhật con trỏ `ml/market/trends/latest.json`.
5. GitHub Actions tự gọi Render Deploy Hook nếu thành công khi push mã ML lên `main`; các lần chạy hằng tuần vẫn cập nhật được báo cáo trên R2 mà không cần redeploy API.

Cần các secrets GitHub đã được cấu hình: `DATABASE_URL` (hoặc `NEON_DATABASE_URL`), `ML_R2_ENDPOINT`, `ML_R2_BUCKET`, `ML_R2_ACCESS_KEY_ID`, `ML_R2_SECRET_ACCESS_KEY`. Không công bố các giá trị này.

## API / Dashboard

- Render: `GET /health`, `GET /ready`, `GET /market-forecast`.
- Vercel: `GET /api/market-forecast` (proxy chỉ đọc dữ liệu tổng hợp; không truy vấn giá theo từng thuốc).
- Trang web PharmaBiz: `?view=market-forecast`. Mở được từ sidebar **Dự báo thị trường thuốc** hoặc từ chi tiết DAV.
- API cũ `POST /api/forecast-price` bị vô hiệu (HTTP 410), API Render dự báo giá riêng cho thuốc bị loại.
- Nếu báo cáo chưa cập nhật lên R2, màn hình hiện lỗi tải dữ liệu rõ ràng, không số liệu giả.

## Giới hạn sử dụng

Báo cáo xu hướng lịch sử có thể xuất bản ngay cả khi các giá trị **dự báo tương lai** chưa vượt chất lượng. Tuyệt đối không gọi thống kê lịch sử là giá chắc chắn tăng trong tương lai. Không sử dụng để định giá giao dịch, mua sắm bệnh viện, dự toán bán lẻ hay tư vấn điều trị mà không có kiểm định độc lập.
