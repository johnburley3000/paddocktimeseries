"""Resample + gap-fill + Savitzky-Golay smoothing on a synthetic series."""

import numpy as np
import pandas as pd
import xarray as xr

from PaddockTS.Phenology.make_smoothed_paddock_time_series import (
    make_smoothed_paddock_time_series)


def _gappy_series(n_paddocks=2, year=2022):
    """Irregular NDVI over one year with NaN dropouts (cloud losses)."""
    rng = np.random.default_rng(1)
    time = pd.date_range(f'{year}-01-03', f'{year}-12-28', freq='5D')
    doy = time.dayofyear.to_numpy()
    curve = 0.2 + 0.5 * np.sin(np.pi * (doy - doy.min()) / (doy.max() - doy.min())) ** 2
    ndvi = np.stack([curve + 0.01 * p for p in range(n_paddocks)])
    dropout = rng.random(ndvi.shape) < 0.3
    ndvi[dropout] = np.nan
    return xr.Dataset(
        {'NDVI': (('paddock', 'time'), ndvi)},
        coords={'paddock': [str(p + 1) for p in range(n_paddocks)],
                'time': time},
    )


def test_smoothed_series_is_uniform_and_gapless(tmp_troi):
    ds = _gappy_series()
    out = make_smoothed_paddock_time_series(
        tmp_troi, ds_paddockTS=ds, paddocks_filepath='synthetic.gpkg')

    # Uniform 10-day cadence.
    deltas = np.diff(out.time.values).astype('timedelta64[D]').astype(int)
    assert (deltas == 10).all()

    # Gap-filled: the smoothed variable has no NaNs left.
    assert not np.isnan(out['NDVI'].values).any()

    # 'observed' marks which bins held at least one real observation.
    assert 'observed' in out.data_vars
    assert out['observed'].dtype == bool

    # Smoothing must not invent values far outside the input range.
    lo, hi = np.nanmin(ds['NDVI'].values), np.nanmax(ds['NDVI'].values)
    assert out['NDVI'].values.min() > lo - 0.2
    assert out['NDVI'].values.max() < hi + 0.2


def test_smoothed_zarr_persisted_with_marker(tmp_troi):
    make_smoothed_paddock_time_series(
        tmp_troi, ds_paddockTS=_gappy_series(), paddocks_filepath='synthetic.gpkg')
    from PaddockTS.utils import check_if_valid_zarr_exists
    assert check_if_valid_zarr_exists(
        f'{tmp_troi.tmp_dir}/synthetic_timeseries_smoothed.zarr')
