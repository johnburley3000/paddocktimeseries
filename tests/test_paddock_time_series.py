"""Per-paddock median aggregation: pure math and the full synthetic path.

``make_paddock_time_series`` is the pivot from pixel-space to
paddock-space; these tests drive it with a synthetic int16 cube and two
synthetic square paddocks, so the rasterisation, nodata-sentinel
exclusion, and median math are all verified with known answers.
"""

import numpy as np
import xarray as xr

from PaddockTS.Phenology.make_paddock_time_series import (
    _band_medians, make_paddock_time_series)

from conftest import NODATA, synthetic_s2, synthetic_paddocks_gpkg


def test_band_medians_known_values():
    # 2 timesteps over a flat 2x2 grid -> flattened pixel indices 0..3.
    band = np.array([
        [[1.0, 2.0], [3.0, 4.0]],
        [[10.0, 20.0], [30.0, 40.0]],
    ])
    idx = [np.array([0, 1]), np.array([2, 3])]
    out = _band_medians(band, idx)
    np.testing.assert_allclose(out, [[1.5, 15.0], [3.5, 35.0]])


def test_band_medians_ignores_nan():
    band = np.array([[[1.0, np.nan], [np.nan, np.nan]]])
    idx = [np.array([0, 1]), np.array([2, 3])]
    out = _band_medians(band, idx)
    assert out[0, 0] == 1.0          # NaN pixel excluded from the median
    assert np.isnan(out[1, 0])       # all-NaN paddock -> NaN, no crash


def test_band_medians_empty_paddock_is_nan():
    band = np.zeros((1, 2, 2))
    out = _band_medians(band, [np.array([], dtype=int)])
    assert np.isnan(out[0, 0])


def test_make_paddock_time_series_synthetic(tmp_troi, tmp_path):
    ds = synthetic_s2()
    gpkg, slices = synthetic_paddocks_gpkg(tmp_path / 'paddocks.gpkg', ds)

    # Paddock 1's red block gets a known constant; put nodata sentinel in
    # half of it at t=0 — the median must not move.
    red = ds['nbart_red'].values
    red[:, slices[1][0], slices[1][1]] = 2000
    red[0, 0:2, 0:4] = NODATA
    ds['nbart_red'].values[:] = red

    result = make_paddock_time_series(tmp_troi, ds_sentinel2=ds,
                                      paddocks_filepath=gpkg)

    assert sorted(result.paddock.values.tolist()) == ['1', '2']
    assert result.sizes['time'] == ds.sizes['time']

    # Median over paddock 1's red block is 2000 at every timestep, and the
    # -999 sentinel pixels at t=0 were excluded rather than averaged in.
    red_p1 = result['nbart_red'].sel(paddock='1').values
    np.testing.assert_allclose(red_p1, 2000.0)

    # Spectral indices got attached per paddock.
    for name in ('NDVI', 'CFI', 'NIRv', 'NDTI', 'CAI'):
        assert name in result.data_vars

    # The zarr was persisted with its _SUCCESS marker.
    zarr_path = f'{tmp_troi.tmp_dir}/paddocks_timeseries.zarr'
    from PaddockTS.utils import check_if_valid_zarr_exists
    assert check_if_valid_zarr_exists(zarr_path)


def test_paddock_labels_survive(tmp_troi, tmp_path):
    """String paddock labels come through as coordinates, not integers."""
    import geopandas as gpd

    ds = synthetic_s2()
    gpkg, _ = synthetic_paddocks_gpkg(tmp_path / 'named.gpkg', ds)
    gdf = gpd.read_file(gpkg)
    gdf['paddock'] = ['North', 'South']
    gdf.to_file(gpkg, driver='GPKG')

    result = make_paddock_time_series(tmp_troi, ds_sentinel2=ds,
                                      paddocks_filepath=gpkg)
    assert sorted(result.paddock.values.tolist()) == ['North', 'South']
