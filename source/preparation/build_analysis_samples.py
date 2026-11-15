"""Prepare Range, CAFV and county samples; do not run hypothesis tests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

if __package__:
    from .build_monthly_series import COUNT_MAP, FIRST_MONTH, LAST_MONTH, load_history, require, write_outputs
else:
    from build_monthly_series import COUNT_MAP, FIRST_MONTH, LAST_MONTH, load_history, require, write_outputs

POPULATION_COLUMNS = [
    'County', 'City', 'State', 'Postal Code', 'Model Year', 'Make', 'Model',
    'Electric Vehicle Type', 'Clean Alternative Fuel Vehicle (CAFV) Eligibility',
    'Electric Range', 'Base MSRP',
]
TYPE_MAP = {'Battery Electric Vehicle (BEV)': 'BEV', 'Plug-in Hybrid Electric Vehicle (PHEV)': 'PHEV'}
UNKNOWN = 'Eligibility unknown as battery range has not been researched'
CAFV_LABELS = {UNKNOWN, 'Clean Alternative Fuel Vehicle Eligible', 'Not eligible due to low battery range'}


def load_population(path: Path) -> pd.DataFrame:
    population = pd.read_csv(path, low_memory=False)
    require(list(population.columns) == POPULATION_COLUMNS, 'Population must have the expected eleven clean columns in order.')
    require(len(population) > 0 and population['State'].eq('WA').all(), 'Population must be nonempty and contain WA only.')
    required = ['County', 'Electric Vehicle Type', 'Clean Alternative Fuel Vehicle (CAFV) Eligibility']
    require(population[required].notna().all().all(), 'Population is missing a county, vehicle type or CAFV label.')
    require(population['County'].nunique() == 39, 'Population must cover 39 Washington counties.')
    require(set(population['Electric Vehicle Type']) == set(TYPE_MAP), 'Population has unexpected vehicle type labels.')
    require(set(population['Clean Alternative Fuel Vehicle (CAFV) Eligibility']).issubset(CAFV_LABELS), 'Population has unexpected CAFV labels.')
    for col in ['Model Year', 'Electric Range']:
        population[col] = pd.to_numeric(population[col], errors='raise')
        require(not population[col].isin([float('inf'), -float('inf')]).any(), f'Nonfinite value in {col}.')
    year = population['Model Year'].dropna()
    require(year.gt(0).all() and year.mod(1).eq(0).all(), 'Nonmissing Model Year values must be positive integers.')
    require(population['Electric Range'].dropna().gt(0).all(), 'Clean Range must be positive or missing; run preprocessing for zero values.')
    return population


def build_analysis_samples(population: pd.DataFrame, history: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Preserve Population multiplicity and mark sensitivity subsets explicitly."""
    require(set(population['County']) == set(history['County']), 'County coverage differs between Population and History.')
    base = pd.DataFrame({
        'source_record': range(1, len(population) + 1),
        'county': population['County'],
        'vehicle_type': population['Electric Vehicle Type'].map(TYPE_MAP),
        'model_year': population['Model Year'],
        'electric_range': population['Electric Range'],
    })
    ranges = base.loc[base['electric_range'].notna()].copy()
    ranges['h1_year_le_2020'] = ranges['model_year'].notna() & ranges['model_year'].le(2020)
    ranges['h2_valid'] = ranges['model_year'].notna()
    cafv = base[['source_record', 'county', 'vehicle_type']].copy()
    cafv['cafv_status'] = population['Clean Alternative Fuel Vehicle (CAFV) Eligibility']
    cafv['cafv_known'] = cafv['cafv_status'].ne(UNKNOWN)
    county = pd.crosstab(base['county'], base['vehicle_type']).reindex(columns=['BEV', 'PHEV'], fill_value=0)
    county = county.rename(columns={'BEV': 'bev', 'PHEV': 'phev'}).rename_axis(columns=None).reset_index()
    county['ev_total'] = county['bev'] + county['phev']
    county['included_h4a_sensitivity'] = county['ev_total'].ge(30)
    require(int(county['ev_total'].sum()) == len(population), 'County counts do not preserve Population rows.')
    cuts = history.loc[history['Date'].isin(pd.to_datetime([FIRST_MONTH, LAST_MONTH]))]
    snapshots = cuts.groupby(['Date', 'County'], as_index=False, sort=True)[list(COUNT_MAP)].sum()
    snapshots = snapshots.rename(columns={'Date': 'date', 'County': 'county', **COUNT_MAP})
    snapshots['ev_pct'] = 100 * snapshots['ev_total'] / snapshots['total_vehicles']
    snapshots['date'] = snapshots['date'].dt.strftime('%Y-%m-%d')
    require(snapshots.groupby('date').size().to_dict() == {FIRST_MONTH: 39, LAST_MONTH: 39}, 'Each snapshot must have 39 counties.')
    rows = []

    def add(sample: str, source: str, row_count: int, vehicles: int, counties: int, condition: str) -> None:
        rows.append({'sample': sample, 'source': source, 'rows': int(row_count),
                     'vehicle_count': int(vehicles), 'counties': int(counties), 'condition': condition})

    def add_range(label: str, frame: pd.DataFrame, condition: str) -> None:
        add(label, 'Population clean', len(frame), len(frame), frame['county'].nunique(), condition)

    add_range('h1_primary', ranges, 'electric_range is not missing')
    for kind in ['BEV', 'PHEV']:
        add_range(f'h1_primary_{kind.lower()}', ranges.loc[ranges['vehicle_type'].eq(kind)], f'valid Range; vehicle_type={kind}')
    add_range('h1_sensitivity', ranges.loc[ranges['h1_year_le_2020']], 'valid Range; Model Year <= 2020')
    h2 = ranges.loc[ranges['h2_valid']]
    add_range('h2_primary', h2, 'Range and Model Year are not missing')
    for kind in ['BEV', 'PHEV']:
        add_range(f'h2_{kind.lower()}', h2.loc[h2['vehicle_type'].eq(kind)], f'valid Range/year; vehicle_type={kind}')
    known = cafv.loc[cafv['cafv_known']]
    add('h3_primary', 'Population clean', len(known), len(known), known['county'].nunique(), 'cafv_known=True')
    add('h3_sensitivity', 'Population clean', len(cafv), len(cafv), cafv['county'].nunique(), 'all CAFV labels, including Unknown')
    add('h4a_primary', 'Population clean', len(county), int(county['ev_total'].sum()), len(county), 'all counties; rows are county aggregates')
    sensitive = county.loc[county['included_h4a_sensitivity']]
    add('h4a_sensitivity', 'Population clean', len(sensitive), int(sensitive['ev_total'].sum()), len(sensitive), 'county ev_total >= 30')
    for date, label in [(LAST_MONTH, 'h4b_primary'), (FIRST_MONTH, 'h4b_sensitivity')]:
        frame = snapshots.loc[snapshots['date'].eq(date)]
        add(label, 'History clean', len(frame), int(frame['total_vehicles'].sum()), len(frame), f'date={date}; sum Passenger and Truck; test each month separately')
    samples = {
        'range_analysis_sample.csv': ranges.reset_index(drop=True),
        'cafv_analysis_sample.csv': cafv,
        'county_vehicle_type_counts.csv': county,
        'county_ev_snapshots.csv': snapshots,
    }
    return samples, pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-clean', type=Path, required=True)
    parser.add_argument('--history-clean', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--summary-dir', type=Path, required=True)
    args = parser.parse_args()
    samples, summary = build_analysis_samples(load_population(args.population_clean), load_history(args.history_clean))
    outputs = {args.output_dir/name: frame for name, frame in samples.items()}
    outputs[args.summary_dir/'sample_summary.csv'] = summary
    write_outputs(outputs, [args.population_clean, args.history_clean])
    print(json.dumps({'sample_rows': {name: len(frame) for name, frame in samples.items()}}, indent=2))


if __name__ == '__main__':
    main()
