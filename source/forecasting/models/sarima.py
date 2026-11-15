"""SARIMA fitting on monthly EV levels with explicit seasonal configuration."""
from .statistical import fit_history,forecast


def fit(history,config):
    return fit_history(history,config,seasonal=True)
