"""Shared input checks, p-value reporting and Pearson contingency calculations."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05
N_RESAMPLES = 99999
SEED = 42
BATCH = 1000


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise ValueError(message)


def read_sample(path: Path, columns: list[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding='utf-8-sig', low_memory=False)
    require(list(frame.columns) == columns, f'Prepared sample schema differs: {path.name}')
    require(not frame.empty, f'Prepared sample is empty: {path.name}')
    return frame


def numeric(frame: pd.DataFrame, columns: list[str], allow_missing: bool = False) -> None:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors='raise')
        require(not frame[column].isin([np.inf, -np.inf]).any(), f'Nonfinite input: {column}')
        require(allow_missing or frame[column].notna().all(), f'Missing input: {column}')


def boolean_flag(series: pd.Series, label: str) -> pd.Series:
    require(series.notna().all(), f'Missing flag: {label}')
    require(series.isin([True,False]).all() and pd.api.types.is_bool_dtype(series), f'Expected True/False values: {label}')
    return series


def source_records(frame: pd.DataFrame) -> None:
    numeric(frame,['source_record'])
    require(frame['source_record'].gt(0).all() and frame['source_record'].mod(1).eq(0).all(), 'source_record must be a positive integer.')
    require(not frame['source_record'].duplicated().any(), 'source_record is duplicated in a prepared sample.')
    require(frame[['county','vehicle_type']].notna().all().all(), 'Missing county or vehicle type.')
    require(frame['vehicle_type'].isin(['BEV','PHEV']).all(), 'Unexpected vehicle type in prepared sample.')


def p_report(p: float) -> dict:
    require(np.isfinite(p) and 0 <= p <= 1, 'A finite p-value between zero and one is required.')
    if p == 0:
        # A numerical zero is not a claim that the mathematical p-value equals zero.
        return {'p_value':None, 'p_display':'<1e-300 (numerical underflow)',
                'p_numerical_underflow':True, 'p_value_upper_bound':1e-300,
                'nominal_alpha':ALPHA, 'reject_h0':True}
    return {'p_value':float(p), 'p_display':f'{p:.8g}', 'p_numerical_underflow':False,
            'p_value_upper_bound':None, 'nominal_alpha':ALPHA, 'reject_h0':bool(p<ALPHA)}


def chi_square(table: pd.DataFrame, hypothesis: str, sample: str,
               force_monte_carlo: bool = False, n_resamples: int = N_RESAMPLES,
               seed: int = SEED, batch: int = BATCH) -> tuple[dict,pd.DataFrame]:
    observed = table.to_numpy(dtype=float)
    require(observed.ndim==2 and min(observed.shape)>=2, 'A contingency table needs at least two rows and columns.')
    require(np.isfinite(observed).all() and (observed>=0).all() and np.equal(observed,np.floor(observed)).all(), 'Observed counts must be finite nonnegative integers.')
    require((observed.sum(axis=0)>0).all() and (observed.sum(axis=1)>0).all(), 'Contingency margins must be positive.')
    asymptotic = stats.chi2_contingency(observed,correction=False)
    expected = np.asarray(asymptotic.expected_freq)
    use_mc = force_monte_carlo or bool((expected<5).any())
    if use_mc:
        require(n_resamples>=9999 and batch>0, 'Monte Carlo needs at least 9999 draws and a positive batch.')
        method = stats.MonteCarloMethod(n_resamples=n_resamples,batch=batch,rng=np.random.default_rng(seed))
        result = stats.chi2_contingency(observed.astype(np.int64),correction=False,method=method)
        p = float(result.pvalue)
        resolution = 1/(n_resamples+1)
    else:
        result, p, resolution = asymptotic, float(asymptotic.pvalue), None
    total = int(observed.sum())
    df = (observed.shape[0]-1)*(observed.shape[1]-1)
    row = {
        'hypothesis':hypothesis,'sample':sample,'status':'computed',
        'statistic_name':'Pearson chi-square','statistic':float(result.statistic),
        'n':total,'table_rows':observed.shape[0],'table_columns':observed.shape[1],
        'df_theoretical':df,'p_method':'Monte Carlo, fixed margins' if use_mc else 'asymptotic chi-square',
        **p_report(p), 'effect_name':'Cramers V',
        'effect_size':math.sqrt(float(result.statistic)/(total*min(observed.shape[0]-1,observed.shape[1]-1))),
        'effect_definition':'sqrt(chi_square / (N * min(rows-1, columns-1))); N is the sum of observed counts.',
        'expected_min':float(expected.min()), 'expected_cells_lt_5':int((expected<5).sum()),
        'expected_cells_lt_1':int((expected<1).sum()), 'expected_cell_count':int(expected.size),
        'observed_zero_cells':int((observed==0).sum()), 'yates_correction':False,
        'mc_resamples':n_resamples if use_mc else None, 'mc_batch':batch if use_mc else None,
        'mc_seed':seed if use_mc else None,'mc_resolution':resolution,
        'mc_at_resolution_limit':bool(use_mc and math.isclose(p,resolution,rel_tol=0,abs_tol=1e-15)),
    }
    if row['mc_at_resolution_limit']:
        row['p_display']=f'{p:.8g} (Monte Carlo resolution limit)'
    cells=[]
    for i,label in enumerate(table.index):
        for j,column in enumerate(table.columns):
            cells.append({'hypothesis':hypothesis,'sample':sample,'row_label':str(label),'column_label':str(column),
                          'observed':int(observed[i,j]),'expected':float(expected[i,j]),
                          'expected_lt_5':bool(expected[i,j]<5),'row_total':int(observed[i].sum()),
                          'column_total':int(observed[:,j].sum()),'n':total})
    return row,pd.DataFrame(cells)


def check_outputs(paths: list[Path],inputs: list[Path]) -> None:
    resolved=[p.resolve() for p in paths]
    require(len(set(resolved))==len(resolved),'Output paths must be distinct.')
    input_paths={p.resolve() for p in inputs}
    for path in paths:
        require(path.resolve() not in input_paths and not path.exists(),f'Choose a new output path: {path}')
