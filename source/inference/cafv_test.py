"""Test vehicle type versus CAFV status with known-label and Unknown-inclusive samples."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.inference.contingency import boolean_flag, check_outputs, chi_square, read_sample, require, source_records

ELIGIBLE='Clean Alternative Fuel Vehicle Eligible'
INELIGIBLE='Not eligible due to low battery range'
UNKNOWN='Eligibility unknown as battery range has not been researched'
LABELS=[ELIGIBLE,INELIGIBLE,UNKNOWN]
COLUMNS=['source_record','county','vehicle_type','cafv_status','cafv_known']


def load_cafv(path: Path) -> pd.DataFrame:
    frame=read_sample(path,COLUMNS)
    source_records(frame)
    require(frame['cafv_status'].notna().all() and frame['cafv_status'].isin(LABELS).all(),'Unexpected CAFV status in prepared sample.')
    require(boolean_flag(frame['cafv_known'],'cafv_known').eq(frame['cafv_status'].ne(UNKNOWN)).all(),'CAFV known flag differs from status label.')
    return frame


def run_tests(frame: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows,cells=[],[]
    for sample,part,labels in [('known_labels',frame.loc[frame['cafv_known']],LABELS[:2]),('including_unknown',frame,LABELS)]:
        table=pd.crosstab(part['vehicle_type'],part['cafv_status']).reindex(index=['BEV','PHEV'],columns=labels,fill_value=0)
        row,observed=chi_square(table,'H3',sample)
        row['n_bev']=int(table.loc['BEV'].sum())
        row['n_phev']=int(table.loc['PHEV'].sum())
        row['unknown_excluded']=sample=='known_labels'
        rows.append(row)
        cells.append(observed)
    return pd.DataFrame(rows),pd.concat(cells,ignore_index=True)


def export_figure(frame: pd.DataFrame,directory: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    table=pd.crosstab(frame['vehicle_type'],frame['cafv_status']).reindex(index=['BEV','PHEV'],columns=LABELS,fill_value=0)
    shares=table.div(table.sum(axis=1),axis=0)*100
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(11,5.0))
    fig.subplots_adjust(left=.13,right=.96,bottom=.31,top=.82)
    left=pd.Series(0.,index=shares.index)
    for label,caption,color in zip(LABELS,['Đủ điều kiện CAFV','Không đủ điều kiện CAFV','Chưa xác định'],['#167D9A','#D69332','#A8ADB4']):
        rectangles=ax.barh(shares.index,shares[label],left=left,label=caption,color=color,height=.52)
        for rectangle,value,start in zip(rectangles,shares[label],left):
            if value>=5:
                ax.text(start+value/2,rectangle.get_y()+rectangle.get_height()/2,f'{value:.1f}%'.replace('.',','),ha='center',va='center',fontsize=10)
        left+=shares[label]
    ax.invert_yaxis()
    ax.set(xlim=(0,100),xlabel='Tỷ trọng nhãn CAFV trong từng loại xe (%)',title='Trạng thái CAFV theo loại xe — bao gồm nhãn chưa xác định')
    ax.legend(loc='upper left',bbox_to_anchor=(0,-.28),frameon=False,ncol=3,fontsize=9)
    counts='; '.join(f"{kind}: {int(table.loc[kind].sum()):,}".replace(',','.') for kind in table.index)
    fig.text(.06,.025,'Nguồn: mẫu CAFV từ Population clean. '+counts+' bản ghi.\nMẫu số tỷ lệ là số xe của từng loại. H3 chính loại Unknown; độ nhạy giữ toàn bộ nhãn.\nCAFV là nhãn hành chính, không phải bằng chứng về tác động chính sách.',fontsize=8.7,color='#4C5661')
    directory.mkdir(parents=True,exist_ok=True)
    fig.savefig(directory/'cafv_by_vehicle_type.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cafv-sample',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    args=parser.parse_args()
    check_outputs([args.results_dir/'cafv_tests.csv',args.results_dir/'cafv_contingency.csv',args.figures_dir/'cafv_by_vehicle_type.png'],[args.cafv_sample])
    frame=load_cafv(args.cafv_sample)
    tests,cells=run_tests(frame)
    export_figure(frame,args.figures_dir)
    args.results_dir.mkdir(parents=True,exist_ok=True)
    for name,table in [('cafv_tests.csv',tests),('cafv_contingency.csv',cells)]:
        table.to_csv(args.results_dir/name,index=False,encoding='utf-8-sig',lineterminator='\n')
    print(json.dumps({'test_rows':len(tests),'contingency_cells':len(cells)},indent=2))


if __name__=='__main__':
    main()
