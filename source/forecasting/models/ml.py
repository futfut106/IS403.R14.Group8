"""Train-prefix scaling and recursive log-growth regression."""
from __future__ import annotations

import warnings
import numpy as np
from sklearn.preprocessing import StandardScaler

from ..features import (FEATURE_NAMES, build_supervised_dataset,
                        compute_log_growth, recursive_log_forecast)
from ..protocol import require


def fit(history, config, estimator, scale_x=False):
    X, y, names = build_supervised_dataset(compute_log_growth(history['ev_total']))
    x_scaler = StandardScaler().fit(X) if scale_x else None
    y_scaler = StandardScaler().fit(y.reshape(-1, 1))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        estimator.fit(x_scaler.transform(X) if scale_x else X,
                      y_scaler.transform(y.reshape(-1, 1)).ravel())
    converged = bool(estimator.fit_status_ == 0) if hasattr(estimator, 'fit_status_') else None
    return {'estimator': estimator, 'x_scaler': x_scaler, 'y_scaler': y_scaler,
            'config': dict(config), 'n_samples': len(y), 'feature_names': names,
            'converged': converged,
            'warnings': [{'category': w.category.__name__, 'message': str(w.message)} for w in caught]}


def predict_growth(artifact, row):
    X = np.asarray(row, dtype=float).reshape(1, -1)
    if artifact['x_scaler'] is not None:
        X = artifact['x_scaler'].transform(X)
    z = float(artifact['estimator'].predict(X)[0])
    r = float(artifact['y_scaler'].inverse_transform([[z]])[0, 0])
    require(np.isfinite(z) and np.isfinite(r), 'Nonfinite regression prediction.')
    return z, r


def forecast(artifact, history, horizon):
    return recursive_log_forecast(history['ev_total'], lambda row: predict_growth(artifact, row)[1], horizon)


def forecast_with_trace(artifact, history, horizon):
    rows = []
    def predict(row):
        z, r = predict_growth(artifact, row)
        rows.append(dict(zip(FEATURE_NAMES, map(float, row)), z_pred=z, r_pred=r))
        return r
    pred = recursive_log_forecast(history['ev_total'], predict, horizon)
    for step, (row, value) in enumerate(zip(rows, pred), 1):
        row.update(horizon=step, pred=float(value))
    return pred, rows


def describe(artifact):
    estimator = artifact['estimator']
    xs, ys = artifact['x_scaler'], artifact['y_scaler']
    result = {'n_supervised': artifact['n_samples'], 'feature_names': artifact['feature_names'],
              'x_standardized': xs is not None,
              'x_mean': None if xs is None else xs.mean_.tolist(),
              'x_scale': None if xs is None else xs.scale_.tolist(),
              'target_mean': float(ys.mean_[0]), 'target_scale': float(ys.scale_[0]),
              'target_variance': float(ys.var_[0]), 'scaler_ddof': 0,
              'converged': artifact['converged'], 'warnings': artifact['warnings']}
    if hasattr(estimator, 'support_'):
        result.update(n_support=int(len(estimator.support_)),
                      support_fraction=float(len(estimator.support_) / artifact['n_samples']))
    if hasattr(estimator, 'coef_'):
        result.update(coefficients=np.asarray(estimator.coef_).ravel().tolist(),
                      intercept=np.asarray(estimator.intercept_).reshape(-1).tolist())
    if hasattr(estimator, 'feature_importances_'):
        result['feature_importances'] = estimator.feature_importances_.tolist()
    return result
