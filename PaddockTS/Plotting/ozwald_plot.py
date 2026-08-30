"""Diagnostic plots for OzWALD daily and 8-day climate / vegetation data.

Each plot file is a single panel covering the full date range of a
``Troi``. Variables are grouped thematically (temperature, precipitation,
vegetation index, etc.) and plotted as thin-line time-series.
"""

from matplotlib import pyplot as plt
from troi import Troi
from os import makedirs
import pandas as pd


DAILY_GROUPS = {
    'temperature': {
        'vars': ['Tmax', 'Tmin'],
        'ylabel': 'Temperature (°C)',
        'title': 'OzWALD Daily Temperature',
    },
    'precipitation': {
        'vars': ['Pg'],
        'ylabel': 'Precipitation (mm)',
        'title': 'OzWALD Daily Precipitation',
    },
    'wind': {
        'vars': ['Uavg', 'Ueff'],
        'ylabel': 'Wind Speed (m/s)',
        'title': 'OzWALD Wind Speed',
    },
    'radiation': {
        'vars': ['DWLReff'],
        'ylabel': 'Radiation (W/m²)',
        'title': 'OzWALD Downwelling Longwave Radiation',
    },
}

EIGHTDAY_GROUPS = {
    'vegetation_index': {
        'vars': ['NDVI', 'EVI'],
        'ylabel': 'Index',
        'title': 'OzWALD Vegetation Indices',
    },
    'vegetation_cover': {
        'vars': ['PV', 'NPV', 'BS'],
        'ylabel': 'Fraction',
        'title': 'OzWALD Fractional Cover',
    },
    'lai_gpp': {
        'vars': ['LAI', 'GPP'],
        'ylabel': 'LAI (m²/m²) / GPP (g m⁻² d⁻¹)',
        'title': 'OzWALD LAI & GPP',
    },
    'water': {
        'vars': ['Ssoil', 'Qtot'],
        'ylabel': 'mm',
        'title': 'OzWALD Soil Moisture & Runoff',
    },
}


def _plot_groups(df, time_col, groups, troi, prefix):
    makedirs(troi.out_dir, exist_ok=True)

    for name, cfg in groups.items():
        cols = [c for c in cfg['vars'] if c in df.columns]
        if not cols:
            continue

        fig, ax = plt.subplots(figsize=(12, 4))
        kind = cfg.get('kind', 'line')

        if kind == 'bar':
            monthly = df.set_index(time_col)[cols].resample('ME').sum()
            monthly.plot(kind='bar', ax=ax, width=0.8)
            ticks = range(0, len(monthly), max(1, len(monthly) // 12))
            ax.set_xticks(list(ticks))
            ax.set_xticklabels([monthly.index[i].strftime('%Y-%m') for i in ticks], rotation=45, ha='right')
        else:
            for col in cols:
                ax.plot(df[time_col], df[col], label=col, linewidth=0.5, alpha=0.8)
            ax.legend()

        ax.set_ylabel(cfg['ylabel'])
        ax.set_title(cfg['title'])
        plt.tight_layout()
        out_path = f'{troi.out_dir}/{troi.stub}_{prefix}_{name}.png'
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f'  saved: {out_path}')


def ozwald_daily_plot(troi: Troi, groups: dict = None):
    """Plot OzWALD daily climate variables grouped by theme.

    Reads the daily series from the machine-wide :mod:`pyozwald` store
    and writes one PNG per group to
    ``{troi.out_dir}/{troi.stub}_ozwald_daily_{group}.png``.

    Args:
        troi: The :class:`troi.Troi`.
        groups: Optional override of the default grouping. Maps a group
            name to ``{'vars': [...], 'ylabel': str, 'title': str,
            'kind': 'line'|'bar'}``. If ``None``, uses
            :data:`DAILY_GROUPS` (temperature, precipitation, wind,
            radiation).
    """
    from pyozwald.store import Store
    df = Store(config=troi.config).get_df_troi(troi, cadence='daily')
    _plot_groups(df, 'time', groups or DAILY_GROUPS, troi, 'ozwald_daily')


def ozwald_8day_plot(troi: Troi, groups: dict = None):
    """Plot OzWALD 8-day vegetation / water variables grouped by theme.

    Reads the 8-day series from the machine-wide :mod:`pyozwald` store
    and writes one PNG per group to
    ``{troi.out_dir}/{troi.stub}_ozwald_8day_{group}.png``.

    Args:
        troi: The :class:`troi.Troi`.
        groups: Optional override of the default grouping. If ``None``,
            uses :data:`EIGHTDAY_GROUPS` (vegetation index, fractional
            cover, LAI/GPP, soil water/runoff).
    """
    from pyozwald.store import Store
    df = Store(config=troi.config).get_df_troi(troi, cadence='8day')
    _plot_groups(df, 'time', groups or EIGHTDAY_GROUPS, troi, 'ozwald_8day')


def test():
    from PaddockTS.utils import get_example_troi
    q = get_example_troi()
    ozwald_daily_plot(q)
    ozwald_8day_plot(q)


if __name__ == '__main__':
    test()
