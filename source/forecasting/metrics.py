"""Full-precision forecast metrics on the vehicle-count scale."""
from __future__ import annotations

import numpy as np


def calculate_metrics(actual,pred) -> dict[str,float]:
    actual,pred=np.asarray(actual,dtype=float),np.asarray(pred,dtype=float)
    if actual.ndim!=1 or pred.shape!=actual.shape or not actual.size:
        raise ValueError('Actual and prediction must be nonempty aligned one-dimensional vectors.')
    if not np.isfinite(actual).all() or not np.isfinite(pred).all():
        raise ValueError('Metrics require finite actuals and predictions.')
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        error=actual-pred
        denominator=np.abs(actual)+np.abs(pred)
        terms=np.divide(200*np.abs(error),denominator,out=np.zeros_like(error),where=denominator!=0)
        return {'rmse':float(np.sqrt(np.mean(error**2))),'mae':float(np.mean(np.abs(error))),
                'smape':float(np.mean(terms)),'bias':float(np.mean(error))}
