# Bảng kết quả và ghi nhận thực nghiệm

Lưu đầu ra dạng CSV/JSON được tạo từ mã nguồn. Hiện chưa có kết quả phân tích trong repo này.

| Thư mục | Nội dung sẽ lưu |
|---|---|
| `preprocessing/` | Tóm tắt chất lượng: số dòng/cột trước và sau xử lý, missing, khóa và các kiểm tra dữ liệu |
| `preparation/` | Tóm tắt mẫu kiểm định, cấu trúc chuỗi tháng và train/test |
| `descriptive/` | Bảng tần số, tỷ lệ, thống kê Range, địa bàn và tăng trưởng |
| `inference/` | Thống kê kiểm định, p-value, cỡ ảnh hưởng, cỡ mẫu, độ nhạy và bảng chéo |
| `forecasting/` | Dự báo, cấu hình đã chọn, CV/bảng ứng viên khi áp dụng, chỉ tiêu, chẩn đoán và bảng so sánh |

Các bảng phải truy được tới script và dữ liệu đầu vào; không sửa tay kết quả để khớp báo cáo. Dự báo và metric lưu đủ độ chính xác, chỉ làm tròn khi trình bày. Các model được so sánh trên cùng ngày và actual; ghi rõ origin, horizon, config và công thức đánh giá.

Dữ liệu clean/mẫu đầu vào thuộc `data/processed/`; hình thuộc `figures/`; báo cáo thuộc `reports/`.

[Quay lại README tổng](../README.md)
