"""Mann-Whitney U and Spearman analyses of prepared valid Range samples."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import stats

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.inference.contingency import ALPHA, boolean_flag, check_outputs, numeric, p_report, read_sample, require, source_records

COLUMNS=['source_record','county','vehicle_type','model_year','electric_range','h1_year_le_2020','h2_valid']


def load_range(path: Path) -> pd.DataFrame:
    frame=read_sample(path,COLUMNS)
    source_records(frame)
    numeric(frame,['electric_range'])
    numeric(frame,['model_year'],allow_missing=True)
    require(frame['electric_range'].gt(0).all(),'Prepared Range values must be positive.')
    years=frame['model_year'].dropna()
    require(years.gt(0).all() and years.mod(1).eq(0).all(),'Model Year must be a positive integer or missing.')
    require(boolean_flag(frame['h2_valid'],'h2_valid').eq(frame['model_year'].notna()).all(),'h2_valid differs from Model Year availability.')
    expected=frame['model_year'].notna() & frame['model_year'].le(2020)
    require(boolean_flag(frame['h1_year_le_2020'],'h1_year_le_2020').eq(expected).all(),'H1 sensitivity flag differs from Model Year <= 2020.')
    return frame


def run_tests(frame: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for sample,part in [('primary',frame),('year_le_2020',frame.loc[frame['h1_year_le_2020']])]:
        bev=part.loc[part['vehicle_type'].eq('BEV'),'electric_range'].to_numpy()
        phev=part.loc[part['vehicle_type'].eq('PHEV'),'electric_range'].to_numpy()
        require(len(bev)>0 and len(phev)>0,'H1 requires nonempty BEV and PHEV samples.')
        result=stats.mannwhitneyu(bev,phev,alternative='two-sided',method='asymptotic',use_continuity=True,nan_policy='raise')
        superiority=float(result.statistic)/(len(bev)*len(phev))
        row={'hypothesis':'H1','sample':sample,'status':'computed','statistic_name':'Mann-Whitney U (BEV)',
             'statistic':float(result.statistic),'n':len(part),'n_bev':len(bev),'n_phev':len(phev),
             'p_method':'asymptotic normal, ties and continuity corrected','alternative':'two-sided',
             **p_report(float(result.pvalue)),'effect_name':'rank-biserial (BEV minus PHEV)',
             'effect_size':2*superiority-1,'probability_superiority_bev':superiority,
             'effect_definition':'A=P(BEV>PHEV)+0.5*P(tie)=U_BEV/(n_BEV*n_PHEV); rank_biserial=2*A-1.'}
        for name,values in [('bev',bev),('phev',phev)]:
            q1,q3=np.quantile(values,[.25,.75],method='linear')
            row[name+'_median_miles']=float(np.median(values))
            row[name+'_q1_miles']=float(q1)
            row[name+'_q3_miles']=float(q3)
            row[name+'_iqr_miles']=float(q3-q1)
        rows.append(row)
    paired=frame.loc[frame['h2_valid']]
    for sample,part in [('all_valid',paired),('bev',paired.loc[paired['vehicle_type'].eq('BEV')]),('phev',paired.loc[paired['vehicle_type'].eq('PHEV')])]:
        row={'hypothesis':'H2','sample':sample,'n':len(part),'statistic_name':'Spearman rho',
             'p_method':'asymptotic t approximation','alternative':'two-sided','effect_name':'Spearman rho',
             'effect_definition':'Correlation of average ranks of Model Year and Electric Range; no causal interpretation.'}
        if len(part)<3 or part['model_year'].nunique()<2 or part['electric_range'].nunique()<2:
            row.update({'status':'undefined_constant_or_small_sample','statistic':None,'effect_size':None,
                        'p_value':None,'p_display':'not computed','p_numerical_underflow':False,
                        'p_value_upper_bound':None,'nominal_alpha':ALPHA,'reject_h0':None})
        else:
            result=stats.spearmanr(part['model_year'],part['electric_range'],alternative='two-sided',nan_policy='raise')
            row.update({'status':'computed','statistic':float(result.statistic),'effect_size':float(result.statistic),
                        **p_report(float(result.pvalue))})
        rows.append(row)
    year_summary=paired.groupby(['vehicle_type','model_year'])['electric_range'].agg(
        valid_n='size',median_miles='median',q1_miles=lambda s:s.quantile(.25,interpolation='linear'),
        q3_miles=lambda s:s.quantile(.75,interpolation='linear')).reset_index()
    return pd.DataFrame(rows),year_summary


def export_figure(year_summary: pd.DataFrame,directory: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(12,5.3),sharey=True)
    fig.subplots_adjust(left=.08,right=.97,bottom=.27,top=.80,wspace=.13)
    for ax,kind,color in zip(axes,['BEV','PHEV'],['#167D9A','#D69332']):
        part=year_summary.loc[year_summary['vehicle_type'].eq(kind)]
        ax.plot(part['model_year'],part['median_miles'],color=color,marker='o',markersize=3,label='Trung vị')
        ax.fill_between(part['model_year'],part['q1_miles'],part['q3_miles'],color=color,alpha=.2,label='Q1–Q3')
        ax.set(title=f"{kind}: {int(part['valid_n'].sum()):,} cặp hợp lệ".replace(',','.'),xlabel='Năm mẫu xe')
        ax.grid(axis='y',alpha=.17)
        if len(part):
            first,last=int(part['model_year'].min()),int(part['model_year'].max())
            ax.set_xticks(sorted({first,last,*range(first,last+1,max(1,(last-first+5)//6))}))
        ax.legend(frameon=False,loc='upper left')
    axes[0].set_ylabel('Electric Range (mile)')
    fig.suptitle('Electric Range và Model Year trong mẫu hợp lệ',fontweight='bold')
    fig.text(.06,.035,'Nguồn: mẫu Range từ Population clean. Chỉ dùng cặp Range/Model Year hợp lệ.\nDải Q1–Q3 là độ phân tán, không phải khoảng tin cậy. Cỡ mẫu từng năm nằm trong bảng CSV.\nMẫu thiếu Range không đồng đều theo loại xe/năm; đồ thị không chứng minh quan hệ nhân quả.',fontsize=8.7,color='#4C5661')
    directory.mkdir(parents=True,exist_ok=True)
    fig.savefig(directory/'range_by_model_year.png',dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--range-sample',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    args=parser.parse_args()
    check_outputs([args.results_dir/'range_tests.csv',args.results_dir/'range_year_summary.csv',args.figures_dir/'range_by_model_year.png'],[args.range_sample])
    tests,years=run_tests(load_range(args.range_sample))
    export_figure(years,args.figures_dir)
    args.results_dir.mkdir(parents=True,exist_ok=True)
    for name,table in [('range_tests.csv',tests),('range_year_summary.csv',years)]:
        table.to_csv(args.results_dir/name,index=False,encoding='utf-8-sig',lineterminator='\n')
    print(json.dumps({'test_rows':len(tests),'year_rows':len(years)},indent=2))


if __name__=='__main__':
    main()
