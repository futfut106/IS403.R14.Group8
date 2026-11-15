"""State-space fitting and prediction utilities with recorded warnings."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX


def fit_history(history: pd.DataFrame,config: dict,seasonal: bool) -> dict:
    index=pd.DatetimeIndex(history['date'],freq='ME')
    values=pd.Series(history['ev_total'].to_numpy(dtype=float),index=index)
    if values.empty or not np.isfinite(values).all():
        raise ValueError('Model fitting requires finite historical levels.')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        kwargs={'order':tuple(config['order']),'trend':config['trend'],
                'enforce_stationarity':config['enforce_stationarity'],'enforce_invertibility':config['enforce_invertibility']}
        if seasonal:
            model=SARIMAX(values,seasonal_order=tuple(config['seasonal_order']),simple_differencing=False,**kwargs)
            result=model.fit(method=config['optimizer'],maxiter=config['maxiter'],disp=False,cov_type='opg')
        else:
            model=ARIMA(values,**kwargs)
            result=model.fit(method='statespace',method_kwargs={'method':config['optimizer'],'maxiter':config['maxiter'],'disp':0},cov_type='opg')
        covariance=np.asarray(result.cov_params())
        condition=float(np.linalg.cond(covariance))
        rank=int(np.linalg.matrix_rank(covariance))
        ar_roots=np.abs(np.asarray(result.arroots))
        ma_roots=np.abs(np.asarray(result.maroots))
    convergence=result.mle_retvals.get('converged')
    metadata={
        'config_id':config['config_id'],'n_train_months':len(values),
        'train_start':str(index[0].date()),'train_end':str(index[-1].date()),
        'aic':float(result.aic),'bic':float(result.bic),'log_likelihood':float(result.llf),
        'converged':bool(convergence) if convergence is not None else None,
        'iterations':int(result.mle_retvals.get('iterations',0)),
        'loglikelihood_burn':int(result.loglikelihood_burn),
        'covariance_type':str(result.cov_type),'covariance_rank':rank,'n_parameters':len(result.params),
        'covariance_condition_number':condition if np.isfinite(condition) else None,
        'covariance_rank_deficient':rank<len(result.params),
        'covariance_rank_definition':'NumPy default numerical rank of raw covariance, affected by parameter scales.',
        'minimum_abs_ar_root':float(ar_roots.min()) if ar_roots.size else None,
        'minimum_abs_ma_root':float(ma_roots.min()) if ma_roots.size else None,
        'root_within_001_of_unit_circle':bool((ar_roots.size and np.min(np.abs(ar_roots-1))<.01) or (ma_roots.size and np.min(np.abs(ma_roots-1))<.01)),
        'wald_inference_caution':rank<len(result.params),
        'warnings':[{'category':w.category.__name__,'message':str(w.message)} for w in caught],
    }
    return {'fitted':result,'config':dict(config),'metadata':metadata,
            'converged':metadata['converged'],'warnings':metadata['warnings']}


def forecast(artifact: dict,history: pd.DataFrame,horizon: int=12) -> np.ndarray:
    if len(history)!=artifact['metadata']['n_train_months']:
        raise ValueError('Forecast history differs from the fitted prefix.')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=np.asarray(artifact['fitted'].forecast(horizon),dtype=float)
    artifact['warnings'].extend({'category':w.category.__name__,'message':str(w.message)} for w in caught)
    if result.shape!=(horizon,) or not np.isfinite(result).all():
        raise ValueError('Statistical forecasts must be finite and match the horizon.')
    return result


def forecast_distribution(artifact: dict,horizon: int=12,alpha: float=.05) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        distribution=artifact['fitted'].get_forecast(steps=horizon)
        pred=np.asarray(distribution.predicted_mean,dtype=float)
        interval=np.asarray(distribution.conf_int(alpha=alpha),dtype=float)
    artifact['warnings'].extend({'category':w.category.__name__,'message':str(w.message)} for w in caught)
    if pred.shape!=(horizon,) or interval.shape!=(horizon,2) or not np.isfinite(interval).all() or not np.isfinite(pred).all():
        raise ValueError('Nonfinite prediction distribution.')
    if not ((interval[:,0]<=pred)&(pred<=interval[:,1])).all():
        raise ValueError('Prediction interval ordering failed.')
    return pred,interval[:,0],interval[:,1]
