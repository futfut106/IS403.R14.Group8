# Thống kê mô tả xe, địa bàn và diễn biến thời gian

Gói gồm thống kê đặc điểm xe, phân bố địa bàn và diễn biến theo tháng. Các phần dùng Population/History clean đúng cấp quan sát; chưa chạy kiểm định suy diễn hoặc mô hình dự báo.

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

## Phân tích địa bàn và chuỗi thời gian

### Mã nguồn bổ sung

| File | Trách nhiệm |
|---|---|
| `spatial_distribution.py` | Phân bố Population theo County/County–City, tỷ lệ EV và cơ cấu Passenger/Truck từ History cùng tháng |
| `monthly_trends.py` | Diễn biến số xe, cơ cấu, thay đổi ròng, tăng trưởng và tỷ lệ EV toàn bang; không fit model |
| `run_descriptive.py` | Chạy toàn bộ mô tả; tùy chọn `--skip-vehicle` chỉ chạy địa bàn và chuỗi, giữ nguyên gói đặc điểm xe |

Ví dụ bổ sung hai phần mới từ thư mục gốc repo, không ghi đè năm bảng/bốn hình đặc điểm xe đã có:

```powershell
python source/descriptive/run_descriptive.py `
  --population-clean "D:/du_lieu/EV_Population_Washington_Clean.csv" `
  --history-clean "D:/du_lieu/EV_Population_History_Washington_Clean.csv" `
  --results-dir "results/descriptive" `
  --figures-dir "figures/descriptive" `
  --skip-vehicle
```

Lệnh yêu cầu các đầu ra của hai phần mới chưa tồn tại. Khi chạy lại, chọn thư mục mới. Bỏ `--skip-vehicle` để tạo lại toàn bộ 14 bảng CSV, một JSON và 12 hình ở các thư mục đầu ra mới. Không bỏ cờ này để chạy vào nơi đã có bảng/hình đặc điểm xe.

Có thể chạy từng script với `--help`, hoặc dùng `python -m source.descriptive.run_descriptive` cùng tham số. `--snapshot-date` mặc định `2023-11-30`, phải là một ngày cuối tháng có trong History; `--top` mặc định 10, chỉ giới hạn số địa bàn được vẽ, không cắt các bảng CSV.

### Bảng địa bàn

| File | Cấp quan sát và mẫu số |
|---|---|
| `county_summary.csv` | Một dòng mỗi County trong Population; `ev_count=bev+phev`, `share_pct` chia toàn bộ Population; cơ cấu BEV/PHEV chia số EV của chính quận |
| `city_summary.csv` | Một dòng mỗi cặp County–City, giữ nguyên tên; tỷ trọng chia toàn bộ Population; nếu có City thiếu vẫn giữ dòng và cờ `is_missing_city` |
| `county_ev_rates.csv` | Một dòng mỗi quận tại tháng chọn từ History, đã cộng hai nhóm sử dụng; `ev_pct=100×ev_total/total_vehicles` của cùng quận/tháng |
| `usage_type_summary.csv` | Hai dòng Passenger/Truck tại tháng chọn; `ev_pct` dùng tổng phương tiện của chính nhóm; các tỷ trọng toàn bang có tên cột riêng |
| `spatial_summary.json` | Mức tập trung, số tên City/cặp County–City, quy mô snapshot và định nghĩa mẫu số |

Population và History là hai nguồn khác cấp quan sát/thời điểm. Không gán ngày snapshot History cho Population, không chia số EV Population cho tổng phương tiện History. `population_n` là mẫu số cơ cấu Population, không phải số phương tiện của History.

`rank` của hai bảng Population là thứ tự hiển thị giảm dần theo số xe, phá hòa theo tên. Hai cột rank History dùng thứ hạng nhỏ nhất cho các giá trị bằng nhau. Các bảng giữ đủ địa bàn, không chỉ lưu top 10. Số tên City phân biệt khác số cặp County–City vì một tên có thể xuất hiện ở nhiều quận.

### Bảng chuỗi thời gian

| File | Nội dung |
|---|---|
| `monthly_growth.csv` | Chuỗi chuẩn tám cột và các chỉ tiêu cơ cấu/tăng trưởng/thay đổi ròng, trung bình trượt mức EV 12 tháng, SD mẫu của 12 thay đổi ròng |
| `overall_growth_summary.csv` | BEV/PHEV/EV: đầu kỳ, cuối kỳ, thay đổi ròng, tăng trưởng toàn kỳ và tăng trưởng năm hóa |
| `annual_growth.csv` | Các mốc tháng 12 và tháng cuối dữ liệu; `is_year_end=False` ở 11/2023, không gọi mốc này là hết năm 2023 |
| `growth_period_summary.csv` | Mô tả thay đổi ròng/log-growth trên toàn bộ 82 khoảng, hai nửa 41 khoảng và các khoảng thuộc train/test |
| `notable_months.csv` | Ba thay đổi ròng lớn nhất và ba nhỏ nhất, phục vụ mô tả; không mặc định giá trị nhỏ nhất là giảm âm |

Các tiền tố `bev`, `phev`, `ev` nhận diện chuỗi; hậu tố `net_change` có đơn vị xe; `mom_growth_pct`, `yoy_growth_pct`, `log_growth_pct` có đơn vị %. Log-growth mô tả ở đây được nhân 100 và không phải bảng feature ML để đưa trực tiếp vào model.

- Thay đổi ròng: `y_t−y_(t−1)`; MoM: `100×(y_t/y_(t−1)−1)`.
- Thay đổi cùng kỳ: `y_t−y_(t−12)`; YoY: `100×(y_t/y_(t−12)−1)`.
- Tăng trưởng năm hóa: `100×[(y_cuoi/y_dau)^(12/so_khoang_thang)−1]`; 83 mốc tương ứng 82 khoảng tháng.
- Log-growth: `100×[ln(y_t)−ln(y_(t−1))]`; tỷ lệ toàn bang được tính lại từ tổng số lượng.

Giữ trống kỳ không đủ lịch sử: thay đổi/MoM thiếu tháng đầu, YoY thiếu 12 tháng đầu; không điền bằng 0. `ev_ma12` cần đủ 12 mức EV; `net_change_sd12` cần đủ 12 thay đổi ròng và dùng `ddof=1`.

Các thống kê train/test trong gói này chỉ mô tả phần dữ liệu tương ứng, không phải kết quả huấn luyện hay backtest. Toàn kỳ dùng để mô tả; chưa thực hiện ADF/KPSS, ACF/PACF, kiểm định mùa vụ hoặc nhận dạng model. Không kết luận mùa vụ hay nhân quả chỉ từ đồ thị.

### Tám hình bổ sung

- Địa bàn: `population_by_county.png`, `population_by_city.png`, `county_ev_rates.png`, `usage_type_comparison.png`.
- Chuỗi: `monthly_ev_population.png`, `monthly_ev_composition.png`, `monthly_ev_growth.png`, `statewide_ev_rate.png`.

Hình ghi nguồn, kỳ và mẫu số. Các số xe cuối tháng và thay đổi ròng không được diễn giải trực tiếp thành doanh số. Không tự suy nhu cầu điện, hành vi sạc hay số trạm từ các bảng/hình này.
