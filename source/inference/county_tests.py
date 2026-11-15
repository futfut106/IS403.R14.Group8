"""Test county BEV/PHEV composition and same-month EV/non-EV rates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.inference.contingency import BATCH, N_RESAMPLES, SEED, boolean_flag, check_outputs, chi_square, numeric, read_sample, require

COUNTY_COLUMNS=['county','bev','phev','ev_total','included_h4a_sensitivity']
SNAPSHOT_COLUMNS=['date','county','bev','phev','ev_total','non_ev','total_vehicles','ev_pct']
DATES=['2017-01-31','2023-11-30']


def load_counties(path: Path) -> pd.DataFrame:
    frame=read_sample(path,COUNTY_COLUMNS)
    require(len(frame)==39 and frame['county'].notna().all() and not frame['county'].duplicated().any(),'Expected one row for each of 39 counties.')
    numeric(frame,['bev','phev','ev_total'])
    counts=frame[['bev','phev','ev_total']]
    require(counts.ge(0).all().all() and counts.mod(1).eq(0).all().all(),'County counts must be nonnegative integers.')
    require(frame['bev'].add(frame['phev']).eq(frame['ev_total']).all() and frame['ev_total'].gt(0).all(),'County EV count identity failed.')
    require(boolean_flag(frame['included_h4a_sensitivity'],'included_h4a_sensitivity').eq(frame['ev_total'].ge(30)).all(),'County sensitivity flag differs from EV >= 30.')
    return frame


def load_snapshots(path: Path) -> pd.DataFrame:
    frame=read_sample(path,SNAPSHOT_COLUMNS)
    require(frame[['date','county']].notna().all().all() and not frame.duplicated(['date','county']).any(),'Snapshot keys must be present and unique.')
    require(frame.groupby('date').size().to_dict()=={date:39 for date in DATES},'Expected 39 county rows at each of 01/2017 and 11/2023.')
    numeric(frame,['bev','phev','ev_total','non_ev','total_vehicles','ev_pct'])
    counts=frame[['bev','phev','ev_total','non_ev','total_vehicles']]
    require(counts.ge(0).all().all() and counts.mod(1).eq(0).all().all(),'Snapshot counts must be nonnegative integers.')
    require(frame['bev'].add(frame['phev']).eq(frame['ev_total']).all(),'Snapshot BEV + PHEV differs from EV.')
    require(frame['ev_total'].add(frame['non_ev']).eq(frame['total_vehicles']).all() and frame['total_vehicles'].gt(0).all(),'Snapshot EV + non-EV differs from total.')
    require(frame['ev_pct'].sub(100*frame['ev_total']/frame['total_vehicles']).abs().le(1e-9).all(),'Snapshot EV percentage differs from counts.')
    return frame


def run_tests(counties: pd.DataFrame,snapshots: pd.DataFrame,
              n_resamples: int=N_RESAMPLES,seed: int=SEED,batch: int=BATCH) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows,cells=[],[]
    for date in DATES:
        require(set(snapshots.loc[snapshots['date'].eq(date),'county'])==set(counties['county']),'Snapshot county coverage differs from Population counties.')
    for sample,part,force in [('all_counties',counties,True),('county_ev_ge_30',counties.loc[counties['included_h4a_sensitivity']],False)]:
        table=part.sort_values('county').set_index('county')[['bev','phev']]
        row,observed=chi_square(table,'H4a',sample,force,n_resamples,seed,batch)
        row['counties']=len(part)
        row['excluded_counties']='; '.join(sorted(set(counties['county'])-set(part['county'])))
        rows.append(row)
        cells.append(observed)
    for date,sample in [('2023-11-30','latest_month'),('2017-01-31','first_month')]:
        part=snapshots.loc[snapshots['date'].eq(date)].sort_values('county')
        table=part.set_index('county')[['ev_total','non_ev']]
        row,observed=chi_square(table,'H4b',sample,False,n_resamples,seed,batch)
        row['date']=date
        row['counties']=len(part)
        row['excluded_counties']=''
        rows.append(row)
        observed['date']=date
        cells.append(observed)
    return pd.DataFrame(rows),pd.concat(cells,ignore_index=True)


def export_figure(counties: pd.DataFrame,directory: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data=counties.copy()
    data['bev_share']=100*data['bev']/data['ev_total']
    data=data.sort_values(['bev_share','county'],ascending=[False,True])
    labels=[f"{r.county}{'*' if not r.included_h4a_sensitivity else ''} (n={r.ev_total:,.0f})".replace(',','.') for r in data.itertuples()]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(9,12.8))
    fig.subplots_adjust(left=.32,right=.97,bottom=.12,top=.94)
    ax.barh(labels,data['bev_share'],color='#167D9A',height=.72,label='BEV')
    ax.barh(labels,100-data['bev_share'],left=data['bev_share'],color='#D69332',height=.72,label='PHEV')
    ax.invert_yaxis()
    ax.set(xlim=(0,100),xlabel='Tỷ trọng trong EV của từng quận (%)',title='Cơ cấu BEV/PHEV theo quận trong Population')
    ax.legend(frameon=False,loc='upper left',bbox_to_anchor=(0,-.035),ncol=2)
    fig.text(.055,.025,'Nguồn: bảng County–type từ Population clean; n trong nhãn là số EV của quận.\n* Quận có dưới 30 EV: chỉ loại trong mẫu độ nhạy, vẫn giữ ở mẫu chính.\nĐây là cơ cấu trong EV, không phải tỷ lệ EV trên tổng phương tiện.',fontsize=8.5,color='#4C5661')
    directory.mkdir(parents=True,exist_ok=True)
    fig.savefig(directory/'county_vehicle_type_share.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--county-counts',type=Path,required=True)
    parser.add_argument('--county-snapshots',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    args=parser.parse_args()
    check_outputs([args.results_dir/'county_tests.csv',args.results_dir/'county_contingency.csv',args.figures_dir/'county_vehicle_type_share.png'],[args.county_counts,args.county_snapshots])
    counties,snapshots=load_counties(args.county_counts),load_snapshots(args.county_snapshots)
    tests,cells=run_tests(counties,snapshots)
    export_figure(counties,args.figures_dir)
    args.results_dir.mkdir(parents=True,exist_ok=True)
    for name,table in [('county_tests.csv',tests),('county_contingency.csv',cells)]:
        table.to_csv(args.results_dir/name,index=False,encoding='utf-8-sig',lineterminator='\n')
    print(json.dumps({'test_rows':len(tests),'contingency_cells':len(cells)},indent=2))


if __name__=='__main__':
    main()
