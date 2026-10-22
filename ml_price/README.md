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

- Baseline: **giá không thay đổi** (0%).
- Ba ứng viên độc lập: **time_weighted** (log biến động trung bình có suy giảm trọng số theo thời gian và hạn chế ngoại lệ); **hierarchical** (partial pooling theo hoạt chất, loại giá, đơn vị); **temporal_ridge** (hồi quy ridge theo ngày gốc, mùa vụ, khoảng cách giữa hai lần kê khai và biến động trước đó).
- Chọn thuật toán qua tối thiểu **hai vòng expanding walk-forward validation** theo từng thời hạn. Nhãn của train phải có ngày đích trước ngày bắt đầu validation; nhãn validation kết thúc trước lần chia tiếp theo; test cuối không tham gia chọn mô hình.
- Tiếp tục dùng log-MAE và baseline 0%. Chỉ công bố khi validation tốt hơn ít nhất 1%, test độc lập tốt hơn ít nhất 1% và đủ mẫu tham chiếu kê khai lặp lại.
- Báo cáo gồm bảng **model_comparison**, **walkforward_folds**, số mẫu, **test_gain_fraction**, **test_gain_ci95_pct_points** (bootstrap theo mã đăng ký), và khi đạt có **forecast_sample_ci90_pct** (độ bất định lấy mẫu của giá trị trung bình dự báo, KHÔNG phải khoảng dự báo giá thuốc).
- Nếu không đạt, `forecast_change_pct` bắt buộc là `null`, dashboard vẫn hiển thị lịch sử tăng/giảm/giữ nguyên, trung vị, P10–P90 và chuỗi theo năm. Các khoảng bootstrap mô tả sai số lấy mẫu, không phải bằng chứng chắc chắn cho mức tăng giá tương lai.
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

## Phạm vi thay đổi 2026-10-22

- Giữ nguyên Neon Gold, Silver, Bronze, job crawl và cơ chế cập nhật nguồn. Không tăng số liệu, tạo giá kê khai mới hoặc đặt lại lịch ETL.
- Giữ JSON `schema_version=1` để tương thích với Render/Vercel hiện có; các trường kiểm định bổ sung là tùy chọn cho báo cáo cũ.
- Một số kỳ hạn vẫn có thể không đạt do tập kê khai lặp lại thưa; tính đúng đắn quan trọng hơn ép mô hình hiển thị kết quả.
- Báo cáo phương pháp ở `ml_price/market_models.py` và bài test ở `ml_price/tests/test_market_models.py`.


## Chế độ hiển thị khi mô hình chưa qua kiểm định

Báo cáo có ba tầng thông tin tách biệt:
- **Đã qua kiểm định**: \`status=approved\` và \`forecast_change_pct\` có số thực, đã vượt baseline trên tập test riêng.
- **Ước tính thử nghiệm**: \`experimental_change_pct\` chỉ được tính từ giá kê khai thực (ít nhất 20 cặp lịch sử, 15 mã thuốc và 15 mã tham chiếu có lịch sử lặp lại). Đây là mô hình nghiên cứu **CHƯA vượt kiểm định**, chỉ cho thấy một kịch bản cần tiếp tục đánh giá. Không dùng để định giá giao dịch, dự toán giá hay tuyên bố xu hướng chắc chắn.
- **Chỉ thống kê lịch sử**: không đủ thông tin để tính ước tính thử nghiệm, frontend vẫn hiển thị trung vị, tỷ lệ tăng/giảm, dải phân vị và lịch sử 3/6/12 tháng.

Tuyệt đối không sao chép \`experimental_change_pct\` vào \`forecast_change_pct\` khi \`status != approved\`. \`historical_only=true\` tiếp tục có nghĩa là không có dự báo **được phê duyệt**, dù có số thử nghiệm riêng. Giao diện điều hướng không bị khóa; dấu cảnh báo xuất hiện khi chưa có dự báo đạt chuẩn.

Không cần thay đổi Bronze/Silver/Gold hay lịch thu thập nguồn để bật giao diện này. Báo cáo R2 phải được tính lại bằng workflow GitHub từ dữ liệu thực và bản frontend cần triển khai lên Vercel; chỉ sửa mã trên GitHub chưa chứng minh bản production đã cập nhật.
