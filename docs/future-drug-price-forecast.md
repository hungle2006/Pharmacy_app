# PharmaBiz — dự báo giá thuốc tương lai

## Mục tiêu và phạm vi

Tính năng cũ **ước lượng lại giá DAV hiện tại** không còn được gọi bởi website hay Render.
PharmaBiz hiện hiển thị giá DAV từ Neon Gold và một tính năng riêng **dự báo
giá kê khai có thể xuất hiện sau 3, 6 hoặc 12 tháng**.

Model không tiên đoán giá bán lẻ, giá giao dịch, hoặc giá có hiệu lực chính xác
trong từng ngày. Ngày kê khai là thời điểm công bố và thường không xuất hiện
theo lịch đều đặn. Không có giá tương lai được điền giả hoặc suy diễn từ chính
giá DAV đang hiển thị.

## Tạo dữ liệu train có nhãn tương lai thực

1. Đọc `dav_product` và `price_record` trên Neon (chỉ truy vấn đọc).
2. Gộp theo **số đăng ký + loại giá + đơn vị tính + ngày kê khai**.
3. Loại số đăng ký không hợp lệ, giá âm/0, ngày không hợp lệ, quan sát có
   giá cùng ngày xung đột mạnh và mô tả đóng gói viên/ống mâu thuẫn rõ ràng.
4. Với mỗi ngày gốc và từng thời hạn 3/6/12 tháng, tìm ngày kê khai sau
   **thực sự tồn tại** gần mục tiêu (±35 ngày cho 3 tháng; ±50 cho 6/12 tháng).
   Không suy diễn giá ở ngày không có quan sát.
5. Đặc trưng đầu vào chỉ gồm những thông tin của ngày gốc hoặc sớm hơn.
   Nhãn là **log(tỷ lệ giá tương lai / giá tại ngày gốc)**.
6. Split theo thời gian, với **embargo**: train target trước mốc bắt đầu
   validation, validation target trước mốc bắt đầu test. Không dùng giá tương
   lai để tính đặc trưng.
7. So sánh trên tập test theo từng thời hạn với dự báo **giữ nguyên giá lần
   kê khai gần nhất**. Trọng số kết hợp và độ lệch khoảng dự báo học từ
   validation, không học bằng tập test.
8. Phê duyệt từng thời hạn chỉ khi MAE cải thiện ít nhất 1% và WAPE <= 50%,
   có đủ mẫu test, có trọng số ML dương. Khi không đủ bằng chứng: **từ chối
   phát hành**. Không thay bằng model ước lượng giá hiện tại.

## Kết quả chạy thử đầu tiên trên Neon

Tham khảo: [GitHub Actions backtest](https://github.com/hungle2006/Pharmacy_app/actions/runs/39640458371).

- 51.164 bản ghi giá hợp lệ đầu vào, 48.324 quan sát sau lọc, 1.396 cặp
  có nhãn tương lai ở các thời hạn.
- 3 tháng: test MAE 20.890,02 VND, đối chứng giữ nguyên giá 20.890,02 VND.
- 6 tháng: test MAE 39.627,04 VND, đối chứng 39.627,04 VND.
- 12 tháng: test MAE 1.747,60 VND, đối chứng 1.747,60 VND.
- Không có thời hạn nào vượt quality gate. **Không xuất bản** model và
  không hiện giá dự báo. Các chỉ số trên là kết quả kết hợp được chọn bởi
  validation (trọng số AI bằng 0), không chứng minh mô hình học được xu thế
  tương lai.

## Hệ thống triển khai

- Workflow GitHub `Train Pharmacy Price Model` giữ tên để tương thích
  với workflow triển khai Render. Phần train cũ không chạy trong workflow nữa.
- Chỉ model đã phê duyệt mới tải lên `ml/forecast/versions/<version>` và
  thay pointer `ml/forecast/latest.json` của bucket R2 riêng.
- Không đụng vào `ml/price/latest.json` và danh mục giá cũ; chỉ giữ bản
  sao lịch sử phục vụ rollback, **không còn đường API phục vụ model cũ**.
- API Render: `GET /health`, `GET /ready`, `GET /forecast-horizons`,
  `POST /forecast-price`. Không còn `/predict-price`.
- Vercel: `POST /api/forecast-price` dùng khóa riêng từ biến môi trường
  `ML_API_KEY`, trình duyệt không nhận khóa.
- Thuốc có giá gốc quá **365 ngày** không đủ căn cứ làm mốc giá hiện tại:
  trả lỗi `BASE_PRICE_STALE`; từ 181 đến 365 ngày hiển thị cảnh báo.
- Forecast hợp lệ trả giá tương lai, tỷ lệ thay đổi, ngày mục tiêu, sai số
  test và khoảng sai số hiệu chuẩn theo residual validation (không cam kết
  độ phủ chính xác 90% trong phân phối tương lai).

## Để model có thể tạo kết quả đáng tin cậy

Cần tích lũy thêm giá kê khai mới theo cùng mã đăng ký, loại giá và đơn vị;
chuẩn hóa bản ghi lỗi; nghiên cứu thêm tác động tỷ giá, chính sách, biến động
giá theo nhóm hoạt chất; sau đó backtest trên **khoảng thời gian mới chưa từng
dùng để chọn thuật toán**. Không hạ ngưỡng chất lượng để ép model tạo dự báo.
