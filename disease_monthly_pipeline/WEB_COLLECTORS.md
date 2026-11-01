# 10 bộ thu thập website y tế

Mỗi bộ có hàm riêng và cấu hình nguồn riêng; dùng chung bộ máy tải, kiểm tra
robots.txt và trích xuất để tránh mười bản code lặp. Không cần FIRECRAWL_API_KEY
để chạy mười trang đã duyệt. Firecrawl trong chat được dùng tìm và kiểm tra nguồn.

- `crawl_cdc`: CDC — https://www.cdc.gov/hepatitis-c/signs-symptoms/index.html
- `crawl_niddk`: NIDDK — https://www.niddk.nih.gov/health-information/endocrine-diseases/hypothyroidism
- `crawl_nhlbi`: NHLBI — https://www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia
- `crawl_nimh`: NIMH — https://www.nimh.nih.gov/health/publications/generalized-anxiety-disorder-gad
- `crawl_nei`: NEI — https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/dry-eye
- `crawl_nidcd`: NIDCD — https://www.nidcd.nih.gov/health/menieres-disease
- `crawl_nidcr`: NIDCR — https://www.nidcr.nih.gov/health-info/gum-disease
- `crawl_nichd`: NICHD — https://www.nichd.nih.gov/health/topics/endometri/conditioninfo/symptoms
- `crawl_medlineplus`: MedlinePlus Genetics / NLM — https://medlineplus.gov/genetics/condition/phenylketonuria/
- `crawl_nccih`: NCCIH — https://www.nccih.nih.gov/health/fibromyalgia-in-depth

## Chạy từng bộ hoặc tất cả

```bash
python web_collectors.py --source niddk --output ./crawl-preview
python web_collectors.py --source all --output ./crawl-preview
```

CLI chỉ xuất bản xem trước, không upload. Khi chạy pipeline tháng hiện hữu,
`enrichment.run` gọi cả mười bộ, gộp kết quả với nguồn dataset đã duyệt, validate
rồi commit nguyên tử lên Hugging Face. Mỗi nguồn hiện có một trang seed đã kiểm
tra; đây không phải cam kết cào toàn bộ website. Có thể thêm tối đa ba URL đã duyệt
vào từng nguồn trong web_collectors.json mà không phải viết lại bộ máy.

## Dữ liệu và giới hạn

- disease_train_ready.parquet: vẫn duy nhất một tệp train/validation/test master.
- medical_source_knowledge.jsonl: một danh mục kiến thức chuẩn, ghi đè theo URL.
- source_crawl_report.json: một báo cáo trạng thái cho cả mười nguồn, lỗi và số mẫu.

Tên trang và mục nội dung phải khớp cấu hình. Tôn trọng robots, HTTPS, domain,
redirect và thời gian chờ; mỗi trang tối đa 3 MB, mỗi nguồn tối đa ba trang, cả
lượt tối đa mười phút. Lỗi một nguồn không ngăn chín nguồn còn lại; giữ bản tham
chiếu thành công trước đó và đánh dấu lỗi trong báo cáo. Không lách trang chặn tải.
Một trang đổi nội dung chỉ cập nhật danh mục kiến thức, không đếm thành ca mới.

Chỉ thêm vào TRAIN khi tên bệnh ánh xạ duy nhất vào một nhãn hiện hữu, còn thiếu
quota, không chứa tên đáp án, không trùng/ngần trùng bất kỳ split nào và URL chưa
được nhập trước đó. Không tự tạo nhãn mới, không chia một trang thành hàng chục
mẫu, không dịch/paraphrase để cân bằng giả. Validation/test không đổi. Những đoạn
mô tả tổng quát, trang đã đủ quota, hoặc nhãn trùng tên/đồng nghĩa giữ ở danh mục
tham chiếu; không tự đưa vào train. NCCIH là tài liệu nền cập nhật tháng 5/2016,
được đánh dấu reference_only; retrieved_at không phải ngày cập nhật nội dung.

Điều kiện quyền dùng áp dụng cho text do cơ quan biên soạn; không áp dụng mặc
định cho ảnh, logo, bài báo đính kèm và tài liệu của bên thứ ba. Chú thích nguồn
và chính sách riêng có trong SOURCE_NOTICES.md và từng bản ghi.

CI kiểm tra ranh giới mục, tên trang đổi, đoạn có dấu quyền bên thứ ba, nhãn mơ
hồ, quota, giữ nguyên holdout, chống trùng và giữ một nhóm/URL qua các lần chạy.
Không hứa accuracy tăng từ số lượng trang: phải đo model trên benchmark cố định.
