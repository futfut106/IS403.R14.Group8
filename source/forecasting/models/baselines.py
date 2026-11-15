"""Naive and Drift forecasts from history only."""
from __future__ import annotations

import numpy as np


def forecast(history,method: str,horizon: int=12) -> np.ndarray:
    values=np.asarray(history,dtype=float)
    if values.ndim!=1 or len(values)<2 or not np.isfinite(values).all() or horizon<1:
        raise ValueError('Baseline forecasting needs finite history and a positive horizon.')
    if method=='Naive':
        return np.repeat(values[-1],horizon)
    if method=='Drift':
        return values[-1]+np.arange(1,horizon+1)*(values[-1]-values[0])/(len(values)-1)
    raise ValueError('Unknown baseline method.')
