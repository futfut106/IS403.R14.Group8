"""Paths, display and safe demo exports; analytical algorithms remain in source/."""
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from importlib.metadata import version, PackageNotFoundError
import inspect
import os
import uuid
import json
import io

import numpy as np
import pandas as pd
from IPython.display import display, Code, Image


@dataclass
class DemoPaths:
    project: Path
    data_root: Path
    population_raw: Path
    history_raw: Path
    population_clean: Path
    history_clean: Path
    preparation: Path
    output_root: Path


def configure(project):
    project = Path(project).resolve()
    data_root = Path(os.environ.get('EV_DATA_ROOT', str(project.parent.parent))).resolve()
    def chosen(variable, default):
        return Path(os.environ.get(variable, str(default))).expanduser().resolve()
    paths = DemoPaths(
        project, data_root,
        chosen('EV_POPULATION_RAW', data_root/'archive/Electric_Vehicle_Population_Data.csv'),
        chosen('EV_HISTORY_RAW', data_root/'Electric_Vehicle_Population_Size_History_By_County.csv/Electric_Vehicle_Population_Size_History_By_County.csv'),
        chosen('EV_POPULATION_CLEAN', data_root/'archive/EV_Population_Washington_Clean (1).csv'),
        chosen('EV_HISTORY_CLEAN', data_root/'Electric_Vehicle_Population_Size_History_By_County.csv/EV_Population_History_Washington_Clean.csv'),
        chosen('EV_PREPARATION_DIR', data_root/'Du_lieu_dan_xuat/preparation_20261115'),
        chosen('EV_DEMO_ROOT', data_root/'Du_lieu_dan_xuat/notebook_demo'))
    # Notebook exports must stay outside the project to protect tracked outputs and input files.
    if paths.output_root == project or project in paths.output_root.parents:
        raise ValueError('EV_DEMO_ROOT must be outside the repository.')
    pd.set_option('display.max_rows', 12)
    pd.set_option('display.max_columns', 12)
    pd.set_option('display.width', 140)
    return paths


def show_paths(paths):
    display(pd.DataFrame([{'setting': key, 'path': str(value), 'exists': value.exists()}
                          for key, value in vars(paths).items()]))


def demo_directory(paths, name):
    root = paths.output_root.resolve()
    if root == paths.project or paths.project in root.parents:
        raise ValueError('Demo output must remain outside the repository.')
    stamp = datetime.now(timezone(timedelta(hours=7))).strftime('%Y%m%d_%H%M%S')
    output = root / (name+'_'+stamp+'_'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    return output


def _save_demo_bytes(path, payload):
    """Create a new export, or keep an identical existing export without rewriting it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(payload)
        return True
    except FileExistsError:
        existing = path.read_bytes()
        if existing == payload or existing.replace(b'\r\n', b'\n') == payload.replace(b'\r\n', b'\n'):
            return False
        raise FileExistsError('Existing export has different content; create a new demo directory: '+str(path))


def save_table(frame, path):
    """Export CSV; rerunning an unchanged export is safe and does not overwrite it."""
    payload = frame.to_csv(index=False, lineterminator='\n').encode('utf-8-sig')
    _save_demo_bytes(path, payload)


def save_json(value, path):
    """Export JSON; preserve an identical file and block conflicting content."""
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
    _save_demo_bytes(path, payload)


def show_source(function):
    display(Code(inspect.getsource(function), language='python'))


def show_png(path):
    display(Image(filename=str(path), width=950))


def environment():
    """Report package metadata without requiring every modeling library for every demo."""
    packages = ['pandas', 'numpy', 'scipy', 'matplotlib', 'statsmodels', 'scikit-learn', 'xgboost', 'ipykernel']
    rows = []
    for package in packages:
        try:
            installed_version = version(package)
            status = 'Đã tìm thấy'
        except PackageNotFoundError:
            installed_version = None
            status = 'Không tìm thấy trong kernel hiện tại'
        rows.append({'package': package, 'version': installed_version, 'status': status})
    return pd.DataFrame(rows)


def compare_values(label, actual, reference, rtol=1e-7, atol=1e-6):
    actual, reference = np.asarray(actual, dtype=float), np.asarray(reference, dtype=float)
    np.testing.assert_allclose(actual, reference, rtol=rtol, atol=atol, equal_nan=True,
                               err_msg=label+': result differs; check data/config/environment rather than editing outputs.')
    finite = np.isfinite(actual) & np.isfinite(reference)
    maximum = float(np.max(np.abs(actual[finite]-reference[finite]))) if finite.any() else 0.
    display(pd.DataFrame([{'check': label, 'passed': True, 'max_absolute_difference': maximum}]))


def read_series(paths):
    from source.forecasting.protocol import load_series
    return load_series(paths.preparation/'statewide_monthly.csv')


def series_plot(train, test, predictions):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig, ax = plt.subplots(figsize=(10, 4.7), layout='constrained')
    ax.plot(train['date'].iloc[-12:], train['ev_total'].iloc[-12:], color='gray', label='Train (12 months)')
    ax.plot(test['date'], test['ev_total'], color='black', marker='o', ms=3, label='Actual test')
    for label, pred in predictions.items():
        ax.plot(test['date'], pred, '--o', ms=3, label=label)
    ax.axvline(train['date'].iloc[-1], linestyle=':', color='gray')
    ax.set(ylabel='EV Total (vehicles)', title='Fixed origin: November 2022; no test updates')
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=130)
    display(Image(data=buffer.getvalue(), width=950))
    plt.close(fig)
