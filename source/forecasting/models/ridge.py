"""Ridge on standardized past growth features and standardized growth labels."""
from sklearn.linear_model import Ridge
from . import ml


def fit(history, config):
    return ml.fit(history, config, Ridge(alpha=config['alpha'], solver='svd'), scale_x=True)


forecast = ml.forecast
