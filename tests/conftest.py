"""Shared fixtures: an isolated Troi and synthetic inputs.

Every fixture is offline — no network, no credentials, no model
checkpoints beyond the TFLite files bundled in the package. The
``tmp_troi`` fixture points the Troi registry and all output/cache
directories at a per-test temporary directory, so tests never touch
``~/.config/Troi.json``, the machine-wide registry, or real data roots.
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

# The Sentinel-2 DN bands the pipeline consumes, with the int16 nodata
# sentinel the cleaned cube uses for masked pixels.
S2_BANDS = ('nbart_blue', 'nbart_green', 'nbart_red',
            'nbart_nir_1', 'nbart_swir_2', 'nbart_swir_3')
NODATA = -999


@pytest.fixture
def tmp_troi(tmp_path):
    """A Troi over a tiny bbox with registry + dirs isolated to tmp_path."""
    from datetime import date
    from troi import Troi, Config

    out = tmp_path / 'out'
    tmp = tmp_path / 'tmp'
    cfg = Config(out_dir=str(out), tmp_dir=str(tmp))
    return Troi(
        bbox=[148.36265, -33.52606, 148.38265, -33.50606],
        start=date(2022, 1, 1),
        end=date(2022, 12, 31),
        stub='pytest_troi',
        config=cfg,
    )


def synthetic_s2(nt=4, ny=8, nx=8, seed=0):
    """A cleaned-cube-shaped Sentinel-2 dataset: int16 DN bands on
    (time, y, x) with ``nodata`` attrs and a metre-based grid (as
    delivered by pysentinel2 in EPSG:6933, 10 m pixels)."""
    rng = np.random.default_rng(seed)
    time = pd.date_range('2022-01-05', periods=nt, freq='16D')
    y = 1_000_000.0 - 10.0 * np.arange(ny)
    x = 14_000_000.0 + 10.0 * np.arange(nx)

    data_vars = {}
    for i, band in enumerate(S2_BANDS):
        dn = rng.integers(500, 5000, size=(nt, ny, nx)).astype(np.int16)
        da = xr.DataArray(dn, dims=('time', 'y', 'x'),
                          coords={'time': time, 'y': y, 'x': x})
        da.attrs['nodata'] = NODATA
        data_vars[band] = da
    return xr.Dataset(data_vars)


def synthetic_paddocks_gpkg(path, ds):
    """Two square paddocks on the grid of ``ds``, written as a GeoPackage
    in EPSG:6933. Returns (path, pixel-index slices per paddock)."""
    import geopandas as gpd
    from shapely.geometry import box

    x, y = ds.x.values, ds.y.values
    half = 5.0  # half a pixel: cell centres to cell edges

    # Paddock 1: pixel block rows 0-3, cols 0-3. Paddock 2: rows 4-7, cols 4-7.
    p1 = box(x[0] - half, y[3] - half, x[3] + half, y[0] + half)
    p2 = box(x[4] - half, y[7] - half, x[7] + half, y[4] + half)
    gdf = gpd.GeoDataFrame(
        {'paddock': [1, 2]}, geometry=[p1, p2], crs='EPSG:6933')
    gdf.to_file(path, driver='GPKG')
    slices = {1: (slice(0, 4), slice(0, 4)), 2: (slice(4, 8), slice(4, 8))}
    return str(path), slices


def synthetic_yearly_ndvi(n_paddocks=2, n_obs=36, year=2022):
    """One year of smooth single-peak NDVI on (paddock, time), shaped like
    the output of make_yearly_paddock_time_series: a ``doy`` coordinate
    and a ``spatial_ref`` scalar coordinate."""
    time = pd.date_range(f'{year}-01-05', periods=n_obs, freq='10D')
    doy = time.dayofyear.to_numpy()
    # Sinusoid peaking mid-year, base 0.2, amplitude 0.5; tiny per-paddock offset.
    curve = 0.2 + 0.5 * np.sin(np.pi * (doy - doy.min()) / (doy.max() - doy.min())) ** 2
    ndvi = np.stack([curve + 0.01 * p for p in range(n_paddocks)])
    ds = xr.Dataset(
        {'NDVI': (('paddock', 'time'), ndvi)},
        coords={
            'paddock': [str(p + 1) for p in range(n_paddocks)],
            'time': time,
            'doy': ('time', doy),
            'spatial_ref': np.int32(6933),
        },
    )
    ds.attrs['year'] = year
    return ds
