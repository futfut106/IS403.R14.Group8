# IS403.R14 — Group 8

## Phân tích đội xe điện và dự báo quy mô xe điện tại Washington

Repository phục vụ đồ án của **Nhóm 8**, môn **IS403**, lớp **R14**. Đề tài sử dụng hai bộ dữ liệu Population và History để phân tích đặc điểm, phân bố của đội xe điện tại bang Washington và so sánh các phương pháp dự báo quy mô EV toàn bang.

### Trạng thái repository

Repo đang ở giai đoạn khởi tạo cấu trúc. Mã nguồn, dữ liệu, bảng kết quả, biểu đồ và báo cáo sẽ được bổ sung theo từng bước sau khi chuẩn hóa. Các thư mục dưới đây xác định cách tổ chức sản phẩm; chưa thể chạy toàn bộ quy trình chỉ từ bản khởi tạo này.

## 1. Mục tiêu và phạm vi

- Mô tả cơ cấu xe điện theo BEV/PHEV, CAFV, hãng xe, năm mẫu xe và Electric Range.
- Phân tích phân bố theo quận, thành phố và tỷ lệ EV trong tổng số phương tiện ở cùng thời điểm.
- Thực hiện thống kê suy diễn H1–H4 cùng cỡ ảnh hưởng và phân tích độ nhạy.
- Tổng hợp chuỗi EV Total theo tháng, triển khai dự báo và đánh giá các phương pháp trên cùng cửa sổ kiểm tra.
- Thảo luận kết quả và hàm ý cho việc theo dõi thị trường, lập kế hoạch dịch vụ xe điện trong phạm vi dữ liệu cho phép.

Population là dữ liệu ở cấp phương tiện, dùng cho phân tích cắt ngang. History là dữ liệu theo tháng–quận–nhóm sử dụng, dùng để phân tích tỷ lệ EV và tạo chuỗi thời gian. Hai bộ dữ liệu có cấp quan sát khác nhau; không ghép các dòng của chúng như thể cùng đại diện cho từng xe tại cùng một thời điểm.

Biến dự báo là **số EV hiện có ở cuối tháng**, đơn vị xe. Thay đổi giữa các tháng là thay đổi ròng của đội xe, không được diễn giải trực tiếp thành doanh số. Dữ liệu không trực tiếp đo nhu cầu điện, hành vi sạc, số trạm cần xây hoặc tác động nhân quả của chính sách.

## 2. Dữ liệu nghiên cứu

### Nguồn tải dữ liệu

- [Hai file dữ liệu gốc — raw](https://drive.google.com/drive/folders/1Bp67CYHvmcQcsPUAWl13ZHT_P1s3bWib?usp=sharing)
- [Hai file dữ liệu đã làm sạch — clean](https://drive.google.com/drive/folders/1YvG-HDCbabV6dt6lo1BkaxUJd-wX4qTq?usp=sharing)

Các liên kết cung cấp phiên bản dữ liệu dùng cho đồ án. Trong quá trình làm việc tại máy, đặt dữ liệu theo cấu trúc sau; CSV hiện chưa được đưa vào repo mới.

| Bộ dữ liệu | File gốc trong `data/raw/` | File clean trong `data/processed/` | Kích thước raw → clean |
|---|---|---|---|
| Population | `Electric_Vehicle_Population_Data.csv` | `EV_Population_Washington_Clean.csv` | 135.038 × 17 → 134.726 × 11 |
| History | `Electric_Vehicle_Population_Size_History_By_County.csv` | `EV_Population_History_Washington_Clean.csv` | 19.700 × 10 → 6.474 × 10 |

Kích thước được ghi theo **số dòng dữ liệu × số cột**, không tính dòng tiêu đề. Đây là quy mô của phiên bản nghiên cứu, không phải số liệu cập nhật liên tục từ cổng dữ liệu trực tuyến. Phạm vi sau lọc là `State = WA`.

Nếu file tải về mang hậu tố như `EV_Population_Washington_Clean (1).csv`, thống nhất tên làm việc thành `EV_Population_Washington_Clean.csv`; việc đổi tên không làm thay đổi nội dung dữ liệu.

### Dữ liệu dẫn xuất

`data/processed/` còn chứa các bảng do chương trình chuẩn bị dữ liệu tạo ra:

- `statewide_monthly.csv`: chuỗi toàn bang 83 tháng, từ 01/2017 đến 11/2023.
- Các mẫu phục vụ kiểm định Range, CAFV, cơ cấu BEV/PHEV và tỷ lệ EV theo quận.

History clean vẫn giữ 6.474 quan sát chi tiết. Chuỗi 83 tháng là sản phẩm tổng hợp tiếp theo, không thay thế ý nghĩa của bộ clean. Tỷ lệ EV toàn bang được tính từ tổng số EV và tổng phương tiện, không lấy trung bình đơn giản tỷ lệ của các quận.

## 3. Cấu trúc thư mục

```text
IS403.R14.Group8/
├── README.md
├── data/
│   ├── raw/
│   └── processed/
├── source/
│   ├── preprocessing/
│   ├── preparation/
│   ├── descriptive/
│   ├── inference/
│   └── forecasting/
│       ├── configs/
│       └── models/
├── notebooks/
├── results/
│   ├── preprocessing/
│   ├── preparation/
│   ├── descriptive/
│   ├── inference/
│   └── forecasting/
├── figures/
│   ├── methodology/
│   ├── descriptive/
│   ├── inference/
│   └── forecasting/
├── reports/
└── docs/
```

| Vị trí | Nội dung và trách nhiệm |
|---|---|
| `data/raw/` | Hai CSV gốc, giữ nguyên nội dung |
| `data/processed/` | Hai CSV clean và dữ liệu dẫn xuất dùng cho phân tích/dự báo |
| `source/preprocessing/` | Làm sạch hai raw để tạo hai clean; kiểm tra chất lượng đầu ra |
| `source/preparation/` | Tạo mẫu kiểm định, tổng hợp chuỗi tháng và xác định train/test |
| `source/descriptive/` | Thống kê mô tả đặc điểm xe, địa bàn và diễn biến theo thời gian |
| `source/inference/` | Kiểm định H1–H4, cỡ ảnh hưởng, kiểm tra điều kiện và độ nhạy |
| `source/forecasting/` | Tạo đặc trưng, lựa chọn cấu hình, dự báo, chẩn đoán và đánh giá |
| `source/forecasting/configs/` | Giao thức chung và cấu hình/miền tìm kiếm của từng mô hình |
| `source/forecasting/models/` | Module của từng phương pháp dự báo |
| `notebooks/` | Trình bày phân tích tương tác, gọi lại các hàm trong `source/` |
| `results/` | Bảng kết quả CSV, cấu hình đã chọn và ghi nhận thực nghiệm; chia theo nhóm công việc |
| `figures/` | Sơ đồ và biểu đồ dùng trong báo cáo; chia theo nhóm nội dung |
| `reports/` | Báo cáo Word, PDF và mục lục chính thức |
| `docs/` | Từ điển dữ liệu, hướng dẫn chạy, kế hoạch và ánh xạ báo cáo với code/bảng/hình |

`requirements.txt` và `.gitignore` sẽ được bổ sung khi thiết lập môi trường và đưa các gói mã nguồn vào repo. Không liệt kê chúng như những file đã có ở bản khởi tạo.

## 4. Luồng triển khai

1. **Tiền xử lý:** đọc hai raw, lọc phạm vi, chọn thuộc tính và xử lý kiểu dữ liệu/giá trị thiếu theo quy tắc của từng bộ; xuất hai clean và tóm tắt chất lượng. Clean là đầu ra, không phải đầu vào bắt buộc của bước này.
2. **Chuẩn bị dữ liệu:** từ clean, tạo mẫu phân tích, tổng hợp chuỗi tháng và chia dữ liệu theo thời gian.
3. **Thống kê mô tả:** tạo bảng tần số, tỷ lệ, thống kê Range, phân bố không gian và diễn biến chuỗi.
4. **Thống kê suy diễn:** thực hiện H1–H4 trên đúng mẫu và cấp quan sát, báo cáo cỡ ảnh hưởng/độ nhạy cùng p-value.
5. **Dự báo:** lựa chọn cấu hình trong tập huấn luyện, dự báo 12 bước từ cùng một gốc và đánh giá bằng cùng công thức.
6. **Tổng hợp:** tạo bảng so sánh, phân tích sai số và xuất hình/bảng cho báo cáo.

CSV sạch và mẫu phân tích đặt trong `data/processed/`. Bảng thống kê, kiểm định, CV và dự báo đặt trong `results/`; biểu đồ đặt trong `figures/`.

## 5. Thiết kế phân tích và dự báo

### Thống kê suy diễn

| Giả thuyết | Nội dung phân tích | Phương pháp dự kiến theo thiết kế |
|---|---|---|
| H1 | So sánh Electric Range giữa BEV và PHEV | Mann–Whitney U và cỡ ảnh hưởng |
| H2 | Liên hệ giữa Model Year và Electric Range | Tương quan Spearman; xem xét toàn mẫu và theo loại xe |
| H3 | Liên hệ giữa loại xe và trạng thái CAFV | Chi-square, Cramér's V và phân tích độ nhạy nhãn Unknown |
| H4a | Cơ cấu BEV/PHEV giữa các quận | Chi-square với phương án p Monte Carlo và độ nhạy phù hợp tần số kỳ vọng |
| H4b | So sánh tỷ lệ EV giữa các quận tại cùng tháng | Kiểm định bảng EV/non-EV; phân tích riêng 11/2023 và kỳ bổ sung 01/2017 |

Kết quả phải nêu rõ mẫu, giả định, mức ý nghĩa, cỡ ảnh hưởng và giới hạn diễn giải. Không coi các tháng lặp lại là các phương tiện độc lập; không suy nhân quả từ tương quan hoặc khác biệt thống kê.

### Dự báo chuỗi thời gian

| Thành phần | Thiết kế |
|---|---|
| Biến đích | EV Total toàn bang theo tháng |
| Tập huấn luyện | 01/2017–11/2022, 71 tháng |
| Tập kiểm tra | 12/2022–11/2023, 12 tháng |
| Gốc dự báo | Cuối 11/2022, dự báo 12 bước |
| Phương pháp nền | Naive, Drift |
| Mô hình thống kê | ARIMA, SARIMA |
| Mô hình học máy | Ridge, Random Forest, SVR, XGBoost |
| Đặc trưng ML | Tăng trưởng log quá khứ: lag 1/2/3 và trung bình trượt 3/6 |
| Chỉ tiêu | RMSE, MAE, sMAPE và Bias; Bias = actual − prediction |

Tập kiểm tra dùng để đánh giá cuối. Việc tạo đặc trưng, chuẩn hóa và chọn cấu hình chỉ sử dụng lịch sử cho phép tại mỗi thời điểm; ML dự báo nhiều bước theo cơ chế đệ quy. Tính chỉ tiêu từ dự báo chưa làm tròn và chỉ làm tròn khi trình bày. Chỉ báo cáo khoảng dự báo khi có phương pháp tính và đầu ra tương ứng.

## 6. Liên hệ với cấu trúc báo cáo

| Chương | Vai trò | Thành phần repo hỗ trợ |
|---|---|---|
| 1 | Giới thiệu, câu hỏi và phạm vi | Báo cáo, mô tả nguồn và phạm vi dữ liệu |
| 2 | Cơ sở lý thuyết và nghiên cứu liên quan | Báo cáo và tài liệu tham khảo |
| 3 | Dữ liệu, phương pháp và thiết kế nghiên cứu | Từ điển dữ liệu, sơ đồ, giao thức phân tích/dự báo |
| 4 | Triển khai các phương pháp đã thiết kế | `source/`, cấu hình và hướng dẫn thực thi |
| 5 | Kết quả, so sánh và thảo luận | `results/`, `figures/`, notebook trình bày |
| 6 | Kết luận, hạn chế và kiến nghị | Tổng hợp từ kết quả nghiên cứu |

Đặt tên file theo chức năng, ví dụ `clean_population.py`, `monthly_trends.py`, `forecast_svr.csv`. Số chương, bảng và hình được ghi trong tài liệu ánh xạ ở `docs/`, để tên chương trình không phụ thuộc thứ tự chương.

## 7. Hướng dẫn sử dụng và quy ước làm việc

Hiện mới có cấu trúc thư mục và README; chưa có lệnh chạy pipeline khả dụng trong repo này. Khi bổ sung từng gói, tài liệu sẽ ghi rõ dependency, lệnh chạy từ thư mục gốc, đường dẫn đầu vào và danh sách đầu ra thực tế.

- Giữ nguyên dữ liệu trong `data/raw/`; ghi đầu ra vào thư mục được quy định.
- Dùng đường dẫn tương đối theo repo hoặc tham số đầu vào, tránh gắn code với đường dẫn máy cá nhân.
- Tập trung logic xử lý trong `source/`; notebook gọi lại logic đó để trình bày.
- Sinh bảng/hình từ code và kết quả lưu, tránh chép cứng số liệu trong chương trình dựng báo cáo.
- Duy trì một bản báo cáo chính và bảng ánh xạ mục báo cáo → code → input → output.
- Không đưa file khóa Word, cache, thông tin đăng nhập và file tạm vào Git.
- Cập nhật README, hướng dẫn chạy và mapping khi thay đổi tên file hoặc giao diện dữ liệu.
- Mỗi commit tập trung một phần công việc đã kiểm tra; chuyển từng gói vào repo theo tiến độ được thống nhất.

Các phần mô tả thiết kế trong README là phạm vi triển khai đã thống nhất, không thay cho bằng chứng thực thi hoặc kết quả cuối. Trạng thái và hướng dẫn sẽ được cập nhật cùng từng gói mã nguồn.
