"""Bootstrap regression trees on unscaled past growth features."""
from sklearn.ensemble import RandomForestRegressor
from . import ml


def fit(history, config):
    params = {key: value for key, value in config.items() if key != 'config_id'}
    return ml.fit(history, config, RandomForestRegressor(**params))


forecast = ml.forecast
