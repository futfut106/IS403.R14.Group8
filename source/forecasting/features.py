"""Past-only log-growth features and recursive inversion for later ML models."""
from __future__ import annotations

import numpy as np

FEATURE_NAMES=['r_lag_1','r_lag_2','r_lag_3','r_mean_3','r_mean_6']


def compute_log_growth(levels) -> np.ndarray:
    values=np.asarray(levels,dtype=float)
    if values.ndim!=1 or len(values)<2 or not np.isfinite(values).all() or (values<=0).any():
        raise ValueError('Log growth requires at least two finite positive levels.')
    return np.r_[np.nan,np.diff(np.log(values))]


def extract_features_at_step(history_growth) -> np.ndarray:
    values=np.asarray(history_growth,dtype=float)
    if values.ndim!=1 or len(values)<6 or not np.isfinite(values[-6:]).all():
        raise ValueError('Features require six finite past growth values.')
    return np.array([values[-1],values[-2],values[-3],values[-3:].mean(),values[-6:].mean()])


def build_supervised_dataset(growth) -> tuple[np.ndarray,np.ndarray,list[str]]:
    values=np.asarray(growth,dtype=float)
    if values.ndim!=1 or len(values)<8 or not np.isnan(values[0]) or not np.isfinite(values[1:]).all():
        raise ValueError('Supervised data require a leading missing growth and finite growth after the first index, aligned to at least eight levels.')
    features=np.vstack([extract_features_at_step(values[t-6:t]) for t in range(7,len(values))])
    return features,values[7:].copy(),FEATURE_NAMES.copy()


def recursive_log_forecast(history_levels,predict_one,horizon: int=12) -> np.ndarray:
    if horizon<1:
        raise ValueError('Forecast horizon must be positive.')
    growth=compute_log_growth(history_levels).tolist()
    if len(growth)<7:
        raise ValueError('Recursive forecasting requires at least seven history levels.')
    current=float(np.asarray(history_levels)[-1])
    predictions=[]
    for _ in range(horizon):
        # predict_one must return growth on the original log scale, after any inverse scaling.
        step=float(predict_one(extract_features_at_step(growth)))
        if not np.isfinite(step):
            raise ValueError('Predicted log growth is not finite.')
        with np.errstate(over='raise',invalid='raise'):
            current=float(current*np.exp(step))
        if not np.isfinite(current) or current<=0:
            raise ValueError('Inverted forecast must be finite and positive.')
        predictions.append(current)
        growth.append(step)
    return np.asarray(predictions)
