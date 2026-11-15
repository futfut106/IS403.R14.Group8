"""Validate History clean and aggregate the statewide monthly EV series."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

HISTORY_COLUMNS = [
    'Date', 'County', 'State', 'Vehicle Primary Use',
    'Battery Electric Vehicles (BEVs)', 'Plug-In Hybrid Electric Vehicles (PHEVs)',
    'Electric Vehicle (EV) Total', 'Non-Electric Vehicle Total',
    'Total Vehicles', 'Percent Electric Vehicles',
]
COUNT_MAP = dict(zip(HISTORY_COLUMNS[4:9], ['bev', 'phev', 'ev_total', 'non_ev', 'total_vehicles']))
FIRST_MONTH = '2017-01-31'
LAST_MONTH = '2023-11-30'
TRAIN_END = '2022-11-30'
TEST_START = '2022-12-31'


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise ValueError(message)


def load_history(path: Path) -> pd.DataFrame:
    """Read the study's clean History; validate without changing its source."""
    history = pd.read_csv(path, low_memory=False)
    require(list(history.columns) == HISTORY_COLUMNS, 'History must have the expected ten clean columns in order.')
    require(len(history) > 0 and history.notna().all().all(), 'History must be nonempty and contain no missing cells.')
    require(history['State'].eq('WA').all(), 'History must contain WA only.')
    require(set(history['Vehicle Primary Use']) == {'Passenger', 'Truck'}, 'Expected Passenger and Truck use groups.')
    require(history['County'].nunique() == 39, 'History must cover 39 Washington counties.')
    history['Date'] = pd.to_datetime(history['Date'], format='%Y-%m-%d', errors='raise')
    dates = pd.DatetimeIndex(sorted(history['Date'].unique()))
    expected_dates = pd.period_range('2017-01', '2023-11', freq='M').to_timestamp('M')
    require(dates.equals(expected_dates), 'History must cover all 83 month ends from 01/2017 through 11/2023.')
    keys = ['Date', 'County', 'Vehicle Primary Use']
    require(not history.duplicated(keys).any(), 'History contains duplicate month/county/use keys.')
    expected_keys = pd.MultiIndex.from_product(
        [expected_dates, sorted(history['County'].unique()), ['Passenger', 'Truck']], names=keys)
    actual_keys = pd.MultiIndex.from_frame(history[keys])
    require(len(actual_keys) == len(expected_keys) and len(expected_keys.difference(actual_keys)) == 0,
            'History is missing month/county/use combinations.')
    for col in HISTORY_COLUMNS[4:]:
        history[col] = pd.to_numeric(history[col], errors='raise')
        require(history[col].notna().all() and not history[col].isin([float('inf'), -float('inf')]).any(),
                f'History contains a nonfinite numeric value: {col}')
    counts = history[list(COUNT_MAP)]
    require(counts.ge(0).all().all() and counts.mod(1).eq(0).all().all(), 'Vehicle counts must be nonnegative integers.')
    history[list(COUNT_MAP)] = counts.astype('int64')
    bev, phev, ev, non_ev, total = list(COUNT_MAP)
    require(history[bev].add(history[phev]).eq(history[ev]).all(), 'BEV + PHEV differs from EV Total.')
    require(history[ev].add(history[non_ev]).eq(history[total]).all(), 'EV + non-EV differs from Total Vehicles.')
    require(history[total].gt(0).all(), 'Total Vehicles must be positive.')
    pct = (100 * history[ev] / history[total]).round(2)
    require(history[HISTORY_COLUMNS[-1]].sub(pct).abs().le(1e-9).all(), 'History percentage differs from its counts.')
    return history


def build_monthly_series(history: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aggregate validated History counts, then calculate ratios and splits."""
    monthly = history.groupby('Date', sort=True)[list(COUNT_MAP)].sum().rename(columns=COUNT_MAP).reset_index()
    monthly = monthly.rename(columns={'Date': 'date'})
    monthly['ev_pct'] = 100 * monthly['ev_total'] / monthly['total_vehicles']
    monthly['split'] = monthly['date'].le(pd.Timestamp(TRAIN_END)).map({True: 'train', False: 'test'})
    require(monthly['ev_total'].gt(0).all(), 'Monthly EV totals must be positive.')
    require(monthly['split'].value_counts().to_dict() == {'train': 71, 'test': 12}, 'Expected 71 train months and 12 test months.')
    require(monthly.loc[monthly['split'].eq('test'), 'date'].min() == pd.Timestamp(TEST_START), 'Incorrect first test month.')
    monthly['date'] = monthly['date'].dt.strftime('%Y-%m-%d')
    summary = {
        'history_rows': int(len(history)), 'counties': int(history['County'].nunique()),
        'use_groups': sorted(history['Vehicle Primary Use'].unique().tolist()),
        'rows_per_month': 78, 'monthly_rows': int(len(monthly)),
        'first_month': FIRST_MONTH, 'last_month': LAST_MONTH,
        'train': {'start': FIRST_MONTH, 'end': TRAIN_END, 'months': 71},
        'test': {'start': TEST_START, 'end': LAST_MONTH, 'months': 12},
        'columns': monthly.columns.tolist(), 'count_unit': 'vehicles', 'ev_pct_unit': 'percent',
        'aggregation': 'Sum count columns across counties and both use groups; ev_pct = 100 * ev_total / total_vehicles.',
        'features_created': False,
    }
    return monthly, summary


def write_outputs(outputs: dict[Path, object], inputs: list[Path]) -> None:
    """Check all destination paths before writing any CSV or summary."""
    resolved = [path.resolve() for path in outputs]
    require(len(set(resolved)) == len(resolved), 'Output paths must be distinct.')
    input_paths = {path.resolve() for path in inputs}
    for path in outputs:
        require(path.resolve() not in input_paths and not path.exists(), f'Choose a new output path: {path}')
    for path, value in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, pd.DataFrame):
            value.to_csv(path, index=False, encoding='utf-8-sig', lineterminator='\n')
        else:
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-clean', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True, help='Local directory for derived input CSVs.')
    parser.add_argument('--summary-dir', type=Path, required=True, help='Directory for preparation summaries.')
    args = parser.parse_args()
    monthly, summary = build_monthly_series(load_history(args.history_clean))
    write_outputs({args.output_dir/'statewide_monthly.csv': monthly,
                   args.summary_dir/'monthly_series_summary.json': summary}, [args.history_clean])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
