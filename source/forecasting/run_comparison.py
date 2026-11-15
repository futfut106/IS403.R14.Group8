"""Compare already locked forecasts without fitting or retuning any model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import platform

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'source.forecasting'

from .comparison import (FAMILIES, FORECAST_FILES, compare, read_inputs,
                         selection_summary, verify_published_metrics)
from .comparison_plots import FIGURES, draw
from .protocol import check_outputs, load_protocol, load_series

TABLES = ['comparison_metrics.csv', 'comparison_predictions.csv', 'comparison_errors.csv',
          'comparison_cumulative_metrics.csv', 'comparison_interval_summary.csv', 'comparison_selection_summary.csv']


def run(series_path, forecast_dir, results_dir, figures_dir):
    inputs = [series_path] + [forecast_dir / f for f in FORECAST_FILES]
    inputs += [forecast_dir / f'best_{suffix}.json' for suffix in FAMILIES.values()]
    inputs += [forecast_dir / f'cv_{suffix}.csv' for model, suffix in FAMILIES.items() if model != 'ARIMA']
    inputs += [forecast_dir / 'statistical_test_metrics.csv', forecast_dir / 'ml_test_metrics.csv']
    outputs = [results_dir / f for f in TABLES + ['comparison_run.json']] + [figures_dir / f for f in FIGURES]
    check_outputs(outputs, inputs)
    series = load_series(series_path)
    aligned, choices, excluded = read_inputs(forecast_dir, series)
    tables = compare(aligned)
    tables['comparison_selection_summary.csv'] = selection_summary(forecast_dir, choices)
    verify_published_metrics(forecast_dir, tables['comparison_metrics.csv'])
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    for filename, table in tables.items():
        table.to_csv(results_dir / filename, index=False, encoding='utf-8-sig')
    draw(tables, figures_dir)
    scores = tables['comparison_metrics.csv']
    best = scores.iloc[0]
    run_record = {'protocol': load_protocol(), 'python': platform.python_version(),
                  'input_files': [p.name for p in inputs], 'model_count': 8, 'prediction_count': 96,
                  'excluded_groups': excluded, 'no_model_refit_or_retuning': True,
                  'lowest_test_rmse': {'model': best['model'], 'config_id': best['config_id'], 'rmse': float(best['rmse'])},
                  'checks_completed': ['Prepared monthly series schema and dates validated.',
                                       'Eight locked methods aligned to the same actuals, origin, level scale and 12 steps.',
                                       'Selected IDs agree with per-family best metadata.',
                                       'Selected CV prefixes and fit status validated.',
                                       'Recomputed test metrics match published package 3/4 metrics.',
                                       'Intervals validated only for selected ARIMA/SARIMA.'],
                  'cautions': ['Test ranking describes one 12-month fixed-origin window; no statistical superiority claim.',
                               'Final ranking does not retune configurations or provide a new unseen test for a deployed winner.',
                               'ARIMA covariance/near-unit-root caution remains in best_arima.json; do not infer reliable Wald tests.',
                               'Cumulative errors are nested prefixes, not independent repeated test origins.',
                               'Observed 12-month interval coverage is not a long-run 95% calibration guarantee.',
                               'No causal policy, sales, electricity load or charging-station estimate is identified.']}
    (results_dir / 'comparison_run.json').write_text(json.dumps(run_record, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(scores[['rank_rmse', 'model', 'config_id', 'rmse', 'mae', 'smape', 'bias']].to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series', required=True, type=Path)
    parser.add_argument('--forecast-dir', required=True, type=Path)
    parser.add_argument('--results-dir', required=True, type=Path)
    parser.add_argument('--figures-dir', required=True, type=Path)
    args = parser.parse_args()
    run(args.series, args.forecast_dir, args.results_dir, args.figures_dir)


if __name__ == '__main__':
    main()
