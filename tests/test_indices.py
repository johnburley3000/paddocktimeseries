"""Spectral-index math on hand-computed reflectance values.

The indices are on-read derivatives from pysentinel2 (the pipeline
requests them via ``Cube.get_ds_troi(..., indices=...)`` and
``make_paddock_time_series`` computes them transiently per band).
"""

import numpy as np
import pytest
import xarray as xr

from pysentinel2.derive import INDICES, add_indices, ndvi, ndti, cai

from conftest import NODATA


def _one_pixel_ds(nir=6000, red=2000, green=1500, blue=1000,
                  swir2=3000, swir3=1000):
    """A 1x1x1 dataset with the given DN values and nodata attrs."""
    values = {'nbart_nir_1': nir, 'nbart_red': red, 'nbart_green': green,
              'nbart_blue': blue, 'nbart_swir_2': swir2, 'nbart_swir_3': swir3}
    data = {}
    for band, dn in values.items():
        da = xr.DataArray(np.full((1, 1, 1), dn, dtype=np.int16),
                          dims=('time', 'y', 'x'))
        da.attrs['nodata'] = NODATA
        data[band] = da
    return xr.Dataset(data)


def test_ndvi_hand_computed():
    # NDVI = (0.6 - 0.2) / (0.6 + 0.2) = 0.5
    ds = _one_pixel_ds(nir=6000, red=2000)
    assert ndvi(ds)[0, 0, 0] == pytest.approx(0.5)


def test_ndti_hand_computed():
    # NDTI = (0.3 - 0.1) / (0.3 + 0.1) = 0.5
    ds = _one_pixel_ds(swir2=3000, swir3=1000)
    assert ndti(ds)[0, 0, 0] == pytest.approx(0.5)


def test_cai_hand_computed():
    # CAI = 0.5 * (0.3 + 0.1) - 0.6 = -0.4
    ds = _one_pixel_ds(nir=6000, swir2=3000, swir3=1000)
    assert cai(ds)[0, 0, 0] == pytest.approx(-0.4)


def test_nodata_and_zero_become_nan():
    for red_dn in (0, NODATA):
        ds = _one_pixel_ds(red=red_dn)
        assert np.isnan(ndvi(ds)[0, 0, 0])


def test_add_indices_attaches_all_five():
    ds = _one_pixel_ds()
    out = add_indices(ds, tuple(INDICES))
    for name in INDICES:
        assert name in out.data_vars
        assert out[name].dims == ('time', 'y', 'x')


def test_add_indices_rejects_unknown():
    with pytest.raises(ValueError):
        add_indices(_one_pixel_ds(), ('NDVI', 'BOGUS'))
