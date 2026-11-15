"""Describe monthly EV stocks, composition and net growth; do not fit forecasting models."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import pandas as pd

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.preparation.build_monthly_series import build_monthly_series, load_history
from source.descriptive.vehicle_characteristics import integer_label, percent_label
from source.descriptive.spatial_distribution import validate_destinations, write_tables

TABLE_NAMES = ['monthly_growth.csv','overall_growth_summary.csv','annual_growth.csv','growth_period_summary.csv','notable_months.csv']
FIGURE_NAMES = ['monthly_ev_population.png','monthly_ev_composition.png','monthly_ev_growth.png','statewide_ev_rate.png']


def build_tables(history: pd.DataFrame) -> dict[str,pd.DataFrame]:
    monthly,_ = build_monthly_series(history)
    monthly['bev_share_pct'] = 100*monthly['bev']/monthly['ev_total']
    monthly['phev_share_pct'] = 100*monthly['phev']/monthly['ev_total']
    for variable in ['bev','phev','ev_total']:
        prefix = 'ev' if variable == 'ev_total' else variable
        monthly[prefix+'_net_change'] = monthly[variable].diff()
        monthly[prefix+'_mom_growth_pct'] = 100*monthly[variable].pct_change(fill_method=None)
        monthly[prefix+'_yoy_net_change'] = monthly[variable].diff(12)
        monthly[prefix+'_yoy_growth_pct'] = 100*monthly[variable].pct_change(12,fill_method=None)
    monthly['ev_log_growth_pct'] = monthly['ev_total'].map(math.log).diff()*100
    monthly['ev_ma12'] = monthly['ev_total'].rolling(12,min_periods=12).mean()
    monthly['net_change_sd12'] = monthly['ev_net_change'].rolling(12,min_periods=12).std(ddof=1)
    intervals = len(monthly)-1
    growth = []
    for variable in ['bev','phev','ev_total']:
        first,last = int(monthly[variable].iloc[0]),int(monthly[variable].iloc[-1])
        growth.append({'series':variable,'start_date':monthly['date'].iloc[0],'end_date':monthly['date'].iloc[-1],
                       'monthly_intervals':intervals,'start_vehicles':first,'end_vehicles':last,
                       'net_change_vehicles':last-first,'growth_pct':100*(last/first-1),
                       'annualized_growth_pct':100*((last/first)**(12/intervals)-1)})
    dates = pd.to_datetime(monthly['date'])
    annual = monthly.loc[dates.dt.month.eq(12) | monthly.index.to_series().eq(monthly.index[-1])].copy()
    annual = annual[['date','bev','phev','ev_total','bev_yoy_net_change','bev_yoy_growth_pct',
                     'phev_yoy_net_change','phev_yoy_growth_pct','ev_yoy_net_change','ev_yoy_growth_pct']]
    annual['is_year_end'] = pd.to_datetime(annual['date']).dt.month.eq(12)
    changes = monthly.loc[monthly['ev_net_change'].notna()]
    half = len(changes)//2
    periods = []
    for label,frame in [('all_changes',changes),('first_half',changes.iloc[:half]),('second_half',changes.iloc[half:]),
                        ('train_changes',changes.loc[changes['split'].eq('train')]),('test_changes',changes.loc[changes['split'].eq('test')])]:
        periods.append({'period':label,'first_change_month':frame['date'].iloc[0],'last_change_month':frame['date'].iloc[-1],
                        'change_intervals':len(frame),'mean_net_change_vehicles':float(frame['ev_net_change'].mean()),
                        'std_net_change_vehicles':float(frame['ev_net_change'].std(ddof=1)),
                        'min_net_change_vehicles':float(frame['ev_net_change'].min()),
                        'max_net_change_vehicles':float(frame['ev_net_change'].max()),
                        'mean_log_growth_pct':float(frame['ev_log_growth_pct'].mean()),
                        'std_log_growth_pct':float(frame['ev_log_growth_pct'].std(ddof=1))})
    largest = set(changes.nlargest(3,'ev_net_change').index)
    smallest = set(changes.nsmallest(3,'ev_net_change').index)
    notable = monthly.loc[sorted(largest|smallest),['date','ev_total','ev_net_change','ev_mom_growth_pct','ev_yoy_growth_pct']].copy()
    notable['selection'] = ['largest_net_change' if index in largest else 'smallest_net_change' for index in notable.index]
    return dict(zip(TABLE_NAMES,[monthly,pd.DataFrame(growth),annual.reset_index(drop=True),pd.DataFrame(periods),notable.reset_index(drop=True)]))


def export_figures(tables: dict[str,pd.DataFrame],directory: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    directory.mkdir(parents=True,exist_ok=True)
    monthly = tables[TABLE_NAMES[0]]
    dates = pd.to_datetime(monthly['date'])
    period = f"{dates.iloc[0]:%m/%Y}–{dates.iloc[-1]:%m/%Y}"
    note = f'Nguồn: History clean, toàn bang WA, {period}; cộng 39 quận và hai nhóm Passenger/Truck.'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.titleweight':'bold'})

    def style_axis(ax):
        ax.grid(axis='y',alpha=.18)
        ax.set_axisbelow(True)
        ax.set_xticks(dates.loc[dates.dt.month.eq(1)])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.set_xlim(dates.iloc[0],dates.iloc[-1])

    def save(fig,name,extra):
        fig.text(.065,.025,note+'\n'+extra,fontsize=8.8,color='#4C5661')
        fig.savefig(directory/name,dpi=220,bbox_inches='tight',pad_inches=.2)
        plt.close(fig)

    fig,ax = plt.subplots(figsize=(11,5.8))
    fig.subplots_adjust(left=.12,right=.97,bottom=.24,top=.86)
    for variable,label,color in [('ev_total','EV Total','#343E49'),('bev','BEV','#167D9A'),('phev','PHEV','#D69332')]:
        ax.plot(dates,monthly[variable],label=label,color=color,linewidth=2)
    ax.set(title=f'Quy mô EV, BEV và PHEV theo tháng — {period}',ylabel='Số phương tiện cuối tháng',xlabel='Năm')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:integer_label(x)))
    ax.legend(loc='upper left',frameon=False)
    style_axis(ax)
    save(fig,FIGURE_NAMES[0],'Đây là số xe hiện có, không phải số xe bán mới trong tháng.')

    fig,ax = plt.subplots(figsize=(11,5.5))
    fig.subplots_adjust(left=.10,right=.97,bottom=.23,top=.86)
    ax.stackplot(dates,monthly['bev_share_pct'],monthly['phev_share_pct'],labels=['BEV','PHEV'],colors=['#167D9A','#D69332'],alpha=.86)
    ax.set(title=f'Cơ cấu BEV/PHEV trong tổng EV — {period}',ylabel='Tỷ trọng trong EV (%)',xlabel='Năm',ylim=(0,100))
    ax.legend(loc='upper left',frameon=True,ncol=2)
    style_axis(ax)
    save(fig,FIGURE_NAMES[1],'Mẫu số mỗi tháng là EV Total của chính tháng đó; hai tỷ trọng cộng bằng 100%.')

    fig,axes = plt.subplots(2,1,figsize=(11,7.7),sharex=True)
    fig.subplots_adjust(left=.12,right=.97,bottom=.19,top=.87,hspace=.25)
    values = monthly['ev_net_change']
    axes[0].bar(dates,values,width=22,color=['#B44C4C' if pd.notna(v) and v<0 else '#167D9A' for v in values])
    axes[0].set_ylabel('Thay đổi ròng (xe)')
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x,_:integer_label(x)))
    axes[1].plot(dates,monthly['ev_mom_growth_pct'],color='#167D9A',linewidth=1.8,label='So tháng trước (MoM)')
    axes[1].plot(dates,monthly['ev_yoy_growth_pct'],color='#D69332',linewidth=1.8,label='So cùng tháng năm trước (YoY)')
    axes[1].set(ylabel='Tăng trưởng (%)',xlabel='Năm')
    axes[1].legend(loc='upper left',bbox_to_anchor=(0,1.15),frameon=False,ncol=2,fontsize=9)
    for ax in axes:
        ax.axhline(0,color='#60666D',linewidth=.7)
        style_axis(ax)
    fig.suptitle(f'Thay đổi ròng và tăng trưởng EV — {period}',fontweight='bold')
    save(fig,FIGURE_NAMES[2],'MoM thiếu ở tháng đầu; YoY thiếu 12 tháng đầu do không có kỳ gốc. Không điền các kỳ này bằng 0.')

    fig,ax = plt.subplots(figsize=(11,5.6))
    fig.subplots_adjust(left=.10,right=.97,bottom=.24,top=.86)
    ax.plot(dates,monthly['ev_pct'],color='#167D9A',linewidth=2)
    ax.set(title=f'Tỷ lệ EV trong tổng phương tiện toàn bang — {period}',ylabel='EV / tổng phương tiện (%)',xlabel='Năm')
    style_axis(ax)
    ax.set_ylim(bottom=0)
    save(fig,FIGURE_NAMES[3],'Tỷ lệ = 100 × tổng EV / tổng phương tiện; không lấy trung bình tỷ lệ quận hoặc nhóm sử dụng.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-clean',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    args = parser.parse_args()
    validate_destinations([*(args.results_dir/n for n in TABLE_NAMES),*(args.figures_dir/n for n in FIGURE_NAMES)],[args.history_clean])
    tables = build_tables(load_history(args.history_clean))
    export_figures(tables,args.figures_dir)
    write_tables(tables,args.results_dir)
    print(json.dumps({'months':len(tables[TABLE_NAMES[0]]),'tables':TABLE_NAMES,'figures':FIGURE_NAMES},indent=2))


if __name__ == '__main__':
    main()
