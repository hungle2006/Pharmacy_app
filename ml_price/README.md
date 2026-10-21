# PharmaBiz — ML Model 1: dự đoán giá thuốc

**Trạng thái:** Mã huấn luyện, pipeline và server đã chuẩn bị. Chỉ báo mô hình sẵn sàng khi huấn luyện trên dữ liệu thật **và** vượt baseline. Mô hình không nhằm báo giá bán lẻ hay tư vấn điều trị.

## 1. Dữ liệu và chất lượng mô hình

- Neon Gold (chỉ SELECT): `dav_product` JOIN `price_record`.
- Phân khúc duy nhất phiên bản đầu: `price_type = EXPECTED_WHOLESALE_PRICE_VAT`, `currency = VND`, `unit = viên` (gộp Viên/viên). Không trộn hộp, lọ với viên.
- Các đầu vào: hoạt chất, hàm lượng, dạng bào chế, nhà sản xuất, quốc gia, quy cách.
- Mỗi số đăng ký thuốc chỉ dùng quan sát giá mới nhất; nếu trùng thời điểm thì ưu tiên nguồn Silver. Không để các bản DAV cũ/Silver cùng số đăng ký nằm ở cả tập train và test.
- Chia theo thời gian: 70% train, 15% validation, 15% test; CatBoost hồi quy trên log(giá). Test dùng để chấm điểm cuối.
- So sánh với baseline trung vị theo nhóm hoạt chất/hàm lượng/dạng bào chế từ **tập train**. Chỉ xuất bản nếu MAE trên test cải thiện ít nhất 1%. Báo cáo MAE, RMSE, R² và số quan sát.
- Mỗi mô hình được version hóa; server Render chỉ đọc bản đã được đánh dấu `approved`. Khi kết quả kém, bản model trên R2 không bị ghi đè.

## 2. Cấu hình GitHub Actions

Trong [GitHub repository → Settings → Secrets and variables → Actions](https://github.com/hungle2006/Pharmacy_app/settings/secrets/actions), thêm các secrets **nếu chưa có**:

| Secret GitHub | Giá trị |
|---|---|
| `DATABASE_URL` hoặc `NEON_DATABASE_URL` | Neon pooled Postgres URL có quyền SELECT |
| `ML_R2_ENDPOINT` hoặc `R2_ENDPOINT` | R2 S3 endpoint: https://<account-id>.r2.cloudflarestorage.com |
| `ML_R2_BUCKET` hoặc `R2_BUCKET` | Tên R2 bucket **private** để lưu model |
| `ML_R2_ACCESS_KEY_ID` hoặc `R2_ACCESS_KEY_ID` | R2 S3 access key có quyền đọc/ghi bucket |
| `ML_R2_SECRET_ACCESS_KEY` hoặc `R2_SECRET_ACCESS_KEY` | R2 S3 secret key |

**Không đưa bất kỳ secret nào vào file .py, .yml, issue hoặc chat công khai.**

Vào [Actions → Train Pharmacy Price Model](https://github.com/hungle2006/Pharmacy_app/actions/workflows/train-price-model.yml) → Run workflow. Sau đó workflow tự chạy Chủ nhật 10:00 sáng giờ Việt Nam (phụ thuộc lịch thực thi GitHub). Với model đạt chuẩn, workflow gửi:

- `ml/price/versions/<model_version>/price_model.cbm`
- `ml/price/versions/<model_version>/metadata.json`
- `ml/price/latest.json` — cập nhật **sau cùng**, trỏ tới phiên bản mới.

Artifact GitHub lưu thêm 14 ngày để kiểm tra. Nếu không có secret, model không đạt chuẩn, hoặc upload lỗi thì workflow thất bại rõ ràng; không tự nhận là đã huấn luyện thành công.

## 3. Đưa server lên Render Free

Có thể triển khai bằng [Render Blueprint](https://dashboard.render.com/select-repo?type=blueprint) từ `render.yaml`, hoặc Web Service Python sử dụng:

- Repository: `hungle2006/Pharmacy_app`, nhánh `main`.
- Build: `pip install -r ml_price/requirements-serve.txt`.
- Start: `uvicorn ml_price.serve:app --host 0.0.0.0 --port $PORT`.
- Region: Singapore; instance: Free; auto-deploy: enabled.
- Secrets Render: `ML_API_KEY` (tự tạo mật khẩu dài, ngẫu nhiên), `ML_R2_ENDPOINT`, `ML_R2_BUCKET`, `ML_R2_ACCESS_KEY_ID`, `ML_R2_SECRET_ACCESS_KEY`. Render **không cần DATABASE_URL** để dự đoán.
- Endpoint `GET /health`: máy chủ hoạt động; `GET /ready`: 503 nếu model chưa sẵn sàng; `GET /model-info` và `POST /predict-price` yêu cầu `X-API-Key`.
- Mỗi 5 phút (khi có request), server kiểm tra `latest.json` để tự nạp model mới mà không cần redeploy. Nếu R2 có lỗi, giữ bản chạy trước đó.

Ví dụ gọi API (địa chỉ minh họa, thay bằng domain Render thật):

```bash
curl -X POST https://your-service.onrender.com/predict-price \
  -H "X-API-Key: $ML_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ingredient":"Paracetamol","strength":"500 mg","dosage_form":"Viên nén","manufacturer":"UNKNOWN","country":"Việt Nam","package":"Hộp 10 vỉ x 10 viên","price_type":"EXPECTED_WHOLESALE_PRICE_VAT","unit":"viên"}'
```

Render Free có thể ngủ và khởi động lại khi có yêu cầu, nên request đầu có thể chậm; API không hứa hẹn hoạt động 24/7. Trên Free, cần kiểm tra giới hạn RAM trước khi phục vụ mô hình.

## 4. Kết nối giao diện PharmaBiz trên Vercel

Thiết lập biến môi trường Vercel server-side:

- `ML_PRICE_API_URL`: URL HTTPS của Render (kết thúc bằng `.onrender.com`)
- `ML_API_KEY`: cùng API key đã cấu hình ở Render.

API `POST /api/predict-price` ở Vercel sẽ chuyển yêu cầu sang Render, giấu khóa truy cập khỏi trình duyệt. Nếu Render hoặc R2 chưa sẵn sàng, API trả lỗi tường minh, **không có số liệu dự đoán giả**.

## 5. Chạy thử tại máy

```bash
pip install -r ml_price/requirements-train.txt
python -m unittest discover -s ml_price/tests -p 'test_*.py' -v
# Chỉ chạy huấn luyện thật khi có quyền kết nối Neon SELECT:
python -m ml_price.train
```

Lưu ý: Giá dự đoán là ước lượng từ dữ liệu kê khai, không phản ánh giá mua thực tế của nhà thuốc/bệnh viện, giá bán lẻ hay tương đương lâm sàng.
