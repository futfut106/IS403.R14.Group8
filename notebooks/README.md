# Notebook demo phân tích và dự báo EV Washington

Các notebook dùng để chạy từng cell khi trình bày project. Thuật toán phân tích dùng lại từ `source/`; notebook bổ sung các bảng trung gian, hình và lời giải thích. Không thay thế các runner chính thức và không thay đổi dữ liệu nguồn.

## Danh sách và thứ tự xem

| Notebook | Nội dung |
|---|---|
| `preprocessing_demo.ipynb` | Hai raw → hai clean; phạm vi WA, giữ cột, 0→thiếu, ngày/kiểu số, kiểm tra chất lượng và bảng trước–sau |
| `preparation_demo.ipynb` | Hai clean → năm bảng dẫn xuất, mẫu H1–H4, chuỗi 83 tháng và split 71/12 |
| `descriptive_demo.ipynb` | Đặc điểm xe, địa bàn, mẫu số và diễn biến theo tháng; tính bảng/vẽ hình mới |
| `hypothesis_tests_demo.ipynb` | H1–H4, mẫu chính/độ nhạy, expected, cỡ ảnh hưởng và Monte Carlo |
| `statistical_forecasting_demo.ipynb` | Chẩn đoán train, Naive/Drift, sáu ARIMA, ba SARIMA, chọn cấu hình, forecast và metric |
| `ridge_demo.ipynb` | Feature → CV → chọn alpha → scaler → fit → dự báo đệ quy → metric |
| `random_forest_demo.ipynb` | Tương tự cho RF; giữ nguyên thang X, chuẩn hóa nhãn |
| `svr_demo.ipynb` | Tương tự cho SVR; quan sát scaler X/nhãn và support vectors |
| `xgboost_demo.ipynb` | Tương tự cho XGBoost; CPU hist, seed và config thực chạy |
| `forecast_comparison_demo.ipynb` | Căn 96 forecast đã khóa, tính lại metric/cải thiện baseline, coverage, cumulative metric và bốn hình |

`demo_support.py` chỉ hỗ trợ đường dẫn, hiển thị, biểu đồ demo và xuất an toàn. Công thức/fit/kiểm định/lựa chọn cấu hình nằm trong source. Các view trước–sau của preprocessing nhằm giải thích hàm source, không tạo một pipeline clean riêng.

## Mở và chạy trong VS Code

1. Mở **gốc repo** trong VS Code. Cài extension Python và Jupyter nếu chưa có.
2. Dùng Python 3.12.10 đã cài trên máy. Nếu cần cài các gói còn thiếu, chạy ở Terminal của đúng Python đó:

```powershell
python -m pip install -r notebooks/requirements-demo.txt
```

3. Mở `.ipynb`, chọn Python 3.12.10 đang dùng trên máy. Không cần tạo môi trường hoặc đăng ký kernel riêng. Ô đầu in `sys.executable` để kiểm tra đúng Python.
4. Chạy cell thiết lập đầu tiên; xem bảng đường dẫn và phiên bản thư viện. Sửa đường dẫn nếu mục đầu vào có `exists=False`.
5. Dùng **Shift+Enter** để chạy từng cell. Khi kiểm tra từ đầu, dùng **Restart Kernel → Run All**, không chỉ chạy các cell cuối trên biến cũ còn trong RAM.

Bản local hiện đã được thực thi và **lưu đầy đủ output/execution count** để kiểm chứng từng cell. Khi cần quay một lượt mới, dùng Restart Kernel / Run All. Những assertion đối chiếu giúp phát hiện sai dữ liệu/môi trường; không sửa output để vượt kiểm tra. Hình hiển thị ngay trong notebook.

## Đường dẫn dữ liệu

Mặc định dành cho cấu trúc local đang dùng: gốc dữ liệu là thư mục chứa `GitHub/`, tức hai cấp phía trên repo. Raw và clean nằm ở các vị trí đã cung cấp; preparation mặc định là `Du_lieu_dan_xuat/preparation_20261115`. `demo_support.configure` hiển thị toàn bộ đường dẫn để kiểm tra.

Trên máy khác, sửa trường `PATHS` ngay sau `PATHS = configure(PROJECT_ROOT)` trong cell thiết lập. Ví dụ:

```python
PATHS.population_raw = Path('D:/du_lieu/Electric_Vehicle_Population_Data.csv')
PATHS.history_raw = Path('D:/du_lieu/Electric_Vehicle_Population_Size_History_By_County.csv')
PATHS.population_clean = Path('D:/du_lieu/EV_Population_Washington_Clean.csv')
PATHS.history_clean = Path('D:/du_lieu/EV_Population_History_Washington_Clean.csv')
PATHS.preparation = Path('D:/du_lieu/preparation_output')
```

Cũng có thể đặt các biến môi trường trước khi khởi động kernel:

| Biến | Chức năng |
|---|---|
| `EV_DATA_ROOT` | Gốc thư mục dữ liệu; dùng dựng đường dẫn mặc định |
| `EV_POPULATION_RAW`, `EV_HISTORY_RAW` | Hai CSV raw |
| `EV_POPULATION_CLEAN`, `EV_HISTORY_CLEAN` | Hai CSV clean |
| `EV_PREPARATION_DIR` | Thư mục chứa năm CSV preparation |
| `EV_DEMO_ROOT` | Gốc output demo, bắt buộc ngoài repo |

Các notebook không chia sẻ biến RAM. Mặc định notebook phía sau đọc clean/preparation đã lưu của nghiên cứu, không tự dò output mới nhất của notebook trước. Nếu muốn chạy liền mạch từ raw vừa demo, sau khi notebook preprocessing/preparation xuất xong, lấy đúng đường dẫn `OUT` và gán vào các trường PATHS của notebook phía sau. Không cần sửa các thuật toán.

## Output và dữ liệu tham chiếu

- Mỗi notebook tạo một thư mục mới có thời gian và mã ngẫu nhiên, mặc định trong `Du_lieu_dan_xuat/notebook_demo/`, ngoài repo.
- Không ghi vào `results/`, `figures/` chính thức hoặc ghi đè hai clean. Cell xuất CSV/JSON giữ nguyên file nếu nội dung đã có giống hệt, chặn nếu nội dung khác; Restart/Run All tạo OUT mới cho một lượt đầy đủ.
- Notebook mô hình đọc `results/forecasting/` đã lưu để đối chiếu dự báo; notebook so sánh cần toàn bộ forecast, best metadata, CV và metric của các mô hình. Cần có đủ các file gói 1–5 ở local; khi dùng bản clone mới, phải merge đủ phần liên quan trước.
- Notebook preprocessing gọi hàm raw → clean trước rồi mới đối chiếu với clean có sẵn. Clean đối chiếu không được dùng để tạo đầu ra.
- Các notebook phân tích gọi hàm source và tính lại kết quả. Đối chiếu số học dùng tolerance để không coi chênh lệch dấu phẩy động nhỏ là khác nghiên cứu.
- Nếu khác phiên bản dữ liệu/thư viện, assertion có thể dừng. Kiểm tra đúng đầu vào, version và config; không thay ID hoặc số liệu bằng tay cho khớp một bảng cũ.

## Chạy đầy đủ và quay video

- Mặc định `RUN_GRID_SEARCH=True` trong bốn notebook ML, `RUN_SARIMA_CV=True` trong notebook thống kê: các cell này **thực sự chạy lại** validation.
- Đặt cờ thành False nếu muốn rút thời gian quay: cell sẽ in rõ đang đọc kết quả validation đã lưu, **không** gọi đó là vừa chạy grid. Mô hình đã chọn vẫn được fit lại trên full train và sinh dự báo mới ở các cell sau.
- H4a vẫn dùng 99.999 mô phỏng, seed 42 theo source. Không giảm thông số rồi đọc kết quả cũ. Có thể rút gọn đoạn chờ trong video và ghi rõ.
- Thời gian 15–20 phút không đủ quay mọi cell của cả 10 notebook. Chọn các cell tiêu biểu: preprocessing trước–sau; split; một kết quả kiểm định; feature/scaler/trace; cấu hình và bảng so sánh.
- Không dùng full-series scaler, không cập nhật actual test khi dự báo đệ quy, không chọn lại config theo test. Đọc cỡ ảnh hưởng cùng p và giới hạn dữ liệu.

Các notebook này là **Python**. Chúng không bổ sung code/output R; yêu cầu R trong hướng dẫn nộp vẫn cần được xử lý riêng.

## Phạm vi thay đổi

Chỉ thêm các notebook và file hỗ trợ demo trong thư mục này; không đổi thuật toán hoặc các bảng/hình nghiên cứu của source. Không cần đưa dữ liệu, thư viện cài đặt, output demo hoặc `.ipynb_checkpoints/` lên GitHub.

## Lượt chạy local đã lưu

Ngày 16/11/2026, toàn bộ 10 notebook được chạy từ đầu bằng Python 3.12.10 hiện tại trên máy, pandas 3.0.5 và NumPy 2.5.3. Cả 87 ô code có output; các bảng và hình được lưu ngay trong notebook. Có thể bấm ▶ từng ô theo thứ tự để demo trực tiếp.

Các bảng trong `results/` và hình trong `figures/` của bản local đã được sinh lại bằng source với cùng bộ thư viện. Đối chiếu notebook sử dụng bộ kết quả này; các số trong báo cáo cũ không được dùng làm chuẩn. Không đổi thuật toán, dữ liệu gốc, cấu hình mô hình hoặc nới ngưỡng đối chiếu để làm phép kiểm tra đạt.

Khi mở lại file đã sửa, nạp bản từ ổ đĩa để tránh lưu đè từ tab cũ. Chạy từ ô thiết lập để có `PATHS`, `OUT` và các biến trung gian. CSV/JSON đã tồn tại với nội dung giống hệt được giữ nguyên; nội dung khác vẫn báo xung đột. Chạy lại ô tạo OUT để bắt đầu một lượt xuất mới.
