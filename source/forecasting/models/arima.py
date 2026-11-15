"""ARIMA fitting on monthly EV levels with explicit configuration."""
from .statistical import fit_history,forecast


def fit(history,config):
    return fit_history(history,config,seasonal=False)
