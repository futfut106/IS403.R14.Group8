"""Train-only stationarity checks and fitted innovation diagnostics."""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller,kpss,acf,pacf


def train_diagnostics(train: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    levels=pd.Series(train['ev_total'].to_numpy(dtype=float),index=pd.DatetimeIndex(train['date']))
    transforms={'level':levels,'difference_1':levels.diff(),'difference_2':levels.diff().diff(),
                'difference_1_seasonal_12':levels.diff().diff(12),'difference_2_seasonal_12':levels.diff().diff().diff(12)}
    rows=[]
    correlations=[]
    for transform,series in transforms.items():
        values=series.dropna()
        regressions=['c','ct'] if transform=='level' else ['c']
        for regression in regressions:
            for test in ['ADF','KPSS']:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    if test=='ADF':
                        result=adfuller(values,regression=regression,autolag='AIC',result_object=False)
                        statistic,p,lags,nobs,critical,_=result
                        relation='='
                    else:
                        statistic,p,lags,critical=kpss(values,regression=regression,nlags='auto',result_object=False)
                        nobs=len(values)
                        bounded=any(w.category.__name__=='InterpolationWarning' for w in caught)
                        relation='<' if p==.01 and bounded else '>' if p==.1 and bounded else '='
                rows.append({'test':test,'transformation':transform,'regression':regression,'series_n':len(values),
                             'test_nobs':int(nobs),'statistic':float(statistic),'p_value':float(p),
                             'p_relation':relation,'p_display':relation+f'{p:.8g}',
                             'null_hypothesis':'unit root' if test=='ADF' else 'level stationary' if regression=='c' else 'trend stationary',
                             'reject_h0_005':bool(p<.05),'lags':int(lags),
                             'critical_1pct':float(critical['1%']),'critical_5pct':float(critical['5%']),
                             'critical_10pct':float(critical['10%']),
                             'warnings':' | '.join(f'{w.category.__name__}: {w.message}' for w in caught)})
        for lag,(a,p) in enumerate(zip(acf(values,nlags=24,fft=False,adjusted=False),pacf(values,nlags=24,method='ywm'))):
            correlations.append({'transformation':transform,'n':len(values),'lag':lag,'acf':float(a),'pacf':float(p)})
    return pd.DataFrame(rows),pd.DataFrame(correlations)


def fitted_diagnostics(artifact: dict,train: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    result,config=artifact['fitted'],artifact['config']
    seasonal=config.get('seasonal_order',[0,0,0,0])
    burn=max(int(result.loglikelihood_burn),int(config['order'][1]+seasonal[1]*seasonal[3]))
    innovations=np.asarray(result.filter_results.standardized_forecasts_error[0,burn:],dtype=float)
    raw=np.asarray(result.resid,dtype=float)[burn:]
    if not np.isfinite(innovations).all() or len(innovations)<=24:
        raise ValueError('Insufficient finite post-initialization innovations for diagnostics.')
    model_df=config['order'][0]+config['order'][2]+seasonal[0]+seasonal[2]
    ljung=acorr_ljungbox(innovations,lags=[12,24],model_df=model_df,return_df=True)
    jb=stats.jarque_bera(innovations)
    rows=[]
    for lag,row in ljung.iterrows():
        rows.append({'config_id':config['config_id'],'residual_kind':'standardized one-step forecast errors',
                     'burn':burn,'residual_n':len(innovations),'model_df':model_df,'lag':int(lag),
                     'ljung_box_statistic':float(row.lb_stat),'ljung_box_p_value':float(row.lb_pvalue),
                     'jarque_bera_statistic':float(jb.statistic),'jarque_bera_p_value':float(jb.pvalue),
                     'residual_mean':float(innovations.mean()),'residual_std':float(innovations.std(ddof=1))})
    residuals=pd.DataFrame({'config_id':config['config_id'],'date':train['date'].iloc[burn:].dt.strftime('%Y-%m-%d').to_numpy(),
                            'raw_residual':raw,'standardized_innovation':innovations})
    interval=np.asarray(result.conf_int(alpha=.05))
    parameters=[]
    for index,name in enumerate(result.param_names):
        p=float(np.asarray(result.pvalues)[index])
        parameters.append({'config_id':config['config_id'],'parameter':name,'estimate':float(np.asarray(result.params)[index]),
                           'standard_error':float(np.asarray(result.bse)[index]),'z_value':float(np.asarray(result.zvalues)[index]),
                           'p_value':p if p!=0 else None,'p_display':f'{p:.8g}' if p!=0 else '<1e-300 (numerical underflow)',
                           'lower_95':float(interval[index,0]),'upper_95':float(interval[index,1]),
                           'covariance_rank_deficient':artifact['metadata']['covariance_rank_deficient'],
                           'wald_inference_caution':artifact['metadata']['wald_inference_caution'],
                           'covariance_condition_number':artifact['metadata']['covariance_condition_number']})
    return pd.DataFrame(rows),residuals,pd.DataFrame(parameters)


def export_train_figures(train: pd.DataFrame,directory) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from statsmodels.graphics.tsaplots import plot_acf,plot_pacf
    from matplotlib.ticker import FuncFormatter
    directory.mkdir(parents=True,exist_ok=True)
    levels=pd.Series(train['ev_total'].to_numpy(dtype=float),index=pd.DatetimeIndex(train['date']))
    data=[('Mức EV',levels),('Sai phân bậc 1',levels.diff()),('Sai phân bậc 2',levels.diff().diff()),
          ('Sai phân bậc 2 và mùa vụ 12',levels.diff().diff().diff(12))]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.5,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(4,1,figsize=(11,10.5),sharex=True)
    fig.subplots_adjust(left=.13,right=.97,bottom=.13,top=.92,hspace=.35)
    for ax,(label,series) in zip(axes,data):
        ax.plot(series.index,series,color='#167D9A',linewidth=1.5)
        ax.set_title(label,loc='left',fontsize=9.5)
        ax.set_ylabel('Xe')
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'.replace(',','.')))
        ax.grid(axis='y',alpha=.18)
    fig.suptitle('Chuỗi train và các phép sai phân — 01/2017–11/2022',fontweight='bold')
    fig.text(.06,.025,'Nguồn: chuỗi toàn bang từ History clean; chỉ 71 tháng train.\nCác phép biến đổi dùng chẩn đoán, không tự chứng minh mùa vụ hoặc buộc mọi model dùng cùng bậc sai phân.',fontsize=8.8)
    fig.savefig(directory/'train_transformations.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)
    fig,axes=plt.subplots(3,2,figsize=(12,10))
    fig.subplots_adjust(left=.08,right=.97,bottom=.12,top=.92,hspace=.5,wspace=.25)
    for row,(label,series) in enumerate(data[:3]):
        values=series.dropna()
        plot_acf(values,lags=24,fft=False,ax=axes[row,0],title=label+' — ACF',zero=False)
        plot_pacf(values,lags=24,method='ywm',ax=axes[row,1],title=label+' — PACF',zero=False)
    fig.suptitle('ACF/PACF trên train; 24 độ trễ',fontweight='bold')
    fig.text(.06,.025,'Nguồn: train 01/2017–11/2022. Dải tham khảo 95% của đồ thị không phải kiểm định nhân quả\nvà một vài đỉnh ở lag 12 không đủ để kết luận chắc chắn có mùa vụ.',fontsize=8.8)
    fig.savefig(directory/'train_acf_pacf.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)
