"""Run vehicle, geographic and monthly descriptive analysis with explicit input paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from source.descriptive import vehicle_characteristics as vehicle
from source.descriptive import spatial_distribution as spatial
from source.descriptive import monthly_trends as trends
from source.preparation.build_monthly_series import LAST_MONTH, load_history, require


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-clean',type=Path,required=True)
    parser.add_argument('--history-clean',type=Path,required=True)
    parser.add_argument('--results-dir',type=Path,required=True)
    parser.add_argument('--figures-dir',type=Path,required=True)
    parser.add_argument('--snapshot-date',default=LAST_MONTH)
    parser.add_argument('--top',type=int,default=10)
    parser.add_argument('--skip-vehicle',action='store_true',help='Only create geographic and monthly outputs; preserve existing vehicle outputs.')
    args = parser.parse_args()
    require(args.top>0,'--top must be positive.')
    table_names = spatial.TABLE_NAMES + trends.TABLE_NAMES + ([] if args.skip_vehicle else vehicle.TABLE_NAMES)
    figure_names = spatial.FIGURE_NAMES + trends.FIGURE_NAMES + ([] if args.skip_vehicle else vehicle.FIGURE_NAMES)
    spatial.validate_destinations([*(args.results_dir/n for n in [*table_names,spatial.SUMMARY_NAME]),
                                   *(args.figures_dir/n for n in figure_names)],
                                  [args.population_clean,args.history_clean])
    population = vehicle.load_population(args.population_clean)
    history = load_history(args.history_clean)
    spatial_tables,summary = spatial.build_tables(population,history,args.snapshot_date)
    monthly_tables = trends.build_tables(history)
    all_tables = {**spatial_tables,**monthly_tables}
    if not args.skip_vehicle:
        vehicle_tables = vehicle.build_tables(population)
        all_tables.update(vehicle_tables)
        args.figures_dir.mkdir(parents=True,exist_ok=True)
        vehicle.export_figures(population,vehicle_tables,args.figures_dir,args.top)
    spatial.export_figures(spatial_tables,summary,args.figures_dir,args.top)
    trends.export_figures(monthly_tables,args.figures_dir)
    spatial.write_tables(all_tables,args.results_dir)
    (args.results_dir/spatial.SUMMARY_NAME).write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'tables':len(all_tables),'json_summaries':1,'figures':len(figure_names),
                      'snapshot_date':args.snapshot_date,'vehicle_outputs_included':not args.skip_vehicle},indent=2))


if __name__ == '__main__':
    main()
