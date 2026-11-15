"""Align locked forecasts and recompute descriptive out-of-sample comparisons."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from .metrics import calculate_metrics
from .protocol import load_protocol, require

FAMILIES = {'ARIMA': 'arima', 'SARIMA': 'sarima', 'Ridge': 'ridge',
            'Random Forest': 'random_forest', 'SVR': 'svr', 'XGBoost': 'xgboost'}
MODEL_ORDER = ['Naive', 'Drift', *FAMILIES]
SCHEMA = ['model', 'config_id', 'date', 'origin', 'horizon', 'actual', 'pred',
          'target_transform', 'evaluation_role', 'lower_95', 'upper_95', 'interval_level']
FORECAST_FILES = ['forecast_baselines.csv'] + [f'forecast_{name}.csv' for name in FAMILIES.values()]


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_inputs(directory: Path, series: pd.DataFrame):
    protocol = load_protocol()
    test = series.loc[series['split'].eq('test')].reset_index(drop=True)
    selected, excluded, choices = [], [], {}
    expected_groups = {'forecast_baselines.csv': [('Naive', 'NAIVE'), ('Drift', 'DRIFT')]}
    for model, suffix in FAMILIES.items():
        metadata = load_json(directory / f'best_{suffix}.json')
        choices[model] = metadata
        expected_groups[f'forecast_{suffix}.csv'] = [(model, metadata['config']['config_id'])]
    for filename in FORECAST_FILES:
        frame = pd.read_csv(directory / filename, encoding='utf-8-sig')
        require(list(frame.columns) == SCHEMA, f'Unexpected forecast schema: {filename}')
        require(frame[SCHEMA[:9]].notna().all().all(), f'Missing forecast cells: {filename}')
        require(not frame.duplicated(['model', 'config_id', 'date']).any(), f'Duplicate dates: {filename}')
        expected = set(expected_groups[filename])
        found = set()
        for (model, cid), part in frame.groupby(['model', 'config_id'], sort=False):
            require(len(part) == 12 and part['horizon'].tolist() == list(range(1, 13)), f'Invalid horizon: {cid}')
            dates = pd.to_datetime(part['date'], format='%Y-%m-%d', errors='raise')
            require(list(dates) == list(test['date']), f'Misaligned test dates: {cid}')
            require(part['origin'].eq(protocol['train_end']).all(), f'Mixed forecast origins: {cid}')
            require(part['target_transform'].eq('level').all(), f'Forecast is not on level scale: {cid}')
            actual, pred = part['actual'].to_numpy(dtype=float), part['pred'].to_numpy(dtype=float)
            require(np.isfinite(actual).all() and np.isfinite(pred).all() and (pred > 0).all(), f'Invalid values: {cid}')
            require(np.array_equal(actual, test['ev_total'].to_numpy(dtype=float)), f'Actual differs from prepared series: {cid}')
            role = 'baseline' if model in ['Naive', 'Drift'] else 'selected'
            if (model, cid) in expected:
                require(part['evaluation_role'].eq(role).all(), f'Incorrect selected role: {cid}')
                selected.append(part.copy())
                found.add((model, cid))
            else:
                require(filename == 'forecast_sarima.csv' and model == 'SARIMA'
                        and part['evaluation_role'].eq('candidate_reference').all(), f'Unexpected forecast group: {cid}')
                excluded.append({'model': model, 'config_id': cid, 'reason': 'candidate_reference', 'rows': len(part)})
            intervals = part[['lower_95', 'upper_95', 'interval_level']]
            if model in ['ARIMA', 'SARIMA']:
                require(intervals.notna().all().all() and np.isfinite(intervals.to_numpy(dtype=float)).all(), f'Missing/invalid interval: {cid}')
                require(part['interval_level'].eq(.95).all(), f'Unexpected interval level: {cid}')
                require(part['lower_95'].le(part['pred']).all() and part['pred'].le(part['upper_95']).all(), f'Unordered interval: {cid}')
            else:
                require(intervals.isna().all().all(), f'Unsupported interval for {model}')
        require(found == expected, f'Missing locked forecast: {filename}')
    aligned = pd.concat(selected, ignore_index=True)
    require(len(aligned) == 96 and set(aligned['model']) == set(MODEL_ORDER), 'Expected eight methods and 96 predictions.')
    return aligned, choices, excluded


def selection_summary(directory, choices):
    records = []
    for model, suffix in FAMILIES.items():
        metadata = choices[model]
        cid = metadata['config']['config_id']
        row = {'model': model, 'config_id': cid, 'train_end': load_protocol()['train_end'],
               'train_months': 71, 'selection_metric': 'train_AIC' if model == 'ARIMA' else 'mean_validation_RMSE',
               'selection_value': None, 'cv_folds': 0 if model == 'ARIMA' else 3,
               'n_supervised': None if model in ['ARIMA', 'SARIMA'] else 64,
               'wald_inference_caution': metadata.get('train_fit', {}).get('wald_inference_caution'),
               'selection_rule': metadata['selection']}
        if model == 'ARIMA':
            require(metadata['train_fit']['converged'] is True, 'Selected ARIMA did not converge.')
            row['selection_value'] = metadata['train_fit']['aic']
        else:
            cv = pd.read_csv(directory / f'cv_{suffix}.csv', encoding='utf-8-sig')
            part = cv.loc[cv['config_id'].eq(cid)].copy()
            require(len(part) == 3 and part['fold'].tolist() == [1, 2, 3]
                    and part['status'].eq('ok').all(), f'Invalid locked CV result: {cid}')
            require(part['n_train_months'].tolist() == [47, 53, 59]
                    and part['origin'].tolist() == load_protocol()['cv_origins'], f'Invalid CV prefixes: {cid}')
            require(part['horizon'].eq(12).all(), f'Invalid CV horizon: {cid}')
            require(np.isfinite(part['rmse']).all(), f'Invalid CV scores: {cid}')
            row['selection_value'] = float(part['rmse'].mean())
            if model == 'SARIMA':
                require(metadata['train_fit']['converged'] is True, 'Selected SARIMA did not converge.')
                require(np.isclose(row['selection_value'], metadata['mean_cv_rmse'], rtol=1e-10), 'SARIMA CV disagrees with metadata.')
            else:
                require(metadata['fit']['converged'] is not False, f'Selected fit did not converge: {cid}')
                require(metadata['fit']['n_supervised'] == 64, f'Unexpected ML sample size: {cid}')
        records.append(row)
    summary = pd.DataFrame(records)
    summary['n_supervised'] = summary['n_supervised'].astype('Int64')
    summary['wald_inference_caution'] = summary['wald_inference_caution'].astype('boolean')
    return summary


def compare(aligned):
    errors = aligned.copy()
    errors['error'] = errors['actual'] - errors['pred']
    errors['absolute_error'] = errors['error'].abs()
    errors['squared_error'] = errors['error'] ** 2
    errors['smape_component'] = 200 * errors['absolute_error'] / (errors['actual'].abs() + errors['pred'].abs())
    metrics, cumulative, intervals = [], [], []
    for model in MODEL_ORDER:
        part = errors.loc[errors['model'].eq(model)].sort_values('horizon')
        metrics.append({'model': model, 'config_id': part['config_id'].iloc[0], 'n_test': 12,
                        'origin': part['origin'].iloc[0], **calculate_metrics(part['actual'], part['pred']),
                        'months_underpredicted': int(part['error'].gt(0).sum()),
                        'months_overpredicted': int(part['error'].lt(0).sum())})
        for h in range(1, 13):
            prefix = part.iloc[:h]
            cumulative.append({'model': model, 'config_id': part['config_id'].iloc[0],
                               'through_date': prefix['date'].iloc[-1], 'through_horizon': h,
                               **calculate_metrics(prefix['actual'], prefix['pred'])})
        if part['interval_level'].notna().all():
            covered = part['actual'].ge(part['lower_95']) & part['actual'].le(part['upper_95'])
            intervals.append({'model': model, 'config_id': part['config_id'].iloc[0], 'n_test': 12,
                              'nominal_level': .95, 'covered_months': int(covered.sum()),
                              'observed_coverage': float(covered.mean()),
                              'mean_width': float((part['upper_95'] - part['lower_95']).mean())})
    scores = pd.DataFrame(metrics)
    for metric in ['rmse', 'mae', 'smape']:
        scores['rank_' + metric] = scores[metric].rank(method='min', ascending=True).astype(int)
        for baseline in ['Naive', 'Drift']:
            reference = float(scores.loc[scores['model'].eq(baseline), metric].iloc[0])
            require(reference > 0, f'Zero baseline metric prevents relative improvement: {baseline}/{metric}')
            scores[f'{metric}_improvement_vs_{baseline.lower()}_pct'] = 100 * (1 - scores[metric] / reference)
    scores = scores.sort_values(['rmse', 'model']).reset_index(drop=True)
    predictions = aligned.pivot(index=['date', 'actual'], columns='model', values='pred').reset_index()
    predictions.columns.name = None
    predictions = predictions[['date', 'actual', *MODEL_ORDER]]
    return {'comparison_metrics.csv': scores, 'comparison_predictions.csv': predictions,
            'comparison_errors.csv': errors, 'comparison_cumulative_metrics.csv': pd.DataFrame(cumulative),
            'comparison_interval_summary.csv': pd.DataFrame(intervals)}


def verify_published_metrics(directory, scores):
    previous = pd.concat([pd.read_csv(directory / 'statistical_test_metrics.csv'),
                          pd.read_csv(directory / 'ml_test_metrics.csv')], ignore_index=True)
    for row in scores.to_dict('records'):
        match = previous.loc[previous['model'].eq(row['model']) & previous['config_id'].eq(row['config_id'])]
        require(len(match) == 1, f'Missing/ambiguous published metrics for {row["model"]}')
        for metric in ['rmse', 'mae', 'smape', 'bias']:
            require(np.isclose(row[metric], match[metric].iloc[0], rtol=1e-10, atol=1e-8),
                    f'Recomputed {metric} differs from published result: {row["model"]}')
