# Disease pipeline: Hugging Face → Modal → model phiên bản → Render

Đã cấu hình đúng hai repo:
- Dữ liệu: https://huggingface.co/datasets/leminhhung0101/disease_data
- Model: https://huggingface.co/leminhhung0101/disease_model

Đây là mã nguồn pipeline đã chuẩn bị, không phải bằng chứng đã triển khai hoặc train xong. Không có token trong gói. Các lệnh deploy/train bắt đầu tài nguyên và chi phí khi bạn thực hiện.

## Hoạt động mỗi tháng

GitHub Actions có lịch **09:17 ngày 1 mỗi tháng, giờ Việt Nam** (`17 2 1 * *`, UTC), cùng nút **Run workflow** để chạy ngay. Lịch GitHub là best effort, có thể trễ và chỉ hoạt động khi workflow nằm trên default branch. Public repo có thể bị tắt schedule sau thời gian không hoạt động theo chính sách GitHub; kiểm tra tab Actions nếu bỏ lỡ kỳ chạy.

1. GitHub deploy mã ứng dụng Modal và gửi một lời gọi background, rồi kết thúc; không chờ train nhiều giờ trên GitHub.
2. Modal CPU xác định commit dữ liệu hiện tại, tải **mọi Parquet** khớp `config.json` trong **một snapshot nhất quán**. Cache tồn tại trong Volume nên file không đổi được tái sử dụng.
3. Hợp nhất schema, gộp trùng và kiểm tra chất lượng. File QA không có nhãn bệnh được thống kê và bỏ khỏi classifier, không tự sinh nhãn.
4. Lần đầu giữ split đã chuẩn bị trong tệp hiện có. Nếu đầu vào hoàn toàn là dữ liệu thô có nhãn, chạy bộ làm sạch và chia nhóm đã kèm theo.
5. Giữ cố định validation/test trong Volume. Khi thêm dữ liệu tháng sau, chỉ mẫu mới phù hợp của các nhãn đã có được đưa vào train. Mẫu trùng hoặc gần trùng tập giữ lại không được dùng train. Nhãn mới được cách ly/báo số lượng cho đến khi có phiên bản benchmark mới được chuẩn bị có chủ đích.
6. Modal GPU L4 huấn luyện, tiếp tục checkpoint nếu **cùng dữ liệu và cấu hình** bị gián đoạn. Với dữ liệu mới, tạo run mới; nếu benchmark không đổi, khởi tạo trọng số từ model đang dùng và huấn luyện lại trên toàn tập train hiện tại. Không mang optimizer cũ sang dữ liệu mới.
7. Upload model hoàn chỉnh, tokenizer, metrics và manifest vào `versions/<run_id>/` của model repo. Chỉ cập nhật `deployment.json` sau khi validation đạt ngưỡng cấu hình và không kém model hiện hành trên cùng benchmark. Không dùng test để chọn model.
8. API dự đoán nạp artifact theo commit SHA cố định trong pointer. Có thể gọi Render Deploy Hook sau promotion; với chế độ proxy, model mới cũng tự được Modal nạp sau tối đa khoảng 60 giây, không bắt buộc redeploy Render.

**Không có Parquet thay đổi:** mặc định kiểm tra hàng tháng nhưng bỏ qua GPU, tránh train lặp tốn phí. Chọn `force` trong Run workflow nếu chủ động muốn train lại. Lịch không tự tải dữ liệu mới từ nguồn bên ngoài; bạn cần thêm/cập nhật Parquet trong `disease_data`.

## Bố trí mã trong GitHub

Trong repo Pharmacy_app, đặt thư mục này ở `disease_monthly_pipeline/`, và hai workflow ở **root**:

```
.github/workflows/disease-monthly.yml
.github/workflows/disease-tests.yml
disease_monthly_pipeline/config.json
...
```

Gói ZIP đã bố trí đúng các đường dẫn này. Không đưa dataset/model/token vào Git. Nếu dùng repo riêng, vẫn giữ thư mục con `disease_monthly_pipeline/` để các đường dẫn workflow và Render Blueprint đúng.

## Thiết lập một lần — GitHub

Vào repo → Settings → Secrets and variables → Actions, thêm:

| Secret | Giá trị nhập riêng trong giao diện |
|---|---|
| MODAL_TOKEN_ID | Token ID của workspace Modal dành cho pipeline |
| MODAL_TOKEN_SECRET | Token secret tương ứng |

Không gửi các giá trị này trong chat. Sau khi test pass và mã đã nằm trên main, vào Actions → **Disease model - monthly refresh** → **Run workflow** để chạy lần đầu. Các lần sau có lịch tháng.

Success trên GitHub nghĩa là **đã gửi lệnh**, không phải train đã hoàn thành. Artifact `disease-modal-submission` chứa call ID. Theo dõi trên Modal hoặc chạy `python scripts/check_status.py CALL_ID` từ thư mục mã khi đã đăng nhập Modal.

## Thiết lập một lần — Modal

1. Chọn đúng Modal workspace và environment **main**.
2. Tạo Modal Secret tên chính xác **`disease-training`** trong Dashboard, chứa:
   - **HF_TOKEN**: token đọc dataset repo và ghi model repo; nên giới hạn quyền vào hai repo được nêu.
   - **RENDER_DEPLOY_HOOK**: tùy chọn; nhập hook của dịch vụ Render nếu muốn tự redeploy sau promotion. Không bắt buộc với proxy.
3. GPU và Volume phải khả dụng trong tài khoản. Pipeline tạo các tài nguyên riêng: App `disease-monthly-pipeline`, Volume v2 `disease-monthly-storage`, Dict `disease-monthly-locks`.

Chạy thủ công nếu cần:

```bash
python -m pip install 'modal>=1.2,<2'
modal setup
modal deploy modal_app.py
python scripts/submit.py
```

App dùng CPU để tải/làm sạch; GPU chỉ bật khi bắt đầu train. CPU điều phối nhỏ chờ kết quả. Các chức năng có timeout riêng: prepare 1 giờ, train tối đa 22 giờ, toàn pipeline tối đa 24 giờ. Nếu vượt giới hạn, chạy lại cùng dữ liệu/cấu hình để resume checkpoint đã lưu. Checkpoint hiện được lưu mỗi epoch; phần chưa được lưu khi gián đoạn có thể phải chạy lại.

Khóa phân tán ngăn hai phiên train đồng thời kể cả khi deploy mã mới. Nếu tác vụ bị chấm dứt cứng làm khóa không được giải phóng, xác nhận không còn job chạy rồi xóa riêng key `active` trong Dict trên Modal; không xóa cả Volume. Khóa không có tác dụng thay cho theo dõi chi phí.

## Thiết lập Render

### Mặc định: Render Free làm API, Modal thực hiện suy luận

XLM-R không phù hợp RAM 512 MB của Render Free. Blueprint `disease_monthly_pipeline/render.yaml` dùng service proxy nhẹ, không tải Torch/trọng số vào Render. Tên dự kiến: `pharmacy-disease-monthly-api`.

- Blueprint path: `disease_monthly_pipeline/render.yaml`.
- Root directory: `disease_monthly_pipeline`.
- Build: `pip install -r requirements-api.txt`.
- Start: `uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1`.
- Environment: `INFERENCE_BACKEND=modal`, `MODAL_APP_NAME=disease-monthly-pipeline`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`.
- `API_KEY` được Blueprint tạo; lấy từ Environment để dùng trong header `X-API-Key` của client/backend được phép gọi.

API không lưu/log mô tả người dùng trong mã ứng dụng. `/health` chỉ kiểm tra process, không khẳng định model đã tải. Lần predict đầu sau khi Modal cold start có thể chậm vì phải tải model. Suy luận Modal dùng CPU, tối đa 2 container, tự giảm về 0; có chi phí Modal theo sử dụng, không phải GPU miễn phí.

### Tùy chọn: nạp model trực tiếp trên Render có đủ RAM

Chỉ đổi sau khi chủ động chọn compute plan có bộ nhớ phù hợp và thử tải thực tế:
- Build: `pip install -r requirements-local.txt`.
- `INFERENCE_BACKEND=local`.
- `HF_TOKEN` read-only với model repo nếu repo private; `MODEL_CACHE=/tmp/disease_hf_cache`.
- Dùng một worker. Lần đổi model cần dung lượng cho model cũ/mới trong lúc chuyển; không tự chọn hoặc nâng gói trả phí trong pipeline này.

## Gọi API

```bash
curl -X POST "$DISEASE_API_URL/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DISEASE_API_KEY" \
  -d '{"text":"Tôi bị đau bụng kéo dài và có những triệu chứng khác","top_k":5}'
```

Trả về top-k nhãn, điểm softmax chưa hiệu chuẩn, `model_run` và `artifact_revision`. Không coi score là xác suất chẩn đoán y khoa. Nếu gọi từ website công khai, giữ API key ở backend/Vercel server-side; không nhúng token Modal hoặc API key dài hạn trong JavaScript trình duyệt. `CORS_ORIGINS` có thể đặt danh sách domain được phép.

## Thêm nhiều Parquet

Bạn có thể để:

```
disease_train_ready.parquet
updates/2026-11.parquet
updates/2026-12.parquet
```

Schema bổ sung đơn giản: `text` (mô tả), `label` (tên bệnh/tình trạng), `language` (`vi`/`en`); **không tự gán split** cho các mẫu bổ sung. Cũng hỗ trợ master `input_text/disease_label/task`, hội thoại `messages/target_disease/subset`, hoặc `Question/Disease` đã chuyển Parquet. Không suy bệnh từ câu trả lời QA. Numeric label IDs không đủ nếu không có tên nhãn.

Nếu cần thêm lớp bệnh mới, chuẩn bị đủ dữ liệu và benchmark tương ứng, tăng `benchmark_version` trong config có chủ đích. Bản với benchmark mới không tự thay model hiện hành nếu chưa chọn `approve_new_benchmark` trong Run workflow. Không đổi benchmark chỉ để làm điểm đẹp hơn; theo dõi các bộ đánh giá theo phiên bản.

## Ngưỡng và quyền truy cập

`minimum_validation_macro_f1=0.0` là ngưỡng khởi tạo kỹ thuật để không đoán trước hiệu năng; **không phải tiêu chuẩn chất lượng lâm sàng**. Khi có baseline phù hợp, đặt ngưỡng có ý nghĩa trước khi dùng thực tế. `promotion_tolerance=0.0` không chấp nhận giảm validation macro-F1 trên cùng benchmark.

Hai repo HF được cung cấp đang public ở lần kiểm tra 31/10/2026. Chuyển repo dữ liệu thành private nếu cần kiểm soát chia sẻ; mã vẫn hoạt động với HF_TOKEN phù hợp. Tôn trọng điều khoản nguồn Meddies/PB3002; không có xác nhận y khoa độc lập hay khử trùng ngữ nghĩa/bản dịch đầy đủ trong pipeline.

## Kiểm thử và giới hạn triển khai

```bash
pip install -r requirements-test.txt
python -m pytest -q tests
```

Đã kiểm tra nhiều shard, trùng dữ liệu, holdout cố định, ngăn chuyển train sang test, bỏ QA thiếu nhãn, snapshot pin commit, promotion theo validation, API key và proxy. Blueprint được kiểm tra JSON Schema hiện hành; cần Render CLI/API validation khi đã có repo/workspace và quyền truy cập. Chưa chạy job GPU, chưa ghi model HF, chưa tạo Render service nếu chưa cấu hình secrets và xác nhận workspace.
