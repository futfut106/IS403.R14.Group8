"""Prepare analytical samples and a monthly series from two clean EV datasets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .build_analysis_samples import build_analysis_samples, load_population
    from .build_monthly_series import build_monthly_series, load_history, write_outputs
else:
    from build_analysis_samples import build_analysis_samples, load_population
    from build_monthly_series import build_monthly_series, load_history, write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-clean', type=Path, required=True)
    parser.add_argument('--history-clean', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True, help='Local directory for the five derived input CSVs.')
    parser.add_argument('--summary-dir', type=Path, required=True, help='Directory for the two preparation summaries.')
    args = parser.parse_args()
    population = load_population(args.population_clean)
    history = load_history(args.history_clean)
    monthly, monthly_summary = build_monthly_series(history)
    samples, sample_summary = build_analysis_samples(population, history)
    outputs = {args.output_dir/name: frame for name, frame in samples.items()}
    outputs[args.output_dir/'statewide_monthly.csv'] = monthly
    outputs[args.summary_dir/'sample_summary.csv'] = sample_summary
    outputs[args.summary_dir/'monthly_series_summary.json'] = monthly_summary
    write_outputs(outputs, [args.population_clean, args.history_clean])
    print(json.dumps({'monthly_rows': len(monthly), 'train_months': 71, 'test_months': 12,
                      'sample_rows': {name: len(frame) for name, frame in samples.items()},
                      'output_dir': str(args.output_dir), 'summary_dir': str(args.summary_dir)}, indent=2))


if __name__ == '__main__':
    main()
