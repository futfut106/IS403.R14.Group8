"""Describe vehicle characteristics from Population clean; export five tables and four figures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

POPULATION_COLUMNS = [
    'County', 'City', 'State', 'Postal Code', 'Model Year', 'Make', 'Model',
    'Electric Vehicle Type', 'Clean Alternative Fuel Vehicle (CAFV) Eligibility',
    'Electric Range', 'Base MSRP',
]
TYPE_MAP = {'Battery Electric Vehicle (BEV)': 'BEV', 'Plug-in Hybrid Electric Vehicle (PHEV)': 'PHEV'}
TABLE_NAMES = ['vehicle_type_frequency.csv', 'cafv_frequency.csv', 'make_frequency.csv',
               'model_year_frequency.csv', 'range_summary.csv']
FIGURE_NAMES = ['vehicle_type_share.png', 'top_makes.png', 'model_year_distribution.png', 'range_by_vehicle_type.png']


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise ValueError(message)


def load_population(path: Path) -> pd.DataFrame:
    """Validate an analytical copy of Population clean; do not reclean it."""
    frame = pd.read_csv(path, encoding='utf-8-sig', low_memory=False)
    require(list(frame.columns) == POPULATION_COLUMNS, 'Expected the eleven Population clean columns in order.')
    require(not frame.empty and frame['State'].eq('WA').all(), 'Population must be nonempty and contain WA only.')
    types = frame['Electric Vehicle Type'].dropna()
    require(types.isin(TYPE_MAP).all(), 'Unexpected nonmissing vehicle type labels.')
    for col in ['Model Year', 'Electric Range']:
        frame[col] = pd.to_numeric(frame[col], errors='raise')
        require(not frame[col].isin([float('inf'), -float('inf')]).any(), f'Nonfinite value in {col}.')
    years = frame['Model Year'].dropna()
    require(years.gt(0).all() and years.mod(1).eq(0).all(), 'Model Year must be a positive integer or missing.')
    require(frame['Electric Range'].dropna().gt(0).all(), 'Clean Range must be positive or missing; zero values require preprocessing.')
    return frame


def frequency(series: pd.Series, name: str, chronological: bool = False) -> pd.DataFrame:
    table = series.value_counts(dropna=False, sort=False).rename_axis(name).reset_index(name='count')
    table['is_missing'] = table[name].isna()
    if chronological:
        table[name] = pd.array(table[name], dtype='Int64')
        table = table.sort_values(name, na_position='last', kind='stable')
    else:
        table = table.sort_values(['is_missing', 'count', name], ascending=[True, False, True], na_position='last', kind='stable')
    table['population_n'] = len(series)
    table['share_pct'] = 100 * table['count'] / len(series)
    return table[[name, 'count', 'share_pct', 'population_n', 'is_missing']].reset_index(drop=True)


def build_tables(population: pd.DataFrame) -> dict[str, pd.DataFrame]:
    vehicle_types = population['Electric Vehicle Type'].map(TYPE_MAP)
    tables = {
        'vehicle_type_frequency.csv': frequency(vehicle_types, 'vehicle_type'),
        'cafv_frequency.csv': frequency(population['Clean Alternative Fuel Vehicle (CAFV) Eligibility'], 'cafv_status'),
        'make_frequency.csv': frequency(population['Make'], 'make'),
        'model_year_frequency.csv': frequency(population['Model Year'], 'model_year', chronological=True),
    }
    groups = [('ALL', population), ('BEV', population.loc[vehicle_types.eq('BEV')]),
              ('PHEV', population.loc[vehicle_types.eq('PHEV')])]
    if vehicle_types.isna().any():
        groups.append(('MISSING_TYPE', population.loc[vehicle_types.isna()]))
    rows = []
    for name, frame in groups:
        valid = frame['Electric Range'].dropna()
        n, total = len(valid), len(frame)
        q1 = float(valid.quantile(0.25, interpolation='linear')) if n else None
        q3 = float(valid.quantile(0.75, interpolation='linear')) if n else None
        rows.append({
            'group': name, 'total_n': total, 'valid_n': n, 'missing_n': total-n,
            'valid_pct': 100*n/total if total else None,
            'missing_pct': 100*(total-n)/total if total else None,
            'mean_miles': float(valid.mean()) if n else None,
            'median_miles': float(valid.median()) if n else None,
            'std_miles': float(valid.std(ddof=1)) if n > 1 else None,
            'min_miles': float(valid.min()) if n else None,
            'q1_miles': q1, 'q3_miles': q3,
            'iqr_miles': q3-q1 if n else None,
            'max_miles': float(valid.max()) if n else None,
        })
    tables['range_summary.csv'] = pd.DataFrame(rows)
    return tables


def integer_label(value: float) -> str:
    return f'{value:,.0f}'.replace(',', '.')


def percent_label(value: float) -> str:
    return f'{value:.2f}'.replace('.', ',') + '%'


def export_figures(population: pd.DataFrame, tables: dict[str, pd.DataFrame], directory: Path, top_makes: int) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'savefig.facecolor': 'white'})
    colors = {'BEV': '#167D9A', 'PHEV': '#D69332', 'MISSING_TYPE': '#8D9399'}
    count_format = FuncFormatter(lambda x, _: integer_label(x))
    source_note = f'Nguồn: Population clean, phạm vi WA; n = {integer_label(len(population))} bản ghi.'

    def save(fig, name, note):
        fig.text(0.07, 0.025, note, fontsize=9, color='#4C5661', va='bottom')
        fig.savefig(directory/name, dpi=220, bbox_inches='tight', pad_inches=0.2)
        plt.close(fig)

    # Shares use the full Population denominator, including missing labels if any.
    types = tables['vehicle_type_frequency.csv']
    labels = ['Thiếu loại xe' if row.is_missing else row.vehicle_type for row in types.itertuples()]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    fig.subplots_adjust(left=0.15, bottom=0.23, right=0.94, top=0.84)
    bars = ax.barh(labels, types['share_pct'], color=[colors.get(label, '#8D9399') for label in labels], height=0.55)
    ax.invert_yaxis()
    ax.set(xlim=(0, 110), xlabel='Tỷ trọng trong toàn bộ Population (%)', title='Cơ cấu đội xe điện theo loại xe')
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.grid(True, alpha=0.17)
    ax.set_axisbelow(True)
    for bar, row in zip(bars, types.itertuples()):
        ax.text(bar.get_width()+1.5, bar.get_y()+bar.get_height()/2,
                f'{integer_label(row.count)} xe ({percent_label(row.share_pct)})', va='center', fontsize=10)
    save(fig, FIGURE_NAMES[0], source_note)

    makes = tables['make_frequency.csv']
    top = makes.loc[~makes['is_missing']].head(top_makes)
    fig, ax = plt.subplots(figsize=(11, max(4.5, 0.42*len(top)+1.8)))
    fig.subplots_adjust(left=0.19, bottom=0.18, right=0.95, top=0.88)
    if len(top):
        bars = ax.barh(top['make'], top['count'], color='#167D9A', height=0.68)
        ax.invert_yaxis()
        ax.set_xlim(0, top['count'].max()*1.42)
        for bar, row in zip(bars, top.itertuples()):
            ax.text(bar.get_width()+top['count'].max()*0.015, bar.get_y()+bar.get_height()/2,
                    f'{integer_label(row.count)} ({percent_label(row.share_pct)})', va='center', fontsize=9)
    else:
        ax.text(0.5, 0.5, 'Không có hãng xe hợp lệ', transform=ax.transAxes, ha='center')
    ax.set(title=f'{len(top)} hãng có số xe điện nhiều nhất', xlabel='Số bản ghi phương tiện')
    ax.xaxis.set_major_formatter(count_format)
    ax.xaxis.grid(True, alpha=0.17)
    ax.set_axisbelow(True)
    missing_make = int(population['Make'].isna().sum())
    save(fig, FIGURE_NAMES[1], source_note + '\nTỷ lệ tính trên toàn bộ Population; chỉ vẽ các hãng đứng đầu. Thiếu hãng: '+integer_label(missing_make)+'.')

    years = tables['model_year_frequency.csv']
    valid_years = years.loc[~years['is_missing']]
    fig, ax = plt.subplots(figsize=(11, 5.7))
    fig.subplots_adjust(left=0.11, bottom=0.25, right=0.97, top=0.87)
    if len(valid_years):
        ax.bar(valid_years['model_year'].astype(int), valid_years['count'], color='#167D9A', width=0.75)
        first_year, last_year = int(valid_years['model_year'].min()), int(valid_years['model_year'].max())
        step = max(1, (last_year-first_year+12)//13)
        ax.set_xticks(sorted({first_year, last_year, *range(first_year, last_year+1, step)}))
        ax.set_xlim(first_year-0.75, last_year+0.75)
    ax.set(title='Phân bố đội xe điện theo năm mẫu xe', xlabel='Năm mẫu xe (Model Year)', ylabel='Số bản ghi phương tiện')
    ax.yaxis.set_major_formatter(count_format)
    ax.yaxis.grid(True, alpha=0.17)
    ax.set_axisbelow(True)
    save(fig, FIGURE_NAMES[2], source_note + '\nModel Year là năm mẫu xe, không phải năm bán/đăng ký. Thiếu năm: '+integer_label(population['Model Year'].isna().sum())+'.')

    mapped_types = population['Electric Vehicle Type'].map(TYPE_MAP)
    summary = tables['range_summary.csv'].set_index('group')
    data, labels, group_colors = [], [], []
    for kind in ['BEV', 'PHEV', 'MISSING_TYPE']:
        if kind not in summary.index:
            continue
        row = summary.loc[kind]
        mask = mapped_types.isna() if kind == 'MISSING_TYPE' else mapped_types.eq(kind)
        values = population.loc[mask, 'Electric Range'].dropna()
        if len(values):
            data.append(values.to_numpy())
            title = 'Thiếu loại xe' if kind == 'MISSING_TYPE' else kind
            labels.append(f'{title}\nHợp lệ: {integer_label(row.valid_n)}; thiếu: {integer_label(row.missing_n)}')
            group_colors.append(colors[kind])
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    fig.subplots_adjust(left=0.11, bottom=0.28, right=0.97, top=0.88)
    if data:
        boxes = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.5, whis=1.5,
                           showfliers=True, medianprops={'color': '#20262E', 'linewidth': 1.8},
                           flierprops={'marker': '.', 'markersize': 2.5, 'alpha': 0.3})
        for box, color in zip(boxes['boxes'], group_colors):
            box.set_facecolor(color)
            box.set_alpha(0.65)
    else:
        ax.text(0.5, 0.5, 'Không có Electric Range hợp lệ', transform=ax.transAxes, ha='center')
    ax.set(title='Phân bố Electric Range theo loại xe', ylabel='Electric Range (mile)')
    ax.yaxis.grid(True, alpha=0.17)
    ax.set_axisbelow(True)
    save(fig, FIGURE_NAMES[3], source_note+'\nHộp: Q1–Q3; đường giữa: trung vị; râu theo 1,5 IQR. Các điểm ngoài râu được giữ lại.\nChỉ vẽ Range hợp lệ; không điền giá trị thiếu hoặc loại ngoại lệ.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-clean', type=Path, required=True)
    parser.add_argument('--results-dir', type=Path, required=True)
    parser.add_argument('--figures-dir', type=Path, required=True)
    parser.add_argument('--top-makes', type=int, default=10)
    args = parser.parse_args()
    require(args.top_makes > 0, '--top-makes must be positive.')
    outputs = [args.results_dir/name for name in TABLE_NAMES] + [args.figures_dir/name for name in FIGURE_NAMES]
    resolved = [path.resolve() for path in outputs]
    require(len(set(resolved)) == len(resolved), 'Output paths must be distinct.')
    for path in outputs:
        require(path.resolve() != args.population_clean.resolve() and not path.exists(), f'Choose a new output path: {path}')
    population = load_population(args.population_clean)
    tables = build_tables(population)
    # Import plotting dependencies before writing any tables.
    import matplotlib
    args.results_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)
    export_figures(population, tables, args.figures_dir, args.top_makes)
    for name, frame in tables.items():
        frame.to_csv(args.results_dir/name, index=False, encoding='utf-8-sig', lineterminator='\n')
    print(json.dumps({'population_rows': len(population), 'range_valid': int(population['Electric Range'].notna().sum()),
                      'range_missing': int(population['Electric Range'].isna().sum()),
                      'tables': TABLE_NAMES, 'figures': FIGURE_NAMES,
                      'environment': {'pandas': pd.__version__, 'matplotlib': matplotlib.__version__}}, indent=2))


if __name__ == '__main__':
    main()
