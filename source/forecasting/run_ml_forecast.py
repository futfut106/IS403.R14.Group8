"""Select four regression models on train-only validation, then score fixed-origin test."""
from __future__ import annotations

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'source.forecasting'

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .backtest import run_cross_validation
from .features import FEATURE_NAMES
from .metrics import calculate_metrics
from .models import ml, ridge, random_forest, svr, xgboost
from .protocol import check_outputs, load_protocol, load_series, require

MODELS = {'ridge': ridge, 'random_forest': random_forest, 'svr': svr, 'xgboost': xgboost}
LABELS = {'ridge': 'Ridge', 'random_forest': 'Random Forest', 'svr': 'SVR', 'xgboost': 'XGBoost'}


def summarize_candidates(cv, spec):
    rows = []
    for config in spec['candidates']:
        part = cv.loc[cv['config_id'].eq(config['config_id'])]
        eligible = len(part) == 3 and part['status'].eq('ok').all()
        row = dict(config, eligible=bool(eligible), selected=False)
        for metric in ('rmse', 'mae', 'smape', 'bias'):
            row['mean_' + metric] = float(part[metric].mean()) if eligible else np.nan
        rows.append(row)
    scores = pd.DataFrame(rows)
    valid = scores.loc[scores['eligible']].copy()
    require(len(valid) > 0, 'No candidate completed all validation folds.')
    best = float(valid['mean_rmse'].min())
    threshold = best * (1 + spec['relative_tolerance'])
    pool = valid.loc[valid['mean_rmse'].le(threshold)]
    keys = spec['tie_keys']
    selected = pool.sort_values([key['column'] for key in keys],
                               ascending=[key['ascending'] for key in keys]).iloc[0]['config_id']
    scores['within_tolerance'] = scores['eligible'] & scores['mean_rmse'].le(threshold)
    scores['selected'] = scores['config_id'].eq(selected)
    return scores, next(dict(c) for c in spec['candidates'] if c['config_id'] == selected)


def forecast_frame(name, config_id, test, pred):
    return pd.DataFrame({'model': LABELS[name], 'config_id': config_id,
                         'date': test['date'].dt.strftime('%Y-%m-%d').to_numpy(),
                         'origin': load_protocol()['train_end'], 'horizon': np.arange(1, 13),
                         'actual': test['ev_total'].to_numpy(dtype=float), 'pred': pred,
                         'target_transform': 'level', 'evaluation_role': 'selected',
                         'lower_95': np.nan, 'upper_95': np.nan, 'interval_level': np.nan})


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def draw_figures(name, cv, scores, full, forecasts, figures):
    selected = scores.loc[scores['selected'], 'config_id'].iloc[0]
    fig, ax = plt.subplots(figsize=(9, 4.8), layout='constrained')
    for config_id, part in cv.groupby('config_id', sort=False):
        ax.plot(part['fold'], part['rmse'], marker='o', label=config_id,
                linewidth=2.5 if config_id == selected else 1, alpha=1 if config_id == selected else .65)
    ax.set(xticks=[1, 2, 3], xlabel='Validation fold', ylabel='RMSE (vehicles)',
           title=f'{LABELS[name]}: train-only validation; selected {selected}')
    ax.grid(alpha=.2)
    ax.legend(ncol=4, fontsize=8)
    fig.savefig(figures / f'{name}_validation.png', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4.8), layout='constrained')
    tail = full.iloc[59:]
    ax.plot(tail['date'], tail['ev_total'], color='black', label='Actual')
    ax.plot(pd.to_datetime(forecasts['date']), forecasts['pred'], 'o--', ms=3, label=LABELS[name])
    ax.axvline(pd.Timestamp(load_protocol()['train_end']), color='gray', linestyle=':', label='Forecast origin')
    ax.set(ylabel='EV Total (vehicles)', title=f'{LABELS[name]}: fixed-origin 12-month forecast ({selected})')
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
    ax.grid(alpha=.2)
    ax.legend()
    fig.savefig(figures / f'{name}_forecast.png', dpi=160)
    plt.close(fig)


def run(series_path, results, figures):
    full = load_series(series_path)
    train = full.loc[full['split'].eq('train')].copy()
    test = full.loc[full['split'].eq('test')].copy()
    outputs = [results / f'{stem}_{name}.{extension}' for name in MODELS
               for stem, extension in [('cv', 'csv'), ('validation_forecasts', 'csv'),
                                       ('candidate_scores', 'csv'), ('best', 'json'),
                                       ('forecast', 'csv'), ('trace', 'csv')]]
    outputs += [results / 'ml_test_metrics.csv', results / 'ml_run.json']
    outputs += [figures / f'{name}_{kind}.png' for name in MODELS for kind in ('validation', 'forecast')]
    check_outputs(outputs, [series_path])
    specs = {name: json.loads((Path(__file__).parent / 'configs' / f'{name}.json').read_text(encoding='utf-8'))
             for name in MODELS}
    validation = {}
    # Lock all four choices before fitting/scoring any model on the test window.
    for name, module in MODELS.items():
        folds, traces = [], []
        for config in specs[name]['candidates']:
            cv, trace = run_cross_validation(full, module.fit, module.forecast, config, return_forecasts=True)
            cv['n_supervised'] = cv['n_train_months'] - 7
            folds.append(cv)
            traces.append(trace)
        cv, trace = pd.concat(folds, ignore_index=True), pd.concat(traces, ignore_index=True)
        scores, selected = summarize_candidates(cv, specs[name])
        validation[name] = (cv, trace, scores, selected)
        print(f'{name}: locked {selected["config_id"]}', flush=True)
    fitted = {name: module.fit(train, validation[name][3]) for name, module in MODELS.items()}
    require(all(a['converged'] is not False for a in fitted.values()), 'Selected full-train fit did not converge.')
    results.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    metric_rows = []
    for name in MODELS:
        cv, trace, scores, config = validation[name]
        artifact = fitted[name]
        pred, recursive_trace = ml.forecast_with_trace(artifact, train, 12)
        forecast = forecast_frame(name, config['config_id'], test, pred)
        recursive_trace = pd.DataFrame(recursive_trace)
        recursive_trace.insert(0, 'date', test['date'].dt.strftime('%Y-%m-%d').to_numpy())
        recursive_trace.insert(0, 'config_id', config['config_id'])
        recursive_trace['origin'] = load_protocol()['train_end']
        recursive_trace['actual'] = test['ev_total'].to_numpy(dtype=float)
        for stem, frame in [('cv', cv), ('validation_forecasts', trace), ('candidate_scores', scores),
                            ('forecast', forecast), ('trace', recursive_trace)]:
            frame.to_csv(results / f'{stem}_{name}.csv', index=False, encoding='utf-8-sig')
        metadata = {'model': LABELS[name], 'config': config, 'selection': specs[name]['selection'],
                    'relative_tolerance': specs[name]['relative_tolerance'], 'tie_keys': specs[name]['tie_keys'],
                    'train_end': load_protocol()['train_end'], 'target_fit_scale': 'standardized_log_growth',
                    'export_scale': 'vehicles', 'fit': ml.describe(artifact)}
        save_json(results / f'best_{name}.json', metadata)
        metric_rows.append(dict(model=LABELS[name], config_id=config['config_id'], n_test=12,
                                **calculate_metrics(test['ev_total'], pred)))
        draw_figures(name, cv, scores, full, forecast, figures)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(results / 'ml_test_metrics.csv', index=False, encoding='utf-8-sig')
    save_json(results / 'ml_run.json', {
        'python': platform.python_version(), 'platform': platform.platform(),
        'packages': {p: version(p) for p in ['numpy', 'pandas', 'scipy', 'scikit-learn', 'xgboost', 'matplotlib', 'joblib', 'threadpoolctl']},
        'protocol': load_protocol(), 'feature_names': FEATURE_NAMES,
        'selection_locked_before_test': True, 'full_train_supervised_rows': 64,
        'validation_supervised_rows': [40, 46, 52], 'n_candidate_fits': 81,
        'prediction_intervals': 'not_estimated', 'random_seed': 42,
        'notes': ['No test update or test-based hyperparameter selection.',
                  'Validation windows overlap; fold scores are not independent samples.',
                  'Feature importances are training-model summaries, not causal effects.',
                  'This runner compares configurations within each family; final cross-family comparison is separate.']})
    print(metrics.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series', required=True, type=Path)
    parser.add_argument('--results-dir', required=True, type=Path)
    parser.add_argument('--figures-dir', required=True, type=Path)
    args = parser.parse_args()
    run(args.series, args.results_dir, args.figures_dir)


if __name__ == '__main__':
    main()
