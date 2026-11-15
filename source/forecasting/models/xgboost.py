"""CPU histogram gradient boosting with a fixed seed and one thread."""
from xgboost import XGBRegressor
from . import ml


def fit(history, config):
    params = {key: value for key, value in config.items() if key != 'config_id'}
    return ml.fit(history, config, XGBRegressor(**params))


forecast = ml.forecast
