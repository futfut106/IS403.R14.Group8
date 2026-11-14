# Dữ liệu nghiên cứu

Thư mục lưu dữ liệu gốc, dữ liệu đã làm sạch và các bảng dẫn xuất dùng cho phân tích. Hiện mới khởi tạo cấu trúc, chưa bổ sung CSV.

## Phân loại

| Thư mục | Nội dung |
|---|---|
| `raw/` | Hai CSV gốc Population và History; giữ nguyên nội dung |
| `processed/` | Hai CSV clean, chuỗi tháng toàn bang và mẫu kiểm định được tạo từ clean |

## Tải và đặt dữ liệu

- [Dữ liệu raw](https://drive.google.com/drive/folders/1Bp67CYHvmcQcsPUAWl13ZHT_P1s3bWib?usp=sharing)
- [Dữ liệu clean](https://drive.google.com/drive/folders/1YvG-HDCbabV6dt6lo1BkaxUJd-wX4qTq?usp=sharing)

| Vị trí | Tên file |
|---|---|
| `raw/` | `Electric_Vehicle_Population_Data.csv` |
| `raw/` | `Electric_Vehicle_Population_Size_History_By_County.csv` |
| `processed/` | `EV_Population_Washington_Clean.csv` |
| `processed/` | `EV_Population_History_Washington_Clean.csv` |

Phiên bản nghiên cứu có Population raw 135.038 dòng/17 cột, clean 134.726 dòng/11 cột; History raw 19.700 dòng/10 cột, clean 6.474 dòng/10 cột. Số dòng không tính tiêu đề. Chuỗi toàn bang 83 tháng là dữ liệu dẫn xuất tiếp theo, không phải cấp quan sát của History clean.

Code làm sạch thuộc `source/preprocessing/`, code tạo mẫu và chuỗi tháng thuộc `source/preparation/`. Bảng kết quả thống kê/dự báo đặt trong `results/`, không trộn với dữ liệu đầu vào tại đây.

[Quay lại README tổng](../README.md)
