"""Figures for the common fixed-origin evaluation window."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from .comparison import MODEL_ORDER

FIGURES = ['comparison_accuracy.png', 'comparison_forecasts.png',
           'comparison_monthly_errors.png', 'comparison_cumulative_rmse.png']


def draw(tables, destination):
    scores = tables['comparison_metrics.csv']
    colors = {model: plt.get_cmap('tab10')(i) for i, model in enumerate(MODEL_ORDER)}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), layout='constrained')
    for ax, metric in zip(axes, ['rmse', 'mae']):
        ax.barh(scores['model'], scores[metric], color=[colors[m] for m in scores['model']])
        for i, value in enumerate(scores[metric]):
            ax.text(value + scores[metric].max() * .015, i, f'{value:,.1f}', va='center', fontsize=8)
        ax.invert_yaxis()
        ax.set(xlabel=f'{metric.upper()} (vehicles)', xlim=(0, scores[metric].max() * 1.22))
        ax.grid(axis='x', alpha=.2)
    fig.suptitle('Fixed-origin test accuracy: December 2022–November 2023')
    fig.savefig(destination / FIGURES[0], dpi=160)
    plt.close(fig)
    pred = tables['comparison_predictions.csv']
    dates = pd.to_datetime(pred['date'])
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.5), sharex=True, sharey=True, layout='constrained')
    for ax, model in zip(axes.flat, MODEL_ORDER):
        ax.plot(dates, pred['actual'], color='black', label='Actual', linewidth=1.8)
        ax.plot(dates, pred[model], '--o', ms=2.5, color=colors[model], label='Forecast')
        ax.set_title(model)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 5, 9]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        ax.tick_params(axis='x', labelsize=8)
        ax.grid(alpha=.2)
    axes[0, 0].legend(fontsize=8)
    fig.supylabel('EV Total (vehicles)')
    fig.suptitle('One forecast origin: November 2022; shared axes across methods')
    fig.savefig(destination / FIGURES[1], dpi=160)
    plt.close(fig)
    errors = tables['comparison_errors.csv']
    wide = errors.pivot(index='model', columns='date', values='error').reindex(MODEL_ORDER)
    matrix = wide.to_numpy()
    limit = float(np.abs(matrix).max())
    fig, ax = plt.subplots(figsize=(13, 5.6), layout='constrained')
    im = ax.imshow(matrix, cmap='RdBu_r', vmin=-limit, vmax=limit, aspect='auto')
    ax.set(yticks=range(8), yticklabels=MODEL_ORDER, xticks=range(12),
           xticklabels=pd.to_datetime(wide.columns).strftime('%m/%Y'),
           title='Monthly error = actual − forecast; positive means underprediction')
    ax.tick_params(axis='x', rotation=45)
    for i in range(8):
        for j in range(12):
            ax.text(j, i, f'{matrix[i,j]:,.0f}', ha='center', va='center', fontsize=7,
                    color='white' if abs(matrix[i,j]) > .60 * limit else 'black')
    fig.colorbar(im, ax=ax, label='Error (vehicles)', shrink=.85)
    fig.savefig(destination / FIGURES[2], dpi=160)
    plt.close(fig)
    cumulative = tables['comparison_cumulative_metrics.csv']
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    for ax, models, title in [(axes[0], MODEL_ORDER, 'All methods'),
                              (axes[1], MODEL_ORDER[2:], 'Six fitted models (separate y scale)')]:
        for model in models:
            part = cumulative.loc[cumulative['model'].eq(model)]
            ax.plot(part['through_horizon'], part['rmse'], color=colors[model], label=model, marker='o', ms=2)
        ax.set(xlabel='Through horizon h (months 1…h)', ylabel='Cumulative RMSE (vehicles)',
               title=title, xticks=[1, 3, 6, 9, 12])
        ax.grid(alpha=.2)
        ax.legend(fontsize=7, ncol=2)
    fig.suptitle('Descriptive cumulative error within one test window; no independent horizon samples')
    fig.savefig(destination / FIGURES[3], dpi=160)
    plt.close(fig)
