"""Run H1-H4 and their planned sensitivity analyses from prepared samples."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import scipy

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.inference import range_tests, cafv_test, county_tests
from source.inference.contingency import ALPHA, BATCH, N_RESAMPLES, SEED, check_outputs, require

CSV_NAMES=['range_tests.csv','range_year_summary.csv','cafv_tests.csv','cafv_contingency.csv',
           'county_tests.csv','county_contingency.csv','hypothesis_summary.csv']
FIGURE_NAMES=['range_by_model_year.png','cafv_by_vehicle_type.png','county_vehicle_type_share.png']


def validate_sample_consistency(ranges: pd.DataFrame,cafv: pd.DataFrame,counties: pd.DataFrame,snapshots: pd.DataFrame) -> None:
    paired=ranges.merge(cafv[['source_record','county','vehicle_type']],on='source_record',how='left',
                        suffixes=('_range','_cafv'),validate='one_to_one',indicator=True)
    require(paired['_merge'].eq('both').all(),'Range source records are missing from CAFV Population sample.')
    for column in ['county','vehicle_type']:
        require(paired[column+'_range'].eq(paired[column+'_cafv']).all(),'Prepared Population samples disagree on '+column)
    counts=pd.crosstab(cafv['county'],cafv['vehicle_type']).reindex(columns=['BEV','PHEV'],fill_value=0).sort_index()
    supplied=counties.sort_values('county').set_index('county')
    require(counts.index.equals(supplied.index),'CAFV and county samples have different county coverage.')
    require(np.array_equal(counts.to_numpy(),supplied[['bev','phev']].to_numpy()),'County composition does not reproduce CAFV Population counts.')
    require(int(supplied['ev_total'].sum())==len(cafv),'County totals differ from the Population sample size.')
    for date in county_tests.DATES:
        require(set(snapshots.loc[snapshots['date'].eq(date),'county'])==set(counties['county']),'History snapshot county coverage differs.')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples-dir',type=Path,required=True,help='Directory containing the four preparation sample CSVs.')
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    args=parser.parse_args()
    names=['range_analysis_sample.csv','cafv_analysis_sample.csv','county_vehicle_type_counts.csv','county_ev_snapshots.csv']
    inputs=[args.samples_dir/name for name in names]
    check_outputs([*(args.results_dir/name for name in [*CSV_NAMES,'inference_settings.json']),
                   *(args.figures_dir/name for name in FIGURE_NAMES)],inputs)
    ranges=range_tests.load_range(inputs[0])
    cafv=cafv_test.load_cafv(inputs[1])
    counties=county_tests.load_counties(inputs[2])
    snapshots=county_tests.load_snapshots(inputs[3])
    validate_sample_consistency(ranges,cafv,counties,snapshots)
    range_results,year_summary=range_tests.run_tests(ranges)
    cafv_results,cafv_cells=cafv_test.run_tests(cafv)
    county_results,county_cells=county_tests.run_tests(counties,snapshots)
    columns=['hypothesis','sample','status','n','statistic_name','statistic','df_theoretical',
             'p_method','p_value','p_display','p_numerical_underflow','p_value_upper_bound',
             'nominal_alpha','reject_h0','effect_name','effect_size','effect_definition',
             'expected_min','expected_cells_lt_5','expected_cells_lt_1','mc_resamples','mc_seed',
             'mc_resolution','mc_at_resolution_limit']
    summary=pd.concat([range_results,cafv_results,county_results],ignore_index=True).reindex(columns=columns)
    settings={
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__},
        'input_files':names,'nominal_alpha':ALPHA,
        'multiple_testing':'Unadjusted per-test p-values; no familywise/FDR control is claimed. Sensitivity analyses do not select the preferred conclusion.',
        'range':{'primary_rows':len(ranges),'year_le_2020_rows':int(ranges['h1_year_le_2020'].sum()),
                 'population_rows':len(cafv),'missing_range_rows':len(cafv)-len(ranges),
                 'h1_method':'Two-sided asymptotic Mann-Whitney U; tie correction and continuity correction; first group=BEV.',
                 'h1_effect':'A=U_BEV/(n_BEV*n_PHEV); rank-biserial=2*A-1.',
                 'h2_method':'Two-sided Spearman; asymptotic t approximation; all valid pairs and separate BEV/PHEV analyses.',
                 'quartiles':'Linear interpolation on valid Range values.'},
        'cafv':{'primary_rows':int(cafv['cafv_known'].sum()),'sensitivity_rows':len(cafv),
                'unknown_label':cafv_test.UNKNOWN,'correction':False},
        'county':{'h4a_primary':'All 39 counties; Monte Carlo fixed-margin Pearson chi-square.',
                  'h4a_sensitivity':'Exclude counties with fewer than 30 EV; use asymptotic chi-square only when all expected cells >=5, otherwise Monte Carlo.',
                  'excluded_in_sensitivity':sorted(counties.loc[~counties['included_h4a_sensitivity'],'county'].tolist()),
                  'h4b_primary_date':'2023-11-30','h4b_sensitivity_date':'2017-01-31',
                  'h4b_sample_unit':'Vehicle counts in each separate month; do not pool months as independent vehicles.'},
        'monte_carlo':{'n_resamples':N_RESAMPLES,'batch':BATCH,'seed':SEED,
                       'sampling':'SciPy random_table conditional on fixed row and column margins.',
                       'resolution':1/(N_RESAMPLES+1),'df_reporting':'Theoretical (rows-1)*(columns-1); SciPy resampling dof is not used.',
                       'floor_interpretation':'At the minimum estimate, report the finite simulation resolution, not p=0 or an upper bound on the true p-value.'},
        'p_underflow':'When SciPy returns numerical zero, leave p_value empty, mark p_numerical_underflow and report <1e-300; no exact p=0 claim.',
        'limitations':['Administrative observational records do not establish causality.',
                       'Range availability differs by vehicle type and model year; valid Range records are not a complete representation of every group.',
                       'Statistical significance does not by itself measure business importance or justify policy effects.'],
    }
    range_tests.export_figure(year_summary,args.figures_dir)
    cafv_test.export_figure(cafv,args.figures_dir)
    county_tests.export_figure(counties,args.figures_dir)
    args.results_dir.mkdir(parents=True,exist_ok=True)
    tables=dict(zip(CSV_NAMES,[range_results,year_summary,cafv_results,cafv_cells,county_results,county_cells,summary]))
    for name,table in tables.items():
        table.to_csv(args.results_dir/name,index=False,encoding='utf-8-sig',lineterminator='\n')
    (args.results_dir/'inference_settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(summary[['hypothesis','sample','n','statistic','p_display','effect_size']].to_string(index=False))


if __name__=='__main__':
    main()
