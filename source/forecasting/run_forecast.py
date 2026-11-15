"""Train-only model selection and fixed-origin baseline/ARIMA/SARIMA experiments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import scipy
import statsmodels

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.forecasting.backtest import run_cross_validation
from source.forecasting import diagnostics,features
from source.forecasting.metrics import calculate_metrics
from source.forecasting.models import arima,sarima,baselines
from source.forecasting.models.statistical import forecast_distribution
from source.forecasting.protocol import check_outputs,load_protocol,load_series,require

CSV_NAMES=['candidate_scores_arima.csv','cv_sarima.csv','validation_forecasts_sarima.csv','candidate_scores_sarima.csv',
           'forecast_baselines.csv','forecast_arima.csv','forecast_sarima.csv','statistical_test_metrics.csv',
           'stationarity_tests.csv','train_correlations.csv','residual_diagnostics.csv','residual_series.csv','model_parameters.csv']
JSON_NAMES=['best_arima.json','best_sarima.json','statistical_run.json','protocol_checks.json']
FIGURE_NAMES=['baseline_forecast.png','arima_forecast.png','sarima_forecasts.png','sarima_validation.png',
              'train_transformations.png','train_acf_pacf.png','model_innovations.png']


def candidates(family: str) -> tuple[dict,list[dict]]:
    config=json.loads((Path(__file__).resolve().parent/'configs'/f'{family}.json').read_text(encoding='utf-8'))
    common={key:value for key,value in config.items() if key!='candidates'}
    return config,[{**common,**candidate} for candidate in config['candidates']]


def fit_candidates(train: pd.DataFrame,configs: list[dict],fit_fn) -> tuple[dict,pd.DataFrame]:
    artifacts,rows={},[]
    for config in configs:
        record={'config_id':config['config_id'],'order':str(config['order']),
                'seasonal_order':str(config.get('seasonal_order',[0,0,0,0]))}
        try:
            artifact=fit_fn(train,config)
            metadata=artifact['metadata']
            artifacts[config['config_id']]=artifact
            record.update(metadata)
            record['warnings']=json.dumps(metadata['warnings'],ensure_ascii=False)
            record['status']='ok' if metadata['converged'] and np.isfinite(metadata['aic']) else 'not_admissible'
        except Exception as error:
            record.update(status='failed',converged=False,error=f'{type(error).__name__}: {error}')
        rows.append(record)
    return artifacts,pd.DataFrame(rows)


def select_arima(scores: pd.DataFrame) -> str:
    eligible=scores.loc[scores['status'].eq('ok')].copy()
    require(not eligible.empty,'No converged finite ARIMA candidate; inspect train-fit failures before continuing.')
    require(eligible['loglikelihood_burn'].nunique()==1,'AIC candidates must use comparable likelihood initialization.')
    return str(eligible.sort_values(['aic','config_id'],kind='stable').iloc[0]['config_id'])


def select_sarima(cv: pd.DataFrame,full_scores: pd.DataFrame) -> tuple[str,pd.DataFrame]:
    records=[]
    for fit in full_scores.to_dict('records'):
        part=cv.loc[cv['config_id'].eq(fit['config_id'])]
        valid=part.loc[part['status'].eq('ok')]
        all_ok=len(valid)==3 and len(part)==3 and fit['status']=='ok'
        records.append({**fit,'validation_ok_folds':len(valid),'mean_cv_rmse':float(part['rmse'].mean()) if 'rmse' in part and part['rmse'].notna().all() else None,
                        'eligible_for_selection':all_ok})
    scores=pd.DataFrame(records)
    eligible=scores.loc[scores['eligible_for_selection'] & scores['mean_cv_rmse'].notna()]
    require(not eligible.empty,'No SARIMA candidate converged in every fold and full train; inspect failures before continuing.')
    selected=str(eligible.sort_values(['mean_cv_rmse','config_id'],kind='stable').iloc[0]['config_id'])
    scores['selected']=scores['config_id'].eq(selected)
    return selected,scores


def forecast_frame(model: str,config_id: str,test: pd.DataFrame,pred,role: str,lower=None,upper=None) -> pd.DataFrame:
    pred=np.asarray(pred,dtype=float)
    require(pred.shape==(len(test),) and np.isfinite(pred).all(),'Prediction dates or values are invalid.')
    frame=pd.DataFrame({'model':model,'config_id':config_id,'date':test['date'].dt.strftime('%Y-%m-%d').to_numpy(),
                        'origin':load_protocol()['train_end'],'horizon':np.arange(1,len(test)+1),
                        'actual':test['ev_total'].to_numpy(),'pred':pred,'target_transform':'level',
                        'evaluation_role':role,'lower_95':np.nan if lower is None else lower,
                        'upper_95':np.nan if upper is None else upper,
                        'interval_level':np.nan if lower is None else .95})
    return frame


def protocol_checks(series: pd.DataFrame,cv: pd.DataFrame) -> dict:
    train=series.loc[series['split'].eq('train')]
    growth=features.compute_log_growth(train['ev_total'])
    x,y,names=features.build_supervised_dataset(growth)
    require(x.shape==(64,5) and len(y)==64,'Full-train ML feature shape differs from 64 x 5.')
    folds=[]
    for months,expected in zip(load_protocol()['cv_train_months'],[40,46,52]):
        xf,yf,_=features.build_supervised_dataset(features.compute_log_growth(train['ev_total'].iloc[:months]))
        require(len(xf)==expected and len(yf)==expected,'Fold feature count differs from the declared design.')
        folds.append({'train_months':months,'supervised_rows':len(xf)})
    full_x,_,_=features.build_supervised_dataset(features.compute_log_growth(series['ev_total']))
    changed=series['ev_total'].to_numpy(dtype=float).copy()
    changed[71:]*=3
    changed_x,_,_=features.build_supervised_dataset(features.compute_log_growth(changed))
    require(np.array_equal(full_x[:64],x) and np.array_equal(changed_x[:64],x),'Past features changed when future actuals changed.')
    require(pd.to_datetime(cv['validation_end']).le(pd.Timestamp(load_protocol()['train_end'])).all(),'Validation entered the test period.')
    require(calculate_metrics([0,1],[0,1])=={'rmse':0.,'mae':0.,'smape':0.,'bias':0.},'Zero-error metric check failed.')
    return {'full_train_months':len(train),'full_train_supervised_rows':len(x),'feature_names':names,'fold_shapes':folds,
            'prefix_features_match_full_series_prefix':True,'prefix_features_unchanged_by_future_actual_mutation':True,
            'validation_stays_within_train':True,'zero_error_and_zero_denominator_metric_check':True,
            'scope':'These checks cover the declared boundaries/features; they do not prove absence of every possible form of leakage.'}


def export_forecast_figures(train: pd.DataFrame,frames: dict,sarima_scores: pd.DataFrame,residuals: pd.DataFrame,selected_ids: list[str],directory: Path,arima_caution: bool=False) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter
    from statsmodels.graphics.tsaplots import plot_acf
    from scipy import stats
    directory.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    for name,title,filename in [('baselines','Naive và Drift','baseline_forecast.png'),('arima','ARIMA đã chọn theo AIC train','arima_forecast.png'),('sarima','Các ứng viên SARIMA; lựa chọn theo validation nội train','sarima_forecasts.png')]:
        data=frames[name]
        actual=data.drop_duplicates('date')
        fig,ax=plt.subplots(figsize=(11,6))
        fig.subplots_adjust(left=.12,right=.97,bottom=.26,top=.85)
        recent=train.iloc[-12:]
        ax.plot(recent['date'],recent['ev_total'],color='#687482',label='Train (12 tháng cuối)',linewidth=1.6)
        ax.plot(pd.to_datetime(actual['date']),actual['actual'],color='#202832',label='Thực tế test',marker='o',markersize=3,linewidth=1.8)
        for index,((model,cfg),part) in enumerate(data.groupby(['model','config_id'],sort=False)):
            color=['#167D9A','#D69332','#9B5A93'][index%3]
            selected=part['evaluation_role'].iloc[0]=='selected'
            ax.plot(pd.to_datetime(part['date']),part['pred'],label=cfg+(' (chọn)' if selected else ''),color=color,linestyle='--',linewidth=1.8)
            if selected and part['lower_95'].notna().all():
                ax.fill_between(pd.to_datetime(part['date']),part['lower_95'],part['upper_95'],alpha=.13,color=color,label='Khoảng dự báo 95% (model chọn)')
        ax.axvline(pd.Timestamp(load_protocol()['train_end']),color='#777777',linestyle=':',linewidth=1)
        ax.set(title=title,ylabel='Số EV cuối tháng',xlabel='Tháng')
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        ax.set_xlim(recent['date'].iloc[0],pd.Timestamp(actual['date'].iloc[-1])+pd.Timedelta(days=10))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'.replace(',','.')))
        ax.grid(axis='y',alpha=.17)
        ax.legend(loc='upper left',frameon=False,fontsize=8.5,ncol=2)
        caution='Covariance ARIMA có cảnh báo điều kiện số; thận trọng với suy diễn hệ số và khoảng dự báo.' if name=='arima' and arima_caution else 'Khoảng thống kê nếu có là dự báo có điều kiện theo model đã fit, không bảo đảm độ bao phủ dài hạn.'
        fig.text(.06,.035,'Nguồn: chuỗi toàn bang từ History clean. Fit/chọn cấu hình chỉ dùng train 01/2017–11/2022.\nGốc 11/2022; dự báo 12 tháng 12/2022–11/2023, không cập nhật bằng actual test.\n'+caution,fontsize=8.7)
        fig.savefig(directory/filename,dpi=220,bbox_inches='tight',pad_inches=.2)
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.5,5.2))
    fig.subplots_adjust(left=.13,right=.96,bottom=.25,top=.85)
    colors=['#167D9A' if chosen else '#A8ADB4' for chosen in sarima_scores['selected']]
    bars=ax.bar(sarima_scores['config_id'],sarima_scores['mean_cv_rmse'],color=colors,width=.6)
    for bar,value in zip(bars,sarima_scores['mean_cv_rmse']):
        if pd.notna(value):
            label=f'{value:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height(),label,ha='center',va='bottom',fontsize=9)
    ax.set(title='SARIMA: RMSE validation trung bình trên ba fold',ylabel='RMSE (xe)')
    ax.set_ylim(top=float(sarima_scores['mean_cv_rmse'].max())*1.20)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'.replace(',','.')))
    ax.grid(axis='y',alpha=.17)
    ax.set_axisbelow(True)
    fig.text(.06,.03,'Chỉ validation nằm trong train; cột xanh là cấu hình đã chọn trước test.\nCác fold chồng lấn nên không xem như ba mẫu độc lập để kiểm định ưu thế.',fontsize=8.8)
    fig.savefig(directory/'sarima_validation.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)
    fig,axes=plt.subplots(len(selected_ids),3,figsize=(13,7.5),squeeze=False)
    fig.subplots_adjust(left=.08,right=.97,bottom=.14,top=.90,wspace=.35,hspace=.5)
    for row,cfg in enumerate(selected_ids):
        part=residuals.loc[residuals['config_id'].eq(cfg)]
        values=part['standardized_innovation'].to_numpy()
        axes[row,0].plot(pd.to_datetime(part['date']),values,color='#167D9A',linewidth=1)
        axes[row,0].axhline(0,color='#777777',linewidth=.6)
        axes[row,0].set_title(cfg+' — innovations',fontsize=10)
        axes[row,0].set_xlim(pd.to_datetime(part['date']).min(),pd.to_datetime(part['date']).max())
        axes[row,0].xaxis.set_major_locator(mdates.YearLocator())
        axes[row,0].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        plot_acf(values,lags=24,zero=False,ax=axes[row,1],title=cfg+' — ACF')
        stats.probplot(values,dist='norm',plot=axes[row,2])
        axes[row,2].set_title(cfg+' — Q–Q chuẩn',fontsize=10)
        axes[row,2].set_xlabel('Phân vị chuẩn lý thuyết')
        axes[row,2].set_ylabel('Phân vị innovations')
    fig.suptitle('Chẩn đoán innovations train sau khởi tạo',fontweight='bold')
    fig.text(.06,.025,'Nguồn: model được chọn trên train; đã loại đoạn burn được lưu trong bảng chẩn đoán.\nĐồ thị/Ljung–Box/Jarque–Bera đánh giá các khía cạnh khác nhau; không tự chứng minh model đúng hoặc dự báo tốt ở mọi thời kỳ.',fontsize=8.8)
    fig.savefig(directory/'model_innovations.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    args=parser.parse_args()
    check_outputs([*(args.results_dir/n for n in CSV_NAMES+JSON_NAMES),*(args.figures_dir/n for n in FIGURE_NAMES)],[args.series])
    series=load_series(args.series)
    train=series.loc[series['split'].eq('train')].copy().reset_index(drop=True)
    # No model receives this partition until selection has finished.
    test=series.loc[series['split'].eq('test')].copy().reset_index(drop=True)
    arima_spec,arima_configs=candidates('arima')
    sarima_spec,sarima_configs=candidates('sarima')
    print('Fitting ARIMA candidates on 71 train months...',flush=True)
    arima_artifacts,arima_scores=fit_candidates(train,arima_configs,arima.fit)
    chosen_arima=select_arima(arima_scores)
    arima_scores['selected']=arima_scores['config_id'].eq(chosen_arima)
    print('Validating SARIMA candidates inside train...',flush=True)
    validations=[run_cross_validation(series,sarima.fit,sarima.forecast,cfg,return_forecasts=True) for cfg in sarima_configs]
    cv=pd.concat([item[0] for item in validations],ignore_index=True)
    cv_forecasts=pd.concat([item[1] for item in validations],ignore_index=True)
    sarima_artifacts,sarima_fit_scores=fit_candidates(train,sarima_configs,sarima.fit)
    chosen_sarima,sarima_scores=select_sarima(cv,sarima_fit_scores)
    print(f'Train-only selections: {chosen_arima}, {chosen_sarima}',flush=True)
    checks=protocol_checks(series,cv)
    stationarity,correlations=diagnostics.train_diagnostics(train)
    frames={}
    frames['baselines']=pd.concat([forecast_frame(method,method.upper(),test,baselines.forecast(train['ev_total'],method),'baseline') for method in ['Naive','Drift']],ignore_index=True)
    pred,lower,upper=forecast_distribution(arima_artifacts[chosen_arima])
    frames['arima']=forecast_frame('ARIMA',chosen_arima,test,pred,'selected',lower,upper)
    sarima_forecasts=[]
    used_artifacts=[arima_artifacts[chosen_arima]]
    for cfg in sarima_configs:
        artifact=sarima_artifacts.get(cfg['config_id'])
        if artifact is None or artifact['converged'] is not True:
            continue
        pred,lower,upper=forecast_distribution(artifact)
        role='selected' if cfg['config_id']==chosen_sarima else 'candidate_reference'
        sarima_forecasts.append(forecast_frame('SARIMA',cfg['config_id'],test,pred,role,lower,upper))
        used_artifacts.append(artifact)
    frames['sarima']=pd.concat(sarima_forecasts,ignore_index=True)
    metric_rows=[]
    for data in frames.values():
        for (model,cfg),part in data.groupby(['model','config_id'],sort=False):
            row={'model':model,'config_id':cfg,'origin':load_protocol()['train_end'],'horizon':12,
                 'evaluation_role':part['evaluation_role'].iloc[0],**calculate_metrics(part['actual'],part['pred'])}
            if part['lower_95'].notna().all():
                row.update(interval_level=.95,interval_coverage=float(part['actual'].between(part['lower_95'],part['upper_95']).mean()),
                           mean_interval_width=float((part['upper_95']-part['lower_95']).mean()))
            metric_rows.append(row)
    diagnostic_tables=[diagnostics.fitted_diagnostics(artifact,train) for artifact in used_artifacts]
    residual_diagnostics=pd.concat([item[0] for item in diagnostic_tables],ignore_index=True)
    residuals=pd.concat([item[1] for item in diagnostic_tables],ignore_index=True)
    parameters=pd.concat([item[2] for item in diagnostic_tables],ignore_index=True)
    tables=dict(zip(CSV_NAMES,[arima_scores,cv,cv_forecasts,sarima_scores,frames['baselines'],frames['arima'],frames['sarima'],pd.DataFrame(metric_rows),
                               stationarity,correlations,residual_diagnostics,residuals,parameters]))
    metadata={
        'input_series':args.series.name,'target_unit':'vehicles at month end','train_start':'2017-01-31','train_end':'2022-11-30',
        'test_start':'2022-12-31','test_end':'2023-11-30','horizon':12,
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
                       'scipy':scipy.__version__,'statsmodels':statsmodels.__version__},
        'selected_arima':chosen_arima,'selected_sarima':chosen_sarima,
        'arima_selection':arima_spec['selection'],'sarima_selection':sarima_spec['selection'],
        'fits':{key:artifact['metadata'] for key,artifact in {**arima_artifacts,**sarima_artifacts}.items()},
        'intervals':'Gaussian state-space prediction intervals conditional on fitted model parameters; no clipping.',
        'sarima_aic_comparison':'AIC/BIC retained descriptively, not used to rank candidates with different differencing.',
        'limitations':['One fixed test origin; test comparison is not independent evidence of long-term superiority.',
                       'Model convergence does not guarantee a well-conditioned covariance matrix or valid residual assumptions.',
                       'ML feature helpers are available, but no Ridge/RF/SVR/XGBoost has been fitted in this package.']}
    payloads={
        'best_arima.json':{'config':arima_artifacts[chosen_arima]['config'],'selection':arima_spec['selection'],
                           'train_fit':arima_artifacts[chosen_arima]['metadata']},
        'best_sarima.json':{'config':sarima_artifacts[chosen_sarima]['config'],'selection':sarima_spec['selection'],
                            'mean_cv_rmse':float(sarima_scores.loc[sarima_scores['selected'],'mean_cv_rmse'].iloc[0]),
                            'train_fit':sarima_artifacts[chosen_sarima]['metadata']},
        'statistical_run.json':metadata,'protocol_checks.json':checks}
    diagnostics.export_train_figures(train,args.figures_dir)
    export_forecast_figures(train,frames,sarima_scores,residuals,[chosen_arima,chosen_sarima],args.figures_dir,
                            arima_caution=arima_artifacts[chosen_arima]['metadata']['wald_inference_caution'])
    args.results_dir.mkdir(parents=True,exist_ok=True)
    for name,table in tables.items():
        table.to_csv(args.results_dir/name,index=False,encoding='utf-8-sig',lineterminator='\n')
    for name,payload in payloads.items():
        (args.results_dir/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(pd.DataFrame(metric_rows).to_string(index=False),flush=True)


if __name__=='__main__':
    main()
