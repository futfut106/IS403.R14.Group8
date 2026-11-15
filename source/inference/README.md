# Kiểm định H1–H4 và phân tích độ nhạy

Gói đọc bốn mẫu do `source/preparation/` tạo, thực hiện các kiểm định đã thiết kế và xuất kết quả/cỡ ảnh hưởng. Không làm sạch lại raw hoặc fit mô hình dự báo.

## Mã nguồn

| File | Trách nhiệm |
|---|---|
| `range_tests.py` | H1 Mann–Whitney U, độ nhạy Model Year ≤2020; H2 Spearman toàn mẫu và riêng BEV/PHEV |
| `cafv_test.py` | H3 type × CAFV: mẫu nhãn đã biết và mẫu bổ sung giữ Unknown |
| `county_tests.py` | H4a cơ cấu BEV/PHEV theo quận; H4b EV/non-EV theo quận tại từng tháng |
| `contingency.py` | Kiểm tra đầu vào, Pearson chi-square, cỡ ảnh hưởng V và biểu diễn p-value dùng chung |
| `run_inference.py` | Kiểm tra nhất quán giữa các mẫu, điều phối toàn bộ phép thử, xuất bảng/hình và cấu hình thực thi |

## Đầu vào và cách chạy

Cần tạo đủ bốn file ngoài repo bằng gói preparation:

- `range_analysis_sample.csv`
- `cafv_analysis_sample.csv`
- `county_vehicle_type_counts.csv`
- `county_ev_snapshots.csv`

Cài dependency bằng `python -m pip install -r requirements.txt`. Từ thư mục gốc repo, thay đường dẫn mẫu trong ví dụ PowerShell:

```powershell
python source/inference/run_inference.py `
  --samples-dir "D:/du_lieu/preparation_output" `
  --results-dir "results/inference" `
  --figures-dir "figures/inference"
```

Có thể dùng `python -m source.inference.run_inference` với cùng tham số. Từng module kiểm định cũng có CLI riêng; dùng `--help`. Tên các file đầu ra phải chưa tồn tại; khi chạy lại, chọn thư mục mới để đối chiếu. Không sửa mẫu nguồn hoặc tự ghi đè kết quả đã lưu.

Các kiểm tra đầu vào bao gồm schema, kiểu cờ True/False, khóa, số đếm, tỷ lệ, điều kiện lọc và tính nhất quán giữa Population Range/CAFV/bảng quận. Không coi chuỗi chữ `False` là True bằng phép ép kiểu boolean tùy ý.

## Thiết kế và cỡ mẫu

| Kiểm định | Mẫu chính | Độ nhạy/phân nhóm |
|---|---|---|
| H1 | 77.857 Range hợp lệ: 46.806 BEV, 31.051 PHEV | Giới hạn cả hai nhóm ở Model Year ≤2020, còn 65.779 dòng |
| H2 | Cặp Model Year/Range hợp lệ, 77.857 dòng | Tính riêng BEV và PHEV; cỡ mẫu được lưu theo nhóm |
| H3 | Loại đúng nhãn Unknown, còn 77.858 dòng; bảng 2×2 | Giữ Unknown, đủ 134.726 dòng; bảng 2×3 |
| H4a | Đủ 39 quận, tổng 134.726 EV; bảng 39×2 | Quận có ≥30 EV: 36 quận, tổng 134.683 EV; không xóa quận khỏi dữ liệu chuẩn |
| H4b | History 11/2023: 39 quận, tổng 5.954.054 phương tiện | Chạy riêng 01/2017: 39 quận, tổng 5.940.783 phương tiện |

Cỡ mẫu trên thuộc phiên bản nghiên cứu đã chốt; các số thực chạy được lưu trong CSV. Mẫu CAFV chính khác mẫu Range một bản ghi: H3 lọc theo nhãn CAFV, không lọc theo Range. `n` của H4b là tổng EV + non-EV, không phải số quận hoặc số dòng snapshot.

### H1 và H2

- Mann–Whitney U hai phía dùng xấp xỉ chuẩn có điều chỉnh ties và hiệu chỉnh liên tục. `statistic` là U của nhóm BEV.
- Xác suất ưu thế `A=U_BEV/(n_BEV×n_PHEV)` có nửa trọng số cho ties. Rank-biserial `2A−1`: dấu dương theo chiều BEV lớn hơn PHEV.
- Không diễn giải Mann–Whitney chỉ là kiểm định trung vị nếu chưa có điều kiện hình dạng phân bố thích hợp. Median/Q1/Q3/IQR dùng mô tả, nội suy quantile tuyến tính.
- Spearman hai phía dùng p xấp xỉ t của SciPy; các mẫu thực tế đều lớn. Rho là cỡ liên hệ theo hạng, không phải hệ số tác động nhân quả.
- Trường hợp nhóm quá nhỏ hoặc biến hằng làm rho không xác định được ghi trạng thái chưa tính, không thay bằng rho/p bằng 0.

### H3, H4a và H4b

- Pearson chi-square dùng `correction=False`, không áp Yates; lưu cả observed và expected.
- Cramér’s V = `sqrt(chi_square / [N×min(r−1,c−1)])`, N là tổng tần số quan sát trong bảng.
- H4a chính có expected nhỏ nên dùng Monte Carlo có biên cố định: SciPy `chi2_contingency` + `MonteCarloMethod`, 99.999 lần, batch 1.000, seed 42. Phương pháp lấy mẫu dùng `random_table` của SciPy, không mô phỏng độc lập từng ô.
- H4a độ nhạy kiểm tra lại expected; chỉ dùng p chi-square xấp xỉ khi mọi expected ≥5. Nếu điều kiện này không đạt thì dùng Monte Carlo, không tự bỏ qua cảnh báo bảng thưa.
- H4b tạo bảng EV/non-EV từ từng snapshot riêng biệt. Không ghép hai tháng thành một mẫu phương tiện độc lập.
- Lưu bậc tự do lý thuyết `(r−1)(c−1)`. SciPy có thể trả `dof=NaN` khi dùng resampling; không dùng NaN đó làm bậc tự do của bảng.

## P-value và kết luận

Mức ý nghĩa danh nghĩa 0,05. Các p-value là từng phép thử chưa điều chỉnh đa kiểm định; không tuyên bố kiểm soát FWER/FDR. Phân tích độ nhạy không dùng để chọn kết luận có lợi.

- `p_value` giữ số chưa làm tròn khi biểu diễn được bằng số thực.
- Nếu thư viện trả số 0 do giới hạn số học, để trống `p_value`, đặt `p_numerical_underflow=True`, lưu giới hạn bảo thủ `p_value_upper_bound=1e-300` và ghi `p_display=<1e-300 (numerical underflow)`. Đây không phải p bằng 0 hay một p chính xác được tính thêm bằng số học độ chính xác cao.
- Với Monte Carlo, mức phân giải là `1/(99999+1)=0,00001`. Nếu kết quả đạt mức thấp nhất, `mc_at_resolution_limit=True`; đây là giới hạn mô phỏng của ước lượng, **không phải cận trên của p thật** và không suy p nhỏ hơn mức này.
- `reject_h0` theo alpha danh nghĩa; luôn đọc cùng statistic, p_method, effect_size, n và điều kiện áp dụng. Không đồng nhất có ý nghĩa thống kê với quan trọng về kinh doanh.

## Bảy CSV và một JSON

| File trong results-dir | Nội dung |
|---|---|
| `range_tests.csv` | Hai kết quả H1 và ba kết quả H2, cỡ mẫu, p và effect; H1 có median/IQR mỗi loại |
| `range_year_summary.csv` | n, median, Q1/Q3 Range theo loại xe và Model Year, dùng cho hình minh họa |
| `cafv_tests.csv` | H3 chính và độ nhạy; statistic, df, V và điều kiện expected |
| `cafv_contingency.csv` | Tần số observed/expected dạng dài của hai bảng CAFV |
| `county_tests.csv` | H4a chính/độ nhạy, H4b hai mốc; phương pháp p và thông số Monte Carlo khi áp dụng |
| `county_contingency.csv` | Observed/expected của từng bảng quận, mẫu và tháng được nhận diện riêng |
| `hypothesis_summary.csv` | Tổng hợp 11 dòng phép thử/phân nhóm; không phải 11 giả thuyết độc lập mới |
| `inference_settings.json` | Môi trường thực chạy, tham số kiểm định, định nghĩa mẫu, seed/số mô phỏng và giới hạn diễn giải |

Chi tiết bảng chéo có nhãn hàng/cột và tổng biên để truy nguồn statistic. Không so sánh trực tiếp độ lớn rank-biserial, rho và V như thể cùng một thước đo.

## Ba hình hỗ trợ

- `range_by_model_year.png`: median và dải Q1–Q3 theo năm cho BEV/PHEV; dải không phải khoảng tin cậy.
- `cafv_by_vehicle_type.png`: tỷ trọng CAFV theo loại xe với cả Unknown; mẫu số là từng loại xe.
- `county_vehicle_type_share.png`: cơ cấu BEV/PHEV trong EV của từng quận, có n và đánh dấu quận dưới 30 EV.

Hình chỉ minh họa mẫu/kết cấu, không thay kết quả kiểm định. Không bổ sung boxplot trùng với hình Range đã có ở gói mô tả.

## Phạm vi diễn giải

Các bản ghi đăng ký hành chính không phải mẫu ngẫu nhiên được thiết kế để suy rộng đến mọi thời kỳ hoặc mọi bang. Range bị thiếu không đồng đều theo loại xe/năm, nên phân tích trên Range hợp lệ có giới hạn đại diện. Không kết luận cơ chế missing MAR/MNAR chỉ từ các tỷ lệ thiếu.

CAFV là nhãn hành chính; liên hệ với loại xe không chứng minh chính sách tạo ra khác biệt. Hai snapshot History được phân tích riêng; dữ liệu lặp theo tháng và kết cấu không gian cần được lưu ý khi diễn giải các giả định độc lập. Không suy hiệu quả kinh doanh hoặc tác động nhân quả từ p-value nhỏ.

## Tài liệu API

- [SciPy Mann–Whitney U](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)
- [SciPy Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html)
- [SciPy chi2_contingency](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.contingency.chi2_contingency.html)
- [SciPy MonteCarloMethod](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.MonteCarloMethod.html)
