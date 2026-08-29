"""Assemble the DAESIM climate-forcing table from the lab's data stores.

DAESIM (the lab's agro-ecosystem simulator) takes one tidy daily table:
SILO radiation plus OzWALD daily meteorology and 8-day biophysical
series (forward-filled to daily), renamed to DAESIM's vocabulary. All
fetching goes through the machine-wide `pysilo` and `pyozwald` stores,
so building a forcing table for an overlapping site or an extended
season downloads only what's missing — usually nothing.
"""
from datetime import date
from os import makedirs
from os.path import exists

import pandas as pd

from troi import Config, config as default_config
from troi import Troi

RENAME = {
    'Pg': 'Precipitation',
    'Qtot': 'Runoff',
    'Tmin': 'Minimum temperature',
    'Tmax': 'Maximum temperature',
    'Ssoil': 'Soil moisture',
    'GPP': 'Vegetation growth',
    'LAI': 'Vegetation leaf area',
    'VPeff': 'VPeff',
    'Uavg': 'Uavg',
    'radiation': 'SRAD',
}

DAESIM_COLUMNS = [
    'Precipitation',
    'Runoff',
    'Minimum temperature',
    'Maximum temperature',
    'Soil moisture',
    'Vegetation growth',
    'Vegetation leaf area',
    'VPeff',
    'Uavg',
    'SRAD',
]

OZWALD_DAILY_VARS = ['Pg', 'Tmax', 'Tmin', 'Uavg', 'VPeff']
OZWALD_8DAY_VARS = ['Ssoil', 'Qtot', 'LAI', 'GPP']

get_filename = lambda q: f'{q.out_dir}/{q.stub}_DAESim_forcing.csv'


def daesim_forcing_df(lat: float, lon: float, start: date, end: date,
                      config: Config = default_config) -> pd.DataFrame:
    """Build the DAESIM forcing table for a coordinate and date range.

    Troi-agnostic — the data-assembly layer. Pipelines that speak
    :class:`troi.Troi` use :func:`daesim_forcing`, which
    adds stub-keyed CSV caching on top.

    Args:
        lat: Latitude in decimal degrees (EPSG:4326).
        lon: Longitude in decimal degrees.
        start: Inclusive start date.
        end: Inclusive end date.
        config: Data root (and SILO email) — defaults to the loaded config.

    Returns:
        pandas.DataFrame: One row per day, ``date`` plus the ten DAESIM
        forcing columns.
    """
    from pysilo.store import Store as SiloStore
    from pyozwald.store import Store as OzWaldStore

    silo = SiloStore(config=config).get_df(lat, lon, start, end)
    ozwald = OzWaldStore(config=config)
    daily = ozwald.get_df(lat, lon, start, end, cadence='daily',
                          variables=OZWALD_DAILY_VARS)
    eightday = ozwald.get_df(lat, lon, start, end, cadence='8day',
                             variables=OZWALD_8DAY_VARS)

    # SILO: just need radiation, indexed by date
    silo = silo[['date', 'radiation']].set_index('date')

    # OzWALD daily
    daily = daily.rename(columns={'time': 'date'}).set_index('date')

    # OzWALD 8-day: forward-fill to daily
    eightday = eightday.rename(columns={'time': 'date'}).set_index('date')
    eightday = eightday.resample('D').ffill()

    # Merge on date
    df = silo.join(daily, how='inner').join(eightday, how='left')
    df.rename(columns=RENAME, inplace=True)
    df = df[DAESIM_COLUMNS]
    df.index.name = 'date'
    return df.reset_index()


def daesim_forcing(troi: Troi) -> pd.DataFrame:
    """DAESIM forcing for the centre of ``troi.bbox``, cached as
    ``{troi.out_dir}/{troi.stub}_DAESim_forcing.csv``.

    The CSV cache makes the assembled *product* reproducible per stub;
    the underlying observations are cached machine-wide by the stores
    regardless, so even a cache miss here re-downloads nothing already
    held locally.
    """
    makedirs(troi.out_dir, exist_ok=True)
    filename = get_filename(troi)

    if exists(filename):
        print(f'  cached: {filename}')
        return pd.read_csv(filename, parse_dates=['date'])

    df = daesim_forcing_df(troi.centre_lat, troi.centre_lon,
                           troi.start, troi.end, config=troi.config)
    df.to_csv(filename, index=False)
    print(f'  saved: {filename} ({len(df)} days)')
    return df


def test():
    """Live: assemble a one-year forcing table and verify shape/columns."""
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix='daesim_forcing_test_')
    cfg = Config(out_dir=tmpdir, tmp_dir=tmpdir, email=default_config.email)
    q = Troi(
        bbox=[148.36265, -33.52606, 148.38265, -33.50606],
        start=date(2023, 1, 1), end=date(2023, 12, 31),
        stub='daesim_forcing_test', config=cfg,
    )
    df = daesim_forcing(q)
    print(df.head())
    ok = (
        list(df.columns) == ['date'] + DAESIM_COLUMNS
        and len(df) == 365
        and df['Precipitation'].notna().all()
        and df['Soil moisture'].notna().sum() > 300  # 8-day ffilled to daily
        and exists(get_filename(q))
    )
    # second call must come from the CSV cache
    df2 = daesim_forcing(q)
    return ok and len(df2) == len(df)


if __name__ == '__main__':
    print(test())
