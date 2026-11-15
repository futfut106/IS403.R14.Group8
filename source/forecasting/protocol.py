"""Read the prepared monthly series and enforce the declared time boundary."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def require(condition: bool,message: str) -> None:
    if not bool(condition):
        raise ValueError(message)


def load_protocol() -> dict:
    return json.loads((Path(__file__).resolve().parent/'configs/protocol.json').read_text(encoding='utf-8'))


def load_series(path: Path) -> pd.DataFrame:
    config=load_protocol()
    frame=pd.read_csv(path,encoding='utf-8-sig')
    require(list(frame.columns)==config['columns'],'Monthly series must use the eight-column preparation schema.')
    require(frame.notna().all().all(),'Monthly series contains missing cells.')
    frame['date']=pd.to_datetime(frame['date'],format='%Y-%m-%d',errors='raise')
    expected=pd.period_range(config['first_month'][:7],config['last_month'][:7],freq='M').to_timestamp('M')
    require(pd.DatetimeIndex(frame['date']).equals(expected),'Monthly dates must be ordered, unique and cover all 83 month ends.')
    columns=['bev','phev','ev_total','non_ev','total_vehicles','ev_pct']
    for column in columns:
        frame[column]=pd.to_numeric(frame[column],errors='raise')
        require(np.isfinite(frame[column]).all(),f'Nonfinite monthly value: {column}')
    counts=frame[columns[:5]]
    require(counts.ge(0).all().all() and counts.mod(1).eq(0).all().all(),'Monthly counts must be nonnegative integers.')
    require(frame['ev_total'].gt(0).all() and frame['total_vehicles'].gt(0).all(),'Monthly EV and total vehicle levels must be positive.')
    require(frame['bev'].add(frame['phev']).eq(frame['ev_total']).all(),'BEV + PHEV differs from EV.')
    require(frame['ev_total'].add(frame['non_ev']).eq(frame['total_vehicles']).all(),'EV + non-EV differs from total.')
    require(frame['ev_pct'].sub(100*frame['ev_total']/frame['total_vehicles']).abs().le(1e-9).all(),'Monthly percentage differs from its counts.')
    train=frame['date'].le(pd.Timestamp(config['train_end']))
    require(frame['split'].eq(train.map({True:'train',False:'test'})).all(),'Split labels disagree with date boundaries.')
    require(int(train.sum())==71 and int((~train).sum())==config['horizon'],'Expected 71 train and 12 test months.')
    require(frame.loc[~train,'date'].min()==pd.Timestamp(config['test_start']),'Incorrect first test date.')
    return frame


def check_outputs(paths: list[Path],inputs: list[Path]) -> None:
    require(len({p.resolve() for p in paths})==len(paths),'Output paths must be distinct.')
    originals={p.resolve() for p in inputs}
    for path in paths:
        require(path.resolve() not in originals and not path.exists(),f'Choose a new output path: {path}')
