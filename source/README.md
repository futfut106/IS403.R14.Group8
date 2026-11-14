# Mã nguồn Python

Chứa logic xử lý và phân tích chính của đồ án. Hiện mới có cấu trúc thư mục; các module và lệnh chạy sẽ được bổ sung cùng từng gói triển khai.

| Thư mục | Vai trò | Liên hệ báo cáo |
|---|---|---|
| `preprocessing/` | Đọc hai raw, tạo hai clean và kiểm tra chất lượng | Phương pháp 3.3; triển khai 4.2.1 |
| `preparation/` | Tạo mẫu kiểm định, tổng hợp chuỗi tháng và xác định split | 3.4–3.5; triển khai 4.2.2 |
| `descriptive/` | Thống kê mô tả đặc điểm xe, địa bàn và thời gian | Triển khai 4.3; kết quả 5.1, 5.2, 5.4.1 |
| `inference/` | Kiểm định H1–H4, cỡ ảnh hưởng và độ nhạy | Triển khai 4.3; kết quả 5.3 |
| `forecasting/` | Đặc trưng, backtest, dự báo, chẩn đoán và đánh giá | Triển khai 4.4–4.5; kết quả 5.4.2–5.6 |
| `forecasting/configs/` | Giao thức chung và cấu hình/miền tìm kiếm của từng model | Thiết kế 3.7; triển khai 4.4 |
| `forecasting/models/` | Module Naive/Drift, ARIMA, SARIMA, Ridge, RF, SVR, XGBoost | Triển khai 4.4; kết quả 5.5 |

Luồng xử lý: `preprocessing` → `preparation` → `descriptive` / `inference` / `forecasting`. Các nhánh phân tích dùng dữ liệu thích hợp với cấp quan sát của mình.

Tên file theo chức năng, không theo số chương. Dùng đường dẫn theo repo hoặc tham số; notebook gọi lại logic từ đây. Đầu ra dữ liệu đặt trong `data/processed/`, bảng kết quả trong `results/`, hình trong `figures/`.

[Quay lại README tổng](../README.md)
