"""Train-only expanding-window validation with fit/forecast callbacks."""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from .metrics import calculate_metrics
from .protocol import load_protocol,require


def run_cross_validation(series: pd.DataFrame,fit_fn,forecast_fn,config: dict,return_forecasts: bool=False):
    protocol=load_protocol()
    # Slice by labels before exposing any history or validation data to a callback.
    training=series.loc[series['split'].eq('train')].copy().reset_index(drop=True)
    require(len(training)==71,'Cross-validation expects the 71-month training partition only.')
    records=[]
    traces=[]
    horizon=protocol['horizon']
    for fold,(months,origin) in enumerate(zip(protocol['cv_train_months'],protocol['cv_origins']),1):
        prefix=training.iloc[:months].copy()
        validation=training.iloc[months:months+horizon].copy()
        require(len(validation)==horizon and prefix['date'].iloc[-1]==pd.Timestamp(origin),'Invalid validation boundary.')
        record={'config_id':config['config_id'],'fold':fold,'origin':origin,'n_train_months':months,
                'validation_start':str(validation['date'].iloc[0].date()),'validation_end':str(validation['date'].iloc[-1].date()),
                'horizon':horizon}
        caught=[]
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                artifact=fit_fn(prefix,dict(config))
                pred=np.asarray(forecast_fn(artifact,prefix,horizon),dtype=float)
            require(pred.shape==(horizon,) and np.isfinite(pred).all(),'Invalid validation predictions.')
            record.update(calculate_metrics(validation['ev_total'],pred))
            converged=artifact.get('converged')
            record.update(status='ok' if converged is not False else 'not_converged',converged=converged)
            messages=list(artifact.get('warnings',[]))+[{'category':w.category.__name__,'message':str(w.message)} for w in caught]
            record['warnings']=json.dumps(messages,ensure_ascii=False)
            for step,(date,actual,prediction) in enumerate(zip(validation['date'],validation['ev_total'],pred),1):
                traces.append({'config_id':config['config_id'],'fold':fold,'origin':origin,
                               'date':str(date.date()),'horizon':step,'actual':float(actual),'pred':float(prediction),
                               'status':record['status']})
        except Exception as error:
            record.update(status='failed',converged=False,error=f'{type(error).__name__}: {error}',
                          warnings=json.dumps([{'category':w.category.__name__,'message':str(w.message)} for w in caught],ensure_ascii=False))
        records.append(record)
    results=pd.DataFrame(records)
    return (results,pd.DataFrame(traces)) if return_forecasts else results
