"""Clean the two Washington EV raw datasets and summarize data quality."""
from pathlib import Path
import argparse
import json
import sys
import pandas as pd
from clean_population import clean_population, write_csv
from clean_history import clean_history


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_data(population, history, population_audit, history_audit):
    require(set(population.State) == {'WA'}, 'Population must contain WA only.')
    require(set(history.State) == {'WA'}, 'History must contain WA only.')
    require(len(population) == population_audit['raw_shape'][0] - population_audit['removed_rows_non_WA'], 'Population row accounting failed.')
    require(not population[['Electric Range', 'Base MSRP']].eq(0).any().any(), 'Range/MSRP zeros remain.')
    key = ['Date', 'County', 'Vehicle Primary Use']
    require(not history.isna().any().any(), 'History contains missing values.')
    require(not history.duplicated(key).any(), 'History key is duplicated.')
    counts = history.iloc[:, 4:9]
    require(counts.ge(0).all().all() and counts.mod(1).eq(0).all().all(), 'Vehicle counts must be nonnegative integers.')
    require(history.iloc[:, 4].add(history.iloc[:, 5]).eq(history.iloc[:, 6]).all(), 'BEV + PHEV differs from EV.')
    require(history.iloc[:, 6].add(history.iloc[:, 7]).eq(history.iloc[:, 8]).all(), 'EV + non-EV differs from total.')
    require(history['Total Vehicles'].gt(0).all(), 'Total Vehicles must be positive.')
    require((100 * history.iloc[:, 6] / history.iloc[:, 8]).round(2).eq(history.iloc[:, 9]).all(), 'EV percentage is inconsistent.')
    dates = pd.DatetimeIndex(pd.to_datetime(sorted(history.Date.unique())))
    require(dates.is_month_end.all(), 'Dates must be month ends.')
    require(dates.to_period('M').equals(pd.period_range(dates.min(), dates.max(), freq='M')), 'Months are not consecutive.')
    expected = pd.MultiIndex.from_product([sorted(history[c].unique()) for c in key], names=key)
    observed = pd.MultiIndex.from_frame(history[key])
    require(len(expected.difference(observed)) == 0 and len(expected) == len(history), 'History grid is incomplete.')
    return {
        'environment': {'python': sys.version.split()[0], 'pandas': pd.__version__},
        'population': population_audit,
        'history': history_audit,
        'quality': {
            'WA_only': True, 'population_row_accounting_valid': True,
            'population_range_msrp_zeros': 0,
            'history_missing_cells': 0, 'history_duplicate_keys': 0,
            'history_complete_combinations': len(expected),
            'history_consecutive_months': len(dates),
            'history_count_identities_valid': True,
            'history_percentages_valid': True,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-raw', type=Path, required=True, help='Path to the Population raw CSV.')
    parser.add_argument('--history-raw', type=Path, required=True, help='Path to the History raw CSV.')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.population_raw, args.history_raw]
    paths = [args.output_dir/name for name in ['EV_Population_Washington_Clean.csv', 'EV_Population_History_Washington_Clean.csv', 'data_quality_summary.json']]
    for path in inputs:
        require(path.is_file(), f'Input not found: {path}')
    for path in paths:
        require(path.resolve() not in [p.resolve() for p in inputs] and not path.exists(), f'Choose a new output path: {path}')
    population, pa = clean_population(args.population_raw)
    history, ha = clean_history(args.history_raw)
    summary = check_data(population, history, pa, ha)
    write_csv(population, paths[0])
    write_csv(history, paths[1])
    paths[2].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'population': list(population.shape), 'history': list(history.shape), 'quality': summary['quality']}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
