# Chuẩn bị dữ liệu phân tích

Đọc hai CSV **clean**, tạo chuỗi tháng toàn bang và mẫu cho H1–H4. Gói này không làm sạch lại raw, không chạy kiểm định, không tạo đặc trưng ML, không huấn luyện hoặc so sánh mô hình.

## Mã nguồn

| File | Trách nhiệm |
|---|---|
| `build_monthly_series.py` | Đọc/kiểm tra History clean, cộng số lượng toàn bang theo tháng, tính lại tỷ lệ EV và gắn train/test |
| `build_analysis_samples.py` | Đọc/kiểm tra Population clean, tạo mẫu Range/CAFV, bảng cơ cấu quận và hai snapshot History |
| `run_preparation.py` | Điều phối hai bước, kiểm tra toàn bộ đường dẫn rồi xuất năm CSV dữ liệu và hai tóm tắt |

Dependency: Python và pandas. Dữ liệu tải qua các link trong [data/README.md](../../data/README.md). Các đường dẫn nguồn/đích được truyền bằng tham số; không tạo `data/raw/` hay `data/processed/` trong repo.

## Chạy từ thư mục gốc repo

Ví dụ PowerShell dưới đây yêu cầu thay các đường dẫn `D:/du_lieu/` bằng vị trí trên máy. Hai clean phải tồn tại; các file đầu ra phải chưa tồn tại.

```powershell
python source/preparation/run_preparation.py `
  --population-clean "D:/du_lieu/EV_Population_Washington_Clean.csv" `
  --history-clean "D:/du_lieu/EV_Population_History_Washington_Clean.csv" `
  --output-dir "D:/du_lieu/preparation_output" `
  --summary-dir "results/preparation"
```

Cũng có thể gọi `python -m source.preparation.run_preparation` với cùng tham số. Mỗi builder có CLI riêng; dùng `--help` để xem. Builder chuỗi chỉ cần History; builder mẫu cần cả Population và History.

Nếu chạy lại khi đã có các tóm tắt trong repo, chọn `--summary-dir` mới để đối chiếu; chương trình không tự ghi đè. Chọn thư mục đầu ra mới hoặc xử lý các bản cũ có chủ đích trước khi dùng lại tên.

## Năm CSV dữ liệu tại output-dir

| File | Cấp quan sát và nội dung |
|---|---|
| `statewide_monthly.csv` | 83 tháng 01/2017–11/2023; train 01/2017–11/2022 (71 tháng), test 12/2022–11/2023 (12 tháng) |
| `range_analysis_sample.csv` | Bản ghi Population có Range hợp lệ cho H1/H2; không xóa các dòng giống nhau trên thuộc tính giữ lại |
| `cafv_analysis_sample.csv` | Toàn bộ Population, giữ cả CAFV Unknown; dùng cờ để chọn mẫu chính/độ nhạy H3 |
| `county_vehicle_type_counts.csv` | 39 quận, số BEV/PHEV từ Population; cờ độ nhạy H4a cho quận có tổng từ 30 xe |
| `county_ev_snapshots.csv` | 78 dòng = 39 quận × hai mốc 01/2017 và 11/2023; đã cộng Passenger/Truck trong cùng quận/tháng |

### Schema và cách dùng

- Chuỗi tháng: `date, bev, phev, ev_total, non_ev, total_vehicles, ev_pct, split`. `ev_pct = 100 × ev_total / total_vehicles`, đơn vị %, không lấy trung bình tỷ lệ các quận. Các cột đếm có đơn vị xe.
- Range: `source_record, county, vehicle_type, model_year, electric_range, h1_year_le_2020, h2_valid`. `vehicle_type` là BEV/PHEV; Range có đơn vị mile. H1 chính dùng toàn bộ file; độ nhạy dùng `h1_year_le_2020=True`. H2 dùng `h2_valid=True`, tách toàn mẫu/BEV/PHEV ở bước kiểm định.
- CAFV: `source_record, county, vehicle_type, cafv_status, cafv_known`. H3 chính chọn `cafv_known=True`; độ nhạy giữ tất cả nhãn. Nhãn CAFV gốc được giữ nguyên.
- Cơ cấu quận: `county, bev, phev, ev_total, included_h4a_sensitivity`. H4a chính dùng đủ quận; độ nhạy dùng cờ True, không xóa quận nhỏ khỏi dữ liệu chuẩn.
- Snapshot: `date, county, bev, phev, ev_total, non_ev, total_vehicles, ev_pct`. H4b chính dùng 11/2023, độ nhạy dùng 01/2017; phân tích riêng hai tháng. Mẫu số là tổng phương tiện, không phải số quận.

`source_record` là thứ tự bản ghi dữ liệu, bắt đầu từ 1 trong Population clean đã đọc; dùng để truy lại dòng, không phải VIN hoặc mã xe. Các cờ được xuất True/False. Không ghép Population với History theo từng phương tiện.

## Hai tóm tắt tại summary-dir

- `sample_summary.csv`: số dòng, số phương tiện, số quận và điều kiện lọc của từng mẫu chính/độ nhạy. Với bảng quận, số dòng là số quận; `vehicle_count` là tổng số xe, hai đại lượng khác nhau.
- `monthly_series_summary.json`: cấp tổng hợp, kỳ thời gian, schema, đơn vị và số tháng train/test. Không chứa cấu hình mô hình hoặc chỉ tiêu dự báo.

Các tóm tắt là sản phẩm bàn giao trong `results/preparation/`; năm CSV dữ liệu được lưu ở vị trí ngoài repo do người chạy chọn.

## Kiểm tra trước khi xuất

- Đúng schema clean, phạm vi WA và nhãn dự kiến; Population giữ số lần xuất hiện bản ghi.
- History đủ 83 ngày cuối tháng, 39 quận và hai nhóm sử dụng; không trùng/thiếu khóa.
- Số lượng hữu hạn, không âm, nguyên; BEV + PHEV = EV, EV + non-EV = tổng và tỷ lệ đầu vào nhất quán.
- Phạm vi quận của hai bộ khớp nhau; snapshot có đủ 39 quận mỗi tháng.
- Mọi đường dẫn đầu ra khác nguồn, không trùng nhau và chưa tồn tại. Chương trình không sửa hai clean nguồn.

Điều kiện mẫu và mốc thời gian được triển khai cho phiên bản nghiên cứu đã chốt. Nếu cung cấp phiên bản dữ liệu khác, cần xem lại phạm vi thay vì bỏ qua lỗi kiểm tra để ép chương trình chạy.
