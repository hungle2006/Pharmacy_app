# Cân bằng nhãn và bổ sung dữ liệu

Huấn luyện dùng trọng số n_train / (n_classes × n_train_of_class). Chỉ đếm
TRAIN; không nhân bản mẫu, thay nhãn hoặc cân bằng lại validation/test.
Loss là tổng cross-entropy có trọng số chia số mẫu của effective batch.
Tổng trọng số mỗi lớp bằng nhau; điều này không làm số quan sát độc lập bằng nhau.

XLM-R được phép chạy tối đa 6 epoch, early stopping theo validation Macro-F1
(patience 2). Tiếp tục từ bản đang phục vụ khi cùng benchmark. Không bảo đảm
accuracy tăng: phải xem accuracy, Macro-F1, balanced accuracy, recall từng nhãn,
ngôn ngữ, confusion và calibration trên tập cố định.
class_balance.json và training_history.json được lưu cùng phiên bản model.

## Ba kênh dữ liệu được tiếp nhận

- CDC: đoạn triệu chứng đã kiểm tra, một trang là một nhóm kiến thức.
- Gretel: mô tả tổng hợp có nhãn, revision cố định; giữ attribution Apache-2.0.
- DDXPlus: ca cấu trúc tổng hợp, CC BY 4.0; file ID và SHA256 cố định.

DDXPlus chỉ đọc source TRAIN, PATHOLOGY là nhãn; không đọc differential diagnosis
vào đầu vào, không suy ra bệnh từ triệu chứng, không đưa tiền sử chứa bệnh vào
đầu vào. Bỏ giá trị mặc định và thang điểm số chưa có mô tả neo. Mã evidence
được diễn đạt bằng question_en + value_meaning gốc. Một tập evidence chỉ tạo
một mẫu dù tuổi/giới khác nhau. Không dịch hay viết lại để tăng số mẫu.

Crosswalk có 10 bệnh, kiểm tra tên nhãn duy nhất trong master. Ví dụ:
Acute rhinosinusitis → Viêm Xoang Cấp Tính. Không ghép pancreatic neoplasm với
ung thư tụy (neoplasm có thể lành tính), anaphylaxis với sốc phản vệ, hoặc
URTI với cảm lạnh. Giới hạn 150.000 dòng scan, tối đa 100 mẫu/nhãn, dừng khi
đạt tổng 100 mẫu train/nhãn. DDXPlus tối đa 50% mẫu của một nhãn, kể cả\ncác lượt chạy tháng sau; không để một nguồn tổng hợp lấn át dữ liệu gốc. Kiểm tra trùng exact + trigram Jaccard ≥ 0,8
với toàn bộ master. Chưa kiểm tra được mọi trùng ngữ nghĩa/dịch chéo ngôn ngữ.

## Mở rộng nguồn và lịch chạy

Firecrawl discovery tìm trên CDC, MedlinePlus, NHS, WHO, NIDDK và NHLBI.
Kết quả chỉ là URL/title vào review queue; chưa được dùng train nếu chưa
kiểm tra ánh xạ bệnh và quyền tái sử dụng. Không cần Firecrawl để tải các
nguồn đã duyệt. Nếu thiếu FIRECRAWL_API_KEY trên Modal, discovery tự tắt,
các importer đã duyệt vẫn chạy.

GitHub giữ lịch tháng hiện hữu; cùng chu kỳ refresh → validate → ghi đè
một master Parquet → train → evaluate → promotion có điều kiện.
Hugging Face giữ lịch sử phiên bản. Không sinh nhiều train shard.
Thay manifest/config làm đổi signature để chạy lại trong cùng tháng.
Khóa dataset_refresh chỉ bảo vệ ghi master và cache nguồn; khóa active bảo vệ\nlượt pipeline/GPU. Model đang train đọc snapshot đã pin, nên có thể xuất bản\nmaster mới trong lúc train mà không thay đổi đầu vào của lượt đang chạy.\nprepare_data gọi cùng hàm refresh_dataset để mọi writer dùng chung khóa.\nYêu cầu train mới xếp hàng, không khởi tạo GPU thứ hai; nếu gặp khóa ngoài\nhàng chờ thì chờ tối đa 30 phút, không tự xóa khóa.
operations_status cung cấp trạng thái gần nhất, không trả token hoặc symptom text.

Ngưỡng promotion validation Macro-F1 0,20 chỉ là ngưỡng kỹ thuật của dự án;
đồng thời phải không giảm so với model đang phục vụ trên cùng benchmark.
Không dùng test để chọn checkpoint. Model mới chưa đạt điều kiện thì không
thay model phục vụ. Còn nhiều nhãn giai đoạn/phân nhóm cần dữ liệu đúng nhãn;
nguồn tổng quát không đủ để cân bằng tất cả 1.400 lớp.

## Kiểm thử

CI chạy toàn bộ unit tests; kiểm tra gradient tích lũy và Trainer 4.57.1 với
Torch CPU 2.8.0 bằng model nhỏ 2 bước; pilot đọc DDXPlus và master công khai,
validate schema và so từng dòng validation/test không đổi. Pilot không upload.

Promotion cũng chặn accuracy validation giảm so với model đang phục vụ trên cùng benchmark, ngay cả khi Macro-F1 tăng. Điểm benchmark có thể cao hơn thực tế khi triển khai; cần một tập ca bệnh độc lập được thẩm định trước khi diễn giải là độ chính xác lâm sàng.
