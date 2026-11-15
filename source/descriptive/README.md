# Thống kê mô tả đặc điểm xe

Gói hiện có `vehicle_characteristics.py`: đọc Population clean và xuất tần số, thống kê Electric Range cùng bốn hình. Chưa triển khai phân bố địa bàn, chuỗi thời gian hoặc kiểm định trong gói này.

## Chạy

Cài dependency bằng `python -m pip install -r requirements.txt`, rồi chạy từ thư mục gốc repo. Thay đường dẫn dữ liệu trong ví dụ PowerShell bằng đường dẫn trên máy:

```powershell
python source/descriptive/vehicle_characteristics.py `
  --population-clean "D:/du_lieu/EV_Population_Washington_Clean.csv" `
  --results-dir "results/descriptive" `
  --figures-dir "figures/descriptive"
```

Có thể dùng `python -m source.descriptive.vehicle_characteristics` với cùng tham số. `--top-makes` mặc định 10, chỉ đổi số hãng được vẽ; CSV vẫn chứa tất cả hãng.

Chương trình yêu cầu các tên đầu ra chưa tồn tại và không trùng file nguồn. Khi chạy lại để đối chiếu, chọn thư mục kết quả/hình mới; không ghi đè trực tiếp các kết quả đã lưu. Dữ liệu nguồn tải từ link trong [data/README.md](../../data/README.md), không cần thêm CSV vào repo.

## Năm bảng trong results-dir

| File | Nội dung |
|---|---|
| `vehicle_type_frequency.csv` | Số lượng và tỷ trọng BEV/PHEV |
| `cafv_frequency.csv` | Số lượng và tỷ trọng theo nhãn CAFV gốc |
| `make_frequency.csv` | Tần số của tất cả hãng, sắp giảm dần; không chỉ lưu top 10 |
| `model_year_frequency.csv` | Tần số theo năm mẫu xe, sắp theo năm |
| `range_summary.csv` | Số hợp lệ/thiếu và thống kê Range của toàn mẫu, BEV và PHEV |

Bốn bảng tần số có cột phân loại, `count`, `share_pct`, `population_n`, `is_missing`. Mẫu số `share_pct` là toàn bộ Population; đơn vị là phần trăm từ 0 đến 100, không phải tỷ lệ 0–1. Nếu có nhãn thiếu, vẫn giữ một dòng `is_missing=True` và ô phân loại để trống. Không điền thiếu thành nhãn thực hoặc âm thầm loại khỏi mẫu số.

`range_summary.csv` gồm:

- `group`: ALL, BEV, PHEV; thêm MISSING_TYPE nếu phát sinh bản ghi thiếu loại xe.
- `total_n`, `valid_n`, `missing_n`, `valid_pct`, `missing_pct`: quy mô từng nhóm và mức thiếu.
- `mean_miles`, `median_miles`, `std_miles`, `min_miles`, `q1_miles`, `q3_miles`, `iqr_miles`, `max_miles`: thống kê trên Range hợp lệ, đơn vị mile.

Độ lệch chuẩn mẫu dùng `ddof=1`. Q1/Q3 dùng quantile nội suy tuyến tính; IQR = Q3 − Q1. Nhóm không có giá trị hợp lệ để trống các thống kê; SD để trống nếu có dưới hai giá trị. Không điền missing bằng 0, không loại ngoại lệ và không khử trùng các bản ghi trên thuộc tính đã giữ.

## Bốn hình trong figures-dir

| File | Nội dung |
|---|---|
| `vehicle_type_share.png` | Cơ cấu loại xe theo toàn bộ Population |
| `top_makes.png` | Các hãng đứng đầu theo số xe; tỷ lệ vẫn tính trên toàn bộ Population |
| `model_year_distribution.png` | Phân bố số xe theo Model Year; không phải doanh số theo năm |
| `range_by_vehicle_type.png` | Boxplot Range theo loại xe; ghi cả số hợp lệ/thiếu |

Hình Range dùng hộp Q1–Q3, đường trung vị, râu theo 1,5 IQR và giữ các điểm ngoài râu. Các chữ số trên hình được làm tròn để đọc; CSV giữ độ chính xác tính toán.

## Diễn giải và phạm vi

Population là ảnh chụp các bản ghi phương tiện; Model Year là năm mẫu xe. CAFV là nhãn đủ điều kiện hành chính trong dữ liệu, không đồng nghĩa một kiểm định về hiệu quả chính sách.

Thống kê Range chỉ mô tả các bản ghi có Range hợp lệ. Mức thiếu giữa BEV và PHEV khác nhau rõ rệt trong dữ liệu nghiên cứu; không suy rằng phân bố Range hợp lệ đại diện đầy đủ cho toàn bộ mỗi nhóm.

Các đầu ra này phục vụ phần kết quả đặc điểm/cơ cấu đội xe. Tên file theo nội dung, không theo số chương; script chưa thực hiện thống kê suy diễn hay mô hình dự báo.
