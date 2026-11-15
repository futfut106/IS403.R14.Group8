# Dự báo quy mô xe điện

Các chương trình nhận `statewide_monthly.csv` do preparation tạo, dùng chung metric và ranh giới thời gian. `run_forecast.py` triển khai Naive/Drift, ARIMA và SARIMA; `run_ml_forecast.py` triển khai Ridge, Random Forest, SVR và XGBoost.

## Chạy từ gốc repo

Cài dependency bằng `python -m pip install -r requirements.txt`. Thay đường dẫn dữ liệu trong ví dụ PowerShell:

```powershell
python source/forecasting/run_forecast.py `
  --series "D:/du_lieu/preparation_output/statewide_monthly.csv" `
  --results-dir "results/forecasting" `
  --figures-dir "figures/forecasting"
```

Có thể dùng `python -m source.forecasting.run_forecast` với cùng tham số. Phải có đủ tám cột do preparation tạo; không dùng bản bốn cột cũ rồi tự suy thêm biến. Tên file đầu ra phải chưa tồn tại. Khi chạy lại để đối chiếu, chọn hai thư mục đầu ra mới; chương trình không tự ghi đè.

Không đặt dữ liệu vào `data/`; CSV nguồn được tải/tạo ở đường dẫn ngoài repo. Tham số `--series` bắt buộc nên không phụ thuộc máy cá nhân.

## Tổ chức code

| File/thư mục | Vai trò |
|---|---|
| `protocol.py`, `configs/protocol.json` | Schema chuỗi, lịch train/test, horizon, fold, đơn vị và quy ước đánh giá |
| `metrics.py` | RMSE, MAE, sMAPE, Bias; không làm tròn trước lưu/tính/chọn |
| `features.py` | Tăng trưởng log, năm feature từ quá khứ, phép dự báo đệ quy và đổi ngược về số xe |
| `backtest.py` | Expanding-window validation bằng callback fit/forecast, ghi điểm, cảnh báo và trạng thái thật |
| `models/baselines.py` | Naive và Drift |
| `models/arima.py`, `models/sarima.py` | Giao diện fit/forecast của từng họ mô hình |
| `models/statistical.py` | Fit state-space và phân phối dự báo; ghi hội tụ, covariance và nghiệm |
| `configs/arima.json`, `configs/sarima.json` | Danh sách ứng viên và cấu hình optimizer/trend/ràng buộc |
| `diagnostics.py` | ADF/KPSS, ACF/PACF, innovations, Ljung–Box, Jarque–Bera và hệ số |
| `run_forecast.py` | Điều phối chọn nội train, dự báo test, chấm điểm và xuất sản phẩm |

## Dữ liệu và cách chấm điểm

- 83 tháng cuối tháng, 01/2017–11/2023; biến đích là EV Total hiện có, không phải doanh số.
- Train 71 tháng 01/2017–11/2022; test 12 tháng 12/2022–11/2023.
- Gốc cố định cuối 11/2022; không cập nhật mô hình hoặc feature bằng actual test ở những bước tiếp theo.
- Dự báo lưu thang số xe, đủ độ chính xác; RMSE/MAE/Bias có đơn vị xe, sMAPE có đơn vị %.
- `Bias = mean(actual − pred)`: dương là dự báo thấp hơn thực tế.
- `sMAPE = mean(200×|actual−pred|/(|actual|+|pred|))`; đóng góp bằng 0 nếu cả hai bằng 0.

Schema forecast gồm `model, config_id, date, origin, horizon, actual, pred, target_transform, evaluation_role, lower_95, upper_95, interval_level`. Baseline không được tự tạo interval: các trường khoảng để trống. `candidate_reference` chỉ ứng viên tham khảo, khác cấu hình đã chọn trong cùng họ.

## Chọn cấu hình trước khi chấm test

### ARIMA

Sáu ứng viên lấy từ thiết kế đã dùng: (1,2,0), (2,2,0), (0,2,1), (1,2,1), (2,2,1), (2,2,2). Mọi ứng viên dùng d=2, trend `n`, ràng buộc stationarity/invertibility, estimator statespace, optimizer L-BFGS và tối đa 500 vòng. Covariance được tính theo OPG.

Chọn AIC train thấp nhất trong các fit hội tụ, AIC hữu hạn và cùng likelihood burn. Không dùng test RMSE để chọn lại cấu hình. ADF/KPSS chỉ là chẩn đoán có giả định, không buộc mọi mô hình khác cũng dùng d=2.

### SARIMA

| ID | Order | Seasonal order |
|---|---|---|
| SARIMA_A | (1,1,1) | (1,1,0,12) |
| SARIMA_B | (0,1,1) | (1,1,1,12) |
| SARIMA_C | (0,2,1) | (0,1,1,12) |

SARIMA dùng trend `n`, `simple_differencing=False`, ràng buộc stationarity/invertibility, L-BFGS/maxiter 500 và covariance OPG.

Do các ứng viên khác bậc sai phân, **không xếp hạng bằng AIC/BIC giữa A/B/C**. Các chỉ tiêu đó vẫn được lưu để đọc đặc tả từng fit. Chọn bằng RMSE validation trung bình chưa làm tròn của ba fold nằm trọn trong train:

| Fold | Train đến | Số tháng train | Validation |
|---|---|---:|---|
| 1 | 11/2020 | 47 | 12/2020–11/2021 |
| 2 | 05/2021 | 53 | 06/2021–05/2022 |
| 3 | 11/2021 | 59 | 12/2021–11/2022 |

Ứng viên chỉ đủ điều kiện chọn khi cả ba fold và lần fit full train hội tụ. Fit lỗi/không hội tụ được ghi rõ, không thay bằng một nhãn SUCCESS cứng. Tie được phá theo config_id. Các fold chồng lấn, không xem là ba mẫu độc lập để kiểm định ưu thế.

Sau khi khóa lựa chọn mới dự báo/chấm test. Ba SARIMA có kết quả tham khảo riêng khi fit hợp lệ; test của ứng viên không được dùng để thay đổi lựa chọn đã khóa.

## Đặc trưng và dự báo đệ quy cho ML

`r_t = ln(y_t) − ln(y_(t−1))`, **không nhân 100**. `compute_log_growth` giữ NaN đầu để căn chỉ số với các mức EV. Không truyền mảng `diff(log(y))` đã bỏ phần tử đầu vào `build_supervised_dataset`.

Năm feature tại t: `r_(t−1), r_(t−2), r_(t−3), mean(r_(t−1)…r_(t−3)), mean(r_(t−1)…r_(t−6))`. Mẫu đầu là tháng thứ 8: full train tạo 64 cặp; ba prefix CV tạo 40/46/52 cặp. Đây là số mẫu ML, không phải số tháng fit của ARIMA/SARIMA.

- `build_supervised_dataset(growth)` trả X, nhãn r_t và thứ tự tên feature.
- `recursive_log_forecast(levels, predict_one, horizon)` chỉ đưa feature quá khứ cho callback; callback phải trả log-growth sau đổi ngược mọi scaler nhãn. Bước sau dùng tăng trưởng dự báo, không dùng actual tương lai. Không kẹp tăng trưởng âm về 0.
- `run_cross_validation(series, fit_fn, forecast_fn, config, return_forecasts=False)` chỉ đưa prefix train cho fit và forecast. Callback fit trả artifact dictionary; callback forecast trả 12 mức EV hữu hạn. Có thể lấy thêm bảng dự báo validation bằng `return_forecasts=True`.
- Scaler X/nhãn của ML được fit trong từng prefix train qua `models/ml.py`; không fit scaler trên toàn chuỗi trước validation.

## Chẩn đoán và giới hạn số học

### Tính dừng

ADF có H0 là unit root. KPSS có H0 là level-stationary (`c`) hoặc trend-stationary (`ct`). Bảng lưu đặc tả, số lag, statistic, critical values và warning. Với KPSS chạm biên bảng tra, `p_relation`/`p_display` ghi `<0.01` hoặc `>0.1`, không gọi 0.01/0.1 là p chính xác.

Các phép biến đổi: mức, sai phân 1/2, sai phân 1/2 cộng sai phân mùa vụ 12; chỉ trên train. ACF/PACF giữ tối đa 24 lag. Các dải/đỉnh đồ thị không tự chứng minh mùa vụ hoặc model đúng.

### Phần dư và hệ số

Sau khi loại `burn=max(loglikelihood_burn,d+D×12)`, Ljung–Box/Jarque–Bera dùng **standardized one-step forecast errors**. Ljung–Box ở lag 12/24 với `model_df=p+q+P+Q`. Lưu cả raw residual và innovations chuẩn hóa để truy phép tính. Không trộn bảng này với chẩn đoán raw residual của một phiên bản chạy khác.

Hội tụ không bảo đảm covariance điều kiện tốt. Metadata lưu numerical rank của covariance thô, condition number, nghiệm AR/MA và cờ nghiệm trong khoảng 0,01 quanh vòng tròn đơn vị. Numerical rank phụ thuộc đơn vị tham số/tolerance, không tự chứng minh ma trận lý thuyết suy biến.

**Trong lần chạy của gói này, ARIMA(2,2,2) được chọn theo AIC nhưng covariance có numerical-rank/conditioning cảnh báo và nghiệm gần đơn vị.** Các SE/Wald p/CI hệ số được giữ với `wald_inference_caution=True`, không dùng để khẳng định hệ số được ước lượng đáng tin cậy. Không tự xóa cấu hình khỏi kết quả hoặc thay optimizer vì nhìn thấy test của ứng viên khác tốt hơn.

Khoảng dự báo 95% là Gaussian state-space có điều kiện theo tham số đã fit, không tự bao gồm đầy đủ bất định chọn mô hình/tham số. Không cắt cận âm hoặc thêm interval giả cho baseline. Độ bao phủ 12/12 trong một cửa sổ không chứng minh độ bao phủ dài hạn 95%.

## Đầu ra

| File CSV | Nội dung |
|---|---|
| `candidate_scores_arima.csv` | AIC/BIC, hội tụ, burn, covariance, warnings và lựa chọn của sáu ứng viên |
| `cv_sarima.csv` | Điểm và trạng thái từng cấu hình/fold |
| `validation_forecasts_sarima.csv` | 108 dự báo validation để tính lại điểm, không chỉ lưu CV RMSE tổng hợp |
| `candidate_scores_sarima.csv` | Điểm validation trung bình, điều kiện đủ chọn và fit full train; AIC không dùng xếp hạng A/B/C |
| `forecast_baselines.csv` | Naive/Drift, mỗi phương pháp 12 dòng |
| `forecast_arima.csv` | ARIMA đã chọn, 12 dòng |
| `forecast_sarima.csv` | Mỗi SARIMA fit hợp lệ 12 dòng; phân biệt selected/candidate_reference |
| `statistical_test_metrics.csv` | RMSE/MAE/sMAPE/Bias và thông tin interval nếu có; chưa là bảng so sánh cuối với ML |
| `stationarity_tests.csv` | ADF/KPSS trên train và các phép biến đổi |
| `train_correlations.csv` | ACF/PACF từ lag 0–24 theo phép biến đổi |
| `residual_diagnostics.csv` | Ljung–Box, Jarque–Bera, cỡ mẫu/burn/model_df |
| `residual_series.csv` | Innovations chuẩn hóa và raw residual theo ngày/config |
| `model_parameters.csv` | Hệ số, SE, Wald p, CI và cờ cảnh báo covariance |

Bốn JSON: `best_arima.json`, `best_sarima.json`, `statistical_run.json`, `protocol_checks.json`. Tên `best` chỉ cấu hình được chọn **trong họ ứng viên theo tiêu chí train/validation**, không phải mô hình tốt nhất của toàn đồ án.

Bảy hình: `baseline_forecast.png`, `arima_forecast.png`, `sarima_forecasts.png`, `sarima_validation.png`, `train_transformations.png`, `train_acf_pacf.png`, `model_innovations.png`.

`protocol_checks.json` ghi các kiểm tra thực chạy về ranh giới validation, số feature, thay actual tương lai không đổi prefix feature và metric toy. Những kiểm tra này không phải phép làm sạch dữ liệu và không chứng minh tuyệt đối loại mọi dạng leakage.

## Tài liệu phương pháp/API

- [statsmodels ARIMA](https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html)
- [statsmodels SARIMAX](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html)
- [statsmodels ADF](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html)
- [statsmodels KPSS](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.kpss.html)

Phân tích là quan sát với một gốc test cố định. Kết quả không tự suy ra doanh số, tác động chính sách hoặc ưu thế dài hạn của một phương pháp.

## Ridge, Random Forest, SVR và XGBoost

Chạy sau preparation và dùng các module nền forecasting:

```powershell
python source/forecasting/run_ml_forecast.py `
  --series "D:/du_lieu/preparation_output/statewide_monthly.csv" `
  --results-dir "results/forecasting" `
  --figures-dir "figures/forecasting"
```

Cũng hỗ trợ `python -m source.forecasting.run_ml_forecast`. Hai runner có tên đầu ra riêng nên có thể dùng cùng thư mục kết quả; mỗi file đầu ra của lần chạy mới phải chưa tồn tại. Không tự ghi đè kết quả cũ.

### Mã nguồn và phép biến đổi

| File | Vai trò |
|---|---|
| `models/ml.py` | Tạo mẫu học từ prefix, fit scaler, đổi ngược nhãn và dự báo đệ quy; lưu trace |
| `models/ridge.py` | Ridge, solver SVD, có intercept không bị phạt |
| `models/random_forest.py` | Random Forest, bootstrap, 300 cây, một thread |
| `models/svr.py` | SVR với kernel RBF hoặc linear |
| `models/xgboost.py` | XGBoost hồi quy, CPU, `tree_method=hist`, một thread |
| `configs/ridge.json`, `random_forest.json`, `svr.json`, `xgboost.json` | Grid và quy tắc chọn cấu hình trước khi chạy |
| `run_ml_forecast.py` | Chạy 81 lượt fit validation, khóa bốn lựa chọn, fit full train và đánh giá test |

Tất cả mô hình học nhãn tăng trưởng log chuẩn hóa `z=(r−mean_train)/std_train`. Mean và variance dùng các **nhãn có giám sát** của prefix (40/46/52 hoặc 64 mẫu), không dùng toàn bộ growth lịch sử hoặc test. `StandardScaler` dùng variance ddof=0; biến không có phương sai được gán scale=1 theo API.

Ridge/SVR còn chuẩn hóa từng cột X bằng scaler riêng của prefix; RF/XGBoost giữ nguyên X. Không dùng `eval_set` hoặc early stopping dựa vào test. Callback dự báo trả tăng trưởng log đã đổi ngược scaler; quy mô xe ở bước h được nhân với exp(tăng trưởng dự báo). Trace ghi cả năm feature, z, r và mức dự báo ở từng bước. Từ bước thứ hai dùng tăng trưởng dự báo trước đó, không cập nhật bằng actual test.

### Grid và quy tắc chọn

| Họ | Ứng viên | Chọn trên validation |
|---|---|---|
| Ridge | alpha = 0.1, 1, 10 | Trong ngưỡng 101% RMSE trung bình tốt nhất, ưu tiên alpha lớn hơn; sau đó RMSE và ID |
| RF | depth = 2/3; min leaf = 3/5; max features = 0.7/1.0 | Trong ngưỡng 101%, ưu tiên depth thấp, min leaf lớn, RMSE thấp rồi ID |
| SVR | RBF: C=0.1/1/10 × epsilon=0.05/0.10; linear: C=1/10, epsilon=0.10 | RMSE trung bình thấp nhất; chỉ phá hòa chính xác bằng ID |
| XGBoost | depth = 1/2 × số cây = 50/100 × learning rate = 0.03/0.10 | Trong ngưỡng 101%, ưu tiên depth thấp, ít cây, RMSE thấp rồi ID |

Các ngưỡng áp dụng trên RMSE trung bình **chưa làm tròn** qua ba fold, trên thang xe. Không dùng quy tắc gần hòa SVR chưa được định nghĩa. Mỗi cấu hình chỉ đủ điều kiện nếu cả ba fold hoàn tất với trạng thái `ok`. Lỗi/cảnh báo/không hội tụ được giữ trong bảng CV. Nếu cấu hình đã chọn không fit full train hợp lệ, chương trình dừng; không chuyển sang cấu hình khác vì nhìn thấy sai số test.

RF dùng squared error, bootstrap=True, 300 cây; XGBoost dùng objective squared error, subsample=0.8, colsample_bytree=1, min_child_weight=3, L2=1, L1=0. Cả hai dùng random_state=42 và n_jobs=1. SVR dùng tol=0.001, gamma=scale (chỉ có tác dụng với RBF), max_iter=-1. Cấu hình đầy đủ nằm trong JSON.

### Đầu ra ML

Với hậu tố `ridge`, `random_forest`, `svr`, `xgboost`, mỗi họ có:

| Tên | Nội dung |
|---|---|
| `cv_<họ>.csv` | Metric, mốc thời gian, cỡ mẫu, trạng thái và warning từng ứng viên/fold |
| `validation_forecasts_<họ>.csv` | 12 dự báo của từng fold/cấu hình để tính lại điểm |
| `candidate_scores_<họ>.csv` | Trung bình metric, điều kiện chọn, ngưỡng gần hòa và cấu hình chọn |
| `best_<họ>.json` | Cấu hình, quy tắc chọn, scaler full train, cỡ mẫu và tóm tắt fit |
| `forecast_<họ>.csv` | 12 dự báo test trên số xe theo schema chung |
| `trace_<họ>.csv` | Feature và phép đổi ngược dự báo đệ quy cho 12 bước test |

`ml_test_metrics.csv` có bốn dòng RMSE/MAE/sMAPE/Bias. `ml_run.json` ghi môi trường chạy, thiết kế và số lượt fit. Tám hình `<họ>_validation.png` và `<họ>_forecast.png` trình bày validation và dự báo từng họ. Không tự thêm khoảng dự báo cho ML: ba cột interval để trống. Không lưu pickle mô hình; có thể huấn luyện lại bằng code/config và đầu vào ngoài repo.

Trong lần chạy đi kèm: Ridge chọn RIDGE03 (alpha=10), RF chọn RF05, SVR chọn SVR02 và XGBoost chọn XGB05. Test RMSE lần lượt là 5325.824073, 5243.320964, 6020.980986 và 5064.830985 xe. Đây là kết quả của phiên bản thư viện được ghi trong `ml_run.json`; không thay bằng số ở một lần chạy hoặc môi trường khác. Các file CSV giữ độ chính xác đầy đủ.

Kết quả này phục vụ phần triển khai và báo cáo từng mô hình. Bảng so sánh giữa các họ được tạo bằng `run_comparison.py` bên dưới; diễn giải kinh doanh và kết luận chung được viết theo phạm vi bằng chứng. Không diễn giải feature importance là tác động nhân quả hoặc khẳng định ưu thế dài hạn từ một cửa sổ 12 tháng.

Tài liệu API chính thức: [Ridge](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html), [Random Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html), [SVR](https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVR.html), [XGBoost](https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBRegressor).

## Tổng hợp và so sánh các phương pháp

Chạy sau cả hai runner thống kê và ML. Chương trình chỉ đọc kết quả đã chốt, không fit lại hoặc đổi siêu tham số:

```powershell
python source/forecasting/run_comparison.py `
  --series "D:/du_lieu/preparation_output/statewide_monthly.csv" `
  --forecast-dir "results/forecasting" `
  --results-dir "results/forecasting" `
  --figures-dir "figures/forecasting"
```

Hỗ trợ `python -m source.forecasting.run_comparison`. Dùng đường dẫn mới nếu các file `comparison_*` đã tồn tại. Không cần dependency bổ sung ngoài requirements hiện có.

### Đầu vào và kiểm tra tính so sánh

`comparison.py` căn chỉnh và tính lại bảng; `comparison_plots.py` vẽ hình; `run_comparison.py` điều phối đọc, kiểm tra và xuất kết quả.

Đầu vào là chuỗi preparation tám cột, bảy file forecast của gói thống kê/ML, sáu `best_*.json`, năm bảng CV của SARIMA và các ML, cùng `statistical_test_metrics.csv`/`ml_test_metrics.csv`. Chương trình:

- Kiểm tra cùng 12 ngày cuối tháng 12/2022–11/2023, gốc 30/11/2022, horizon 1–12 và biến dự báo trên thang số xe.
- Đối chiếu actual của mọi phương pháp với EV Total trong chuỗi preparation; chặn trùng/mất/thừa dòng, sai ID hoặc vai trò của cấu hình.
- Chỉ đưa Naive, Drift và cấu hình đã chọn của sáu họ vào so sánh chính: tổng cộng tám phương pháp, 96 dự báo. SARIMA A/B có vai trò `candidate_reference` được ghi là loại khỏi bảng chính; không chọn lại bằng test.
- Đối chiếu ID với metadata lựa chọn; kiểm tra trạng thái fit/CV và các prefix 47/53/59 tháng. Tính lại RMSE/MAE/sMAPE/Bias trực tiếp từ dự báo và so với metric đã xuất trước đó. Sai khác vượt tolerance số học thì dừng.
- Chỉ chấp nhận khoảng 95% từ ARIMA/SARIMA; các phương pháp khác phải để trống trường khoảng. Không suy ra interval ML từ sai số của 12 tháng test.

Tất cả đầu ra được tính từ số chưa làm tròn. Không sửa forecast/metric của các gói trước. Chương trình chỉ đọc những sản phẩm đó; `comparison_*` có tên riêng và không tự ghi đè.

### Bảng và hình

| File kết quả | Nội dung |
|---|---|
| `comparison_metrics.csv` | Tám dòng metric, rank RMSE/MAE/sMAPE, số tháng dự báo thấp/cao và cải thiện so với Naive/Drift |
| `comparison_predictions.csv` | 12 tháng actual và tám cột dự báo, dùng để đối chiếu chung |
| `comparison_errors.csv` | 96 dòng dự báo kèm error, absolute error, squared error và thành phần sMAPE |
| `comparison_cumulative_metrics.csv` | Metric trên các prefix tháng 1…h của cùng cửa sổ test; 96 dòng |
| `comparison_interval_summary.csv` | Hai dòng ARIMA/SARIMA: mức danh nghĩa, số tháng bao phủ, tỷ lệ bao phủ và độ rộng trung bình |
| `comparison_selection_summary.csv` | Sáu cấu hình đã khóa, tiêu chí train/validation, cỡ mẫu và cờ thận trọng Wald nếu áp dụng |
| `comparison_run.json` | Phạm vi chạy, danh sách đầu vào, nhóm tham khảo bị loại, kiểm tra đã thực hiện và giới hạn diễn giải |

Bốn hình: `comparison_accuracy.png` (RMSE/MAE), `comparison_forecasts.png` (tám ô cùng thang trục), `comparison_monthly_errors.png` (sai số từng tháng) và `comparison_cumulative_rmse.png` (RMSE tích lũy). Hình tích lũy có ô toàn bộ phương pháp và ô sáu mô hình với thang y riêng được ghi rõ; không hiểu thành tám chuỗi test độc lập.

`improvement = 100 × (metric_baseline − metric_model) / metric_baseline`: dương là giảm sai số, âm là tăng sai số. Baseline so với chính nó bằng 0. Rank dùng số đầy đủ, nhỏ hơn tốt hơn; hòa nhận cùng hạng nhỏ nhất. Không xếp hạng Bias theo chiều số nhỏ hơn vì dấu âm/dương phản ánh hướng sai lệch. Đơn vị RMSE/MAE/Bias là xe; sMAPE và improvement là %.

### Cách đọc kết quả đi kèm

Theo RMSE của **cửa sổ test này**, thứ tự là SARIMA C (2354.900944), ARIMA(2,2,2) (2730.963238), XGBoost (5064.830985), RF (5243.320964), Ridge (5325.824073), SVR (6020.980986), Drift (18606.539282) và Naive (28162.950452) xe.

SARIMA C có MAE 1771.095942 xe, sMAPE 1.217804%, giảm RMSE 91.6383% so với Naive và 87.3437% so với Drift. Đây là mức giảm **sai số dự báo**, không phải tăng doanh thu, lợi nhuận hoặc hiệu quả chính sách. ARIMA có Bias tuyệt đối nhỏ hơn SARIMA trong cửa sổ này; thứ hạng RMSE không có nghĩa mọi chỉ tiêu đều trội hơn. Ridge có MAE/sMAPE thấp hơn XGBoost/RF dù RMSE cao hơn, nên cần đọc từng chỉ tiêu theo ý nghĩa của nó.

ML có sai số validation thấp hơn SARIMA trong ba fold nhưng không giữ thứ hạng đó ở test. Không lấy chênh lệch này làm bằng chứng mô hình phi tuyến luôn tốt/xấu hơn hoặc tự khẳng định nguyên nhân thay đổi cơ chế tăng trưởng. Các fold validation chồng lấn; ba điểm trung bình không phải ba mẫu độc lập. ARIMA được chọn bằng AIC train, các họ còn lại bằng RMSE validation: **không so trực tiếp số AIC với số RMSE trong cột selection_value**.

ARIMA và SARIMA đều bao phủ 12/12 actual test bằng khoảng dự báo 95% đã xuất. Với một cửa sổ ngắn, tỷ lệ quan sát 100% không chứng minh hiệu chuẩn dài hạn 95%; độ rộng khoảng phải được đọc kèm. Cảnh báo covariance và nghiệm gần đơn vị của ARIMA vẫn có hiệu lực; không bỏ qua chỉ vì sai số dự báo thấp.

RMSE tích lũy tháng 1…h mô tả sai số phát triển trong **một gốc dự báo**, không phải RMSE được ước lượng từ nhiều gốc độc lập ở horizon h. Gói này không thực hiện kiểm định tuyên bố một phương pháp vượt trội về thống kê. Sau khi xem test, nếu chọn một mô hình để vận hành tiếp, cần thêm giai đoạn đánh giá ngoài mẫu mới; không gọi chính cửa sổ đã dùng xếp hạng là một lần kiểm định độc lập nữa.

Kết quả hỗ trợ theo dõi quy mô đội xe và cân nhắc mô hình dự báo cho nghiên cứu tiếp. Dữ liệu chưa đủ để trực tiếp tính doanh số, doanh thu, tải điện, số trạm sạc hoặc tác động nhân quả của chính sách. Không suy ra các đại lượng này chỉ từ EV Total.
