# Dữ liệu nghiên cứu

Thư mục này giới thiệu dữ liệu và cung cấp link tải Google Drive. Repo không lưu CSV trong `data/`; thư mục chỉ có README này.

## Link tải

- [Dữ liệu gốc — raw](https://drive.google.com/drive/folders/1Bp67CYHvmcQcsPUAWl13ZHT_P1s3bWib?usp=sharing)
- [Dữ liệu đã làm sạch — clean](https://drive.google.com/drive/folders/1YvG-HDCbabV6dt6lo1BkaxUJd-wX4qTq?usp=sharing)

## Hai bộ dữ liệu

| Bộ dữ liệu | File raw | File clean | Kích thước raw → clean |
|---|---|---|---|
| Population | `Electric_Vehicle_Population_Data.csv` | `EV_Population_Washington_Clean.csv` | 135.038 × 17 → 134.726 × 11 |
| History | `Electric_Vehicle_Population_Size_History_By_County.csv` | `EV_Population_History_Washington_Clean.csv` | 19.700 × 10 → 6.474 × 10 |

Kích thước ghi theo số dòng dữ liệu × số cột, không tính tiêu đề, cho phiên bản nghiên cứu. Population phục vụ phân tích cắt ngang; History giữ cấp tháng–quận–nhóm sử dụng. Sau làm sạch, phạm vi là `State = WA`.

## Cách sử dụng

Tải CSV về một vị trí phù hợp trên máy và cấu hình đường dẫn khi chạy chương trình. Giữ nguyên raw; ghi clean và dữ liệu dẫn xuất sang vị trí đầu ra riêng. Không bắt buộc tạo `raw/` hoặc `processed/` bên trong repo.

Nếu tên tải xuống có hậu tố `(1)`, có thể thống nhất tên file làm việc mà không thay đổi nội dung. Tên clean trong bảng là tên chuẩn sử dụng trong tài liệu.

Code làm sạch thuộc `source/preprocessing/`; code tạo mẫu và chuỗi tháng thuộc `source/preparation/`. Clean là đầu ra của phép xử lý raw, không phải đầu vào bắt buộc để làm sạch. Chuỗi toàn bang 83 tháng từ 01/2017–11/2023 là dữ liệu tổng hợp tiếp theo từ History clean.

Hướng dẫn tham số và vị trí lưu dữ liệu dẫn xuất sẽ được bổ sung cùng mã nguồn. Bảng thống kê/kiểm định/dự báo được lưu trong `results/`, hình trong `figures/`.

[Quay lại README tổng](../README.md)
