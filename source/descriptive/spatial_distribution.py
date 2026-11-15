"""Describe geographic concentration and same-month EV rates without joining vehicle snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from source.descriptive.vehicle_characteristics import load_population, integer_label, percent_label
from source.preparation.build_monthly_series import COUNT_MAP, LAST_MONTH, load_history, require

TABLE_NAMES = ['county_summary.csv', 'city_summary.csv', 'county_ev_rates.csv', 'usage_type_summary.csv']
FIGURE_NAMES = ['population_by_county.png', 'population_by_city.png', 'county_ev_rates.png', 'usage_type_comparison.png']
SUMMARY_NAME = 'spatial_summary.json'


def build_tables(population: pd.DataFrame, history: pd.DataFrame, snapshot_date: str = LAST_MONTH) -> tuple[dict[str, pd.DataFrame], dict]:
    require(population['County'].notna().all(), 'County must be present for geographic summaries.')
    require(population['Electric Vehicle Type'].notna().all(), 'Vehicle type must be present for county BEV/PHEV counts.')
    require(set(population['County']) == set(history['County']), 'Population and History county coverage differs.')
    date = pd.Timestamp(snapshot_date)
    require(date in set(history['Date']), 'Snapshot date must be an available History month end.')
    total = len(population)
    county = pd.crosstab(population['County'], population['Electric Vehicle Type']).rename(columns={
        'Battery Electric Vehicle (BEV)': 'bev', 'Plug-in Hybrid Electric Vehicle (PHEV)': 'phev'})
    county = county.reindex(columns=['bev', 'phev'], fill_value=0).rename_axis(columns=None).reset_index().rename(columns={'County': 'county'})
    county['ev_count'] = county['bev'] + county['phev']
    county['share_pct'] = 100 * county['ev_count'] / total
    county['bev_share_pct'] = 100 * county['bev'] / county['ev_count']
    county['phev_share_pct'] = 100 * county['phev'] / county['ev_count']
    county = county.sort_values(['ev_count', 'county'], ascending=[False, True], kind='stable').reset_index(drop=True)
    county['rank'] = county.index + 1
    county['cumulative_share_pct'] = county['share_pct'].cumsum()
    county['population_n'] = total
    city = population.groupby(['County', 'City'], dropna=False).size().rename('ev_count').reset_index()
    city = city.rename(columns={'County': 'county', 'City': 'city'})
    city['is_missing_city'] = city['city'].isna()
    city['share_pct'] = 100 * city['ev_count'] / total
    city['population_n'] = total
    city = city.sort_values(['ev_count', 'county', 'city'], ascending=[False, True, True], na_position='last', kind='stable').reset_index(drop=True)
    city['rank'] = city.index + 1
    cut = history.loc[history['Date'].eq(date)]
    rates = cut.groupby('County')[list(COUNT_MAP)].sum().rename(columns=COUNT_MAP).reset_index().rename(columns={'County': 'county'})
    rates['date'] = date.strftime('%Y-%m-%d')
    rates['ev_pct'] = 100 * rates['ev_total'] / rates['total_vehicles']
    rates['ev_share_statewide_pct'] = 100 * rates['ev_total'] / rates['ev_total'].sum()
    rates['rank_ev_count'] = rates['ev_total'].rank(method='min', ascending=False).astype(int)
    rates['rank_ev_pct'] = rates['ev_pct'].rank(method='min', ascending=False).astype(int)
    rates = rates[['date', 'county', *COUNT_MAP.values(), 'ev_pct', 'ev_share_statewide_pct', 'rank_ev_count', 'rank_ev_pct']]
    rates = rates.sort_values(['ev_pct', 'county'], ascending=[False, True], kind='stable').reset_index(drop=True)
    usage = cut.groupby('Vehicle Primary Use')[list(COUNT_MAP)].sum().rename(columns=COUNT_MAP).reset_index().rename(columns={'Vehicle Primary Use': 'vehicle_primary_use'})
    usage.insert(0, 'date', date.strftime('%Y-%m-%d'))
    usage['ev_pct'] = 100 * usage['ev_total'] / usage['total_vehicles']
    usage['bev_share_ev_pct'] = 100 * usage['bev'] / usage['ev_total'].replace(0, float('nan'))
    usage['ev_share_statewide_pct'] = 100 * usage['ev_total'] / usage['ev_total'].sum()
    usage['vehicle_share_statewide_pct'] = 100 * usage['total_vehicles'] / usage['total_vehicles'].sum()
    require(int(county['ev_count'].sum()) == total and int(city['ev_count'].sum()) == total, 'Geographic counts do not preserve Population rows.')
    summary = {
        'population': {
            'rows': total, 'counties': len(county), 'distinct_city_names': int(population['City'].nunique()),
            'county_city_pairs': len(city), 'missing_city_rows': int(population['City'].isna().sum()),
            'city_names_in_multiple_counties': int(population.dropna(subset=['City']).groupby('City')['County'].nunique().gt(1).sum()),
            'county_top_3_share_pct': float(county.head(3)['share_pct'].sum()),
            'county_top_5_share_pct': float(county.head(5)['share_pct'].sum()),
            'county_top_10_share_pct': float(county.head(10)['share_pct'].sum()),
            'city_pair_median_count': float(city['ev_count'].median()),
            'city_pairs_under_10_vehicles': int(city['ev_count'].lt(10).sum()),
            'city_pairs_with_one_vehicle': int(city['ev_count'].eq(1).sum()),
            'snapshot_date': None,
        },
        'history_snapshot': {
            'date': date.strftime('%Y-%m-%d'), 'source_rows': len(cut), 'counties': len(rates),
            'ev_total': int(cut['Electric Vehicle (EV) Total'].sum()),
            'total_vehicles': int(cut['Total Vehicles'].sum()),
            'statewide_ev_pct': float(100 * rates['ev_total'].sum() / rates['total_vehicles'].sum()),
            'use_groups': usage['vehicle_primary_use'].tolist(),
        },
        'definitions': {
            'population_share_denominator': 'All Population clean rows; no History denominator is joined to Population.',
            'city_key': ['County', 'City'],
            'history_ev_pct': '100 * EV / Total Vehicles after summing Passenger and Truck within each county at the selected month.',
            'population_snapshot_date': 'Not inferred from Model Year; not assumed equal to the selected History date.',
            'rank_ties': 'Population display order breaks ties alphabetically; History ranks use minimum rank for equal values.',
        },
    }
    return dict(zip(TABLE_NAMES, [county, city, rates, usage])), summary


def validate_destinations(paths: list[Path], inputs: list[Path]) -> None:
    resolved = [p.resolve() for p in paths]
    require(len(set(resolved)) == len(resolved), 'Output paths must be distinct.')
    sources = {p.resolve() for p in inputs}
    for path in paths:
        require(path.resolve() not in sources and not path.exists(), f'Choose a new output path: {path}')


def write_tables(tables: dict[str, pd.DataFrame], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(directory/name, index=False, encoding='utf-8-sig', lineterminator='\n')


def export_figures(tables: dict[str, pd.DataFrame], summary: dict, directory: Path, top: int = 10) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5,
                         'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold'})
    population_n = summary['population']['rows']
    date = summary['history_snapshot']['date']

    def bars(frame, label_column, value_column, title, xlabel, output, footer, percent=False):
        selected = frame.head(top).copy()
        fig, ax = plt.subplots(figsize=(11.5, max(5, .43*len(selected)+2)))
        fig.subplots_adjust(left=.26, right=.96, bottom=.22, top=.87)
        labels = selected[label_column].astype(str)
        rectangles = ax.barh(labels, selected[value_column], color='#167D9A', height=.68)
        ax.invert_yaxis()
        maximum = float(selected[value_column].max())
        ax.set_xlim(0, max(maximum*1.35, 1))
        ax.set(title=title, xlabel=xlabel)
        ax.xaxis.grid(True, alpha=.17)
        ax.set_axisbelow(True)
        if not percent:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: integer_label(x)))
        for rectangle, row in zip(rectangles, selected.to_dict('records')):
            label = percent_label(row[value_column]) if percent else f"{integer_label(row[value_column])} ({percent_label(row['share_pct'])})"
            ax.text(rectangle.get_width()+max(maximum*.015,.01), rectangle.get_y()+rectangle.get_height()/2,
                    label, va='center', fontsize=9)
        fig.text(.055,.03,footer,fontsize=8.8,color='#4C5661')
        fig.savefig(directory/output,dpi=220,bbox_inches='tight',pad_inches=.2)
        plt.close(fig)

    bars(tables[TABLE_NAMES[0]], 'county', 'ev_count', f'{min(top,len(tables[TABLE_NAMES[0]]))} quận có nhiều xe điện nhất trong Population',
         'Số bản ghi phương tiện', FIGURE_NAMES[0],
         f'Nguồn: Population clean; mẫu số tỷ trọng = {integer_label(population_n)} bản ghi WA.\nĐây là quy mô trong ảnh chụp Population; không gán ngày của History cho ảnh chụp này.')
    cities = tables[TABLE_NAMES[1]].copy()
    cities['label'] = cities['city'].fillna('Thiếu City') + ' (' + cities['county'] + ')'
    bars(cities, 'label', 'ev_count', f'{min(top,len(cities))} địa bàn County–City có nhiều xe điện nhất',
         'Số bản ghi phương tiện', FIGURE_NAMES[1],
         f'Nguồn: Population clean; mẫu số tỷ trọng = {integer_label(population_n)} bản ghi.\nXếp theo cặp County–City; các thành phố trùng tên ở quận khác không được gộp.')
    bars(tables[TABLE_NAMES[2]], 'county', 'ev_pct', f'{min(top,len(tables[TABLE_NAMES[2]]))} quận có tỷ lệ EV cao nhất — {date}',
         'EV / tổng phương tiện của từng quận (%)', FIGURE_NAMES[2],
         f'Nguồn: History clean tại {date}; đã cộng Passenger và Truck trong từng quận.\nTỷ lệ = 100 × EV / tổng phương tiện cùng quận, cùng tháng; không dùng mẫu số Population.', percent=True)
    usage = tables[TABLE_NAMES[3]]
    fig, axes = plt.subplots(1,2,figsize=(12,5.1))
    fig.subplots_adjust(left=.11,right=.97,bottom=.26,top=.78,wspace=.48)
    for ax,column,title,percent in [(axes[0],'ev_total','Số EV',False),(axes[1],'ev_pct','EV / tổng phương tiện (%)',True)]:
        rectangles = ax.barh(usage['vehicle_primary_use'],usage[column],color=['#167D9A','#D69332'],height=.55)
        ax.invert_yaxis()
        maximum = float(usage[column].max())
        ax.set_xlim(0,max(maximum*1.30,1))
        ax.set_title(title,fontsize=11)
        ax.xaxis.grid(True,alpha=.17)
        ax.set_axisbelow(True)
        if not percent:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_:integer_label(x)))
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
        for rectangle,value in zip(rectangles,usage[column]):
            ax.text(rectangle.get_width()+max(maximum*.025,.005),rectangle.get_y()+rectangle.get_height()/2,
                    percent_label(value) if percent else integer_label(value),va='center',fontsize=9)
    fig.suptitle(f'Passenger và Truck: số EV và tỷ lệ EV — {date}',fontweight='bold')
    fig.text(.055,.035,f'Nguồn: History clean tại {date}.\nMỗi tỷ lệ dùng tổng phương tiện của chính nhóm Passenger/Truck; không phải tỷ trọng nhóm trong toàn bộ EV.',fontsize=9,color='#4C5661')
    fig.savefig(directory/FIGURE_NAMES[3],dpi=220,bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-clean',type=Path,required=True)
    parser.add_argument('--history-clean',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    parser.add_argument('--snapshot-date',default=LAST_MONTH)
    parser.add_argument('--top',type=int,default=10)
    args = parser.parse_args()
    require(args.top > 0,'--top must be positive.')
    validate_destinations([*(args.results_dir/n for n in [*TABLE_NAMES,SUMMARY_NAME]),*(args.figures_dir/n for n in FIGURE_NAMES)],
                          [args.population_clean,args.history_clean])
    tables,summary = build_tables(load_population(args.population_clean),load_history(args.history_clean),args.snapshot_date)
    export_figures(tables,summary,args.figures_dir,args.top)
    write_tables(tables,args.results_dir)
    (args.results_dir/SUMMARY_NAME).write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
