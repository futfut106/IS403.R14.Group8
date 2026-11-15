"""Support-vector regression with train-prefix feature and label scaling."""
from sklearn.svm import SVR
from . import ml


def fit(history, config):
    params = {key: value for key, value in config.items() if key != 'config_id'}
    return ml.fit(history, config, SVR(**params), scale_x=True)


forecast = ml.forecast
