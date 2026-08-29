"""Diagnostic plots for SILO climate variables.

Reads the cached SILO CSV and writes one PNG per group of related
variables (temperature, rainfall, radiation, evapotranspiration, vapour
pressure). All variables are plotted as daily time-series.
"""

from matplotlib import pyplot as plt
from troi import Troi
from os import makedirs
import pandas as pd


PLOT_GROUPS = {
    'temperature': {
        'vars': ['max_temp', 'min_temp'],
        'ylabel': 'Temperature (°C)',
        'title': 'Daily Temperature',
    },
    'rainfall': {
        'vars': ['daily_rain'],
        'ylabel': 'Rainfall (mm)',
        'title': 'Daily Rainfall',
    },
    'radiation': {
        'vars': ['radiation'],
        'ylabel': 'Radiation (MJ/m²)',
        'title': 'Solar Radiation',
    },
    'evapotranspiration': {
        'vars': ['et_short_crop', 'evap_pan'],
        'ylabel': 'ET (mm)',
        'title': 'Evapotranspiration',
    },
    'humidity': {
        'vars': ['vp_deficit', 'vp'],
        'ylabel': 'hPa',
        'title': 'Vapour Pressure',
    },
}


def silo_plot(troi: Troi, groups: dict = None):
    """Plot SILO climate variables grouped by theme.

    Fetches the daily SILO series from the machine-wide ``pysilo`` store
    (downloading only what's missing) and writes one PNG per group to
    ``{troi.out_dir}/{troi.stub}_silo_{group}.png``.

    Args:
        troi: The :class:`troi.Troi`.
        groups: Optional override of the default grouping. If ``None``,
            uses :data:`PLOT_GROUPS` (temperature, rainfall, radiation,
            evapotranspiration, humidity).
    """
    from pysilo.store import Store
    df = Store(config=troi.config).get_df_troi(troi)
    groups = groups or PLOT_GROUPS
    makedirs(troi.out_dir, exist_ok=True)

    for name, cfg in groups.items():
        cols = [c for c in cfg['vars'] if c in df.columns]
        if not cols:
            continue

        fig, ax = plt.subplots(figsize=(12, 4))
        kind = cfg.get('kind', 'line')

        if kind == 'bar':
            monthly = df.set_index('date')[cols].resample('ME').sum()
            monthly.plot(kind='bar', ax=ax, width=0.8)
            ticks = range(0, len(monthly), max(1, len(monthly) // 12))
            ax.set_xticks(list(ticks))
            ax.set_xticklabels([monthly.index[i].strftime('%Y-%m') for i in ticks], rotation=45, ha='right')
        else:
            for col in cols:
                ax.plot(df['date'], df[col], label=col, linewidth=0.5, alpha=0.8)
            ax.legend()

        ax.set_ylabel(cfg['ylabel'])
        ax.set_title(cfg['title'])
        plt.tight_layout()
        out_path = f'{troi.out_dir}/{troi.stub}_silo_{name}.png'
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f'  saved: {out_path}')


def test():
    from PaddockTS.utils import get_example_troi
    silo_plot(get_example_troi())


if __name__ == '__main__':
    test()
