"""Spectral unmixing of Sentinel-2 reflectance into bg / pv / npv fractions.

The model is a small TFLite MLP adapted from
`fractionalcover3 <https://github.com/jrsrp/fractionalcover3>`_ by
Robert Denham (MIT-licensed; see
``PaddockTS/LICENSES/fractionalcover3.LICENSE``). Four model variants
ship with the package, indexed ``n=1..4`` from least to most complex;
``n=4`` is the default and most accurate.

Output bands:

- ``bg`` — bare ground fraction
- ``pv`` — green (photosynthetic) vegetation fraction
- ``npv`` — non-green (non-photosynthetic) vegetation fraction

Fractions are produced per-pixel per-timestep and persisted to
``Paths(troi).fractional_cover`` as Zarr v2. Input reflectance comes
from the machine-wide pysentinel2 cube (cloud-masked, on read).
"""

import os
import warnings

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
warnings.filterwarnings('ignore', module='tensorflow')
warnings.filterwarnings('ignore', module='keras')

import numpy as np
import xarray as xr
from os import makedirs
from os.path import exists
from datetime import datetime
from xarray import Dataset
from troi import Troi
from PaddockTS.paths import Paths
from PaddockTS.FractionalCover.check_if_valid_fractional_cover_exists import check_if_valid_fractional_cover_exists


BANDS = ['nbart_blue', 'nbart_green', 'nbart_red', 'nbart_nir_1', 'nbart_swir_2', 'nbart_swir_3']


def compute_fractional_cover(troi: Troi, ds_sentinel2=None, model_n: int = 4, correction: bool = False):
    """Run the TFLite unmixing model over every Sentinel-2 timestep.

    Stacks the six Sentinel-2 SR bands into a ``(time, band, y, x)``
    tensor, scales reflectance, and invokes the chosen model variant
    once per timestep. The result is written to
    ``Paths(troi).fractional_cover`` and returned as an xarray Dataset
    with ``bg``, ``pv``, ``npv`` data variables on dims
    ``(time, y, x)``.

    Args:
        troi: The :class:`troi.Troi`.
        ds_sentinel2: Optional in-memory Sentinel-2 dataset. If ``None``,
            the cloud-masked window is read from the machine-wide
            pysentinel2 cube (downloading only what's missing). Must
            contain the six bands in :data:`BANDS`.
        model_n: Which bundled model variant to use (``1..4``). Higher
            ``n`` is more accurate but slower; ``n=4`` is the default.
        correction: If ``True``, apply per-band sensor calibration
            factors (gains and offsets fitted in the upstream
            fractionalcover3 work) instead of the simple ``* 0.0001``
            DN-to-reflectance scaling. Use only when your inputs match
            the calibration assumptions of the original model.

    Returns:
        xarray.Dataset: Dataset with variables ``bg``, ``pv``, ``npv``
        on dims ``(time, y, x)``. Also persisted to
        ``Paths(troi).fractional_cover``.
    """
    from PaddockTS.FractionalCover._unmix import unmix_fractional_cover, get_model

    fractional_cover_path = Paths(troi).fractional_cover
    if check_if_valid_fractional_cover_exists(fractional_cover_path):
        try:
            return xr.open_zarr(fractional_cover_path, chunks=None, decode_coords='all')
        except Exception as e:
            print(f'Fractional-cover cache at {fractional_cover_path} unreadable ({e}); recomputing')

    if ds_sentinel2 is None:
        from pysentinel2.cube import Cube
        ds = Cube(config=troi.config).get_ds_troi(troi, clean=True)
    else:
        ds = ds_sentinel2

    if correction:
        factors = (np.array([0.9551, 1.0582, 0.9871, 1.0187, 0.9528, 0.9688]) +
                   np.array([-0.0022, 0.0031, 0.0064, 0.012, 0.0079, -0.0042])
                   ).astype(np.float32)[:, np.newaxis, np.newaxis]
    else:
        factors = np.float32(0.0001)

    # Stream in small time batches, appending each to the zarr as it's
    # unmixed. Materialising the whole window at once — six bands x every
    # timestep as float — needs >10 GB for a multi-year troi and OOMs
    # 8 GB machines; a 32-frame batch stays around 200 MB regardless of
    # the time range. The model is loaded once, not per timestep.
    #
    # Unmixing runs serially on purpose: 4 threads with per-thread
    # interpreters measured 615.2 s vs 618.3 s serial on an 8-year window
    # (340% CPU for zero wall gain — the matmul is memory-bandwidth
    # bound). If this step ever needs to be faster, batch several frames
    # into one Invoke rather than adding threads.
    model = get_model(n=model_n)
    makedirs(os.path.dirname(fractional_cover_path), exist_ok=True)
    timestamp = datetime.utcnow().isoformat() + 'Z'

    n_time = ds.sizes['time']
    batch = 32
    for t0 in range(0, n_time, batch):
        sub = ds.isel(time=slice(t0, t0 + batch))
        inref = np.stack([sub[b].values for b in BANDS], axis=1).astype(np.float32)
        # Cleaned cube bands are int16 with masked pixels at the nodata
        # sentinel; convert to NaN so the unmixing propagates missingness
        # instead of ingesting -999 as reflectance.
        for bi, b in enumerate(BANDS):
            nodata = ds[b].attrs.get('nodata')
            if nodata is not None:
                inref[:, bi][inref[:, bi] == float(nodata)] = np.nan
        inref[inref == 0] = np.nan
        inref *= factors
        fractions = np.empty((inref.shape[0], 3, inref.shape[2], inref.shape[3]),
                             dtype=np.float32)
        for i in range(inref.shape[0]):
            fractions[i] = unmix_fractional_cover(inref[i], fc_model=model)

        coords = {'time': sub.time, 'y': ds.y, 'x': ds.x}
        batch_ds = xr.Dataset({
            'bg': xr.DataArray(fractions[:, 0], dims=['time', 'y', 'x'], coords=coords),
            'pv': xr.DataArray(fractions[:, 1], dims=['time', 'y', 'x'], coords=coords),
            'npv': xr.DataArray(fractions[:, 2], dims=['time', 'y', 'x'], coords=coords),
        })
        if t0 == 0:
            batch_ds = batch_ds.assign_attrs(fractional_cover_computed_at=timestamp)
            batch_ds.to_zarr(fractional_cover_path, mode='w', zarr_format=2,
                             encoding={v: {'chunks': (1, ds.sizes['y'], ds.sizes['x'])}
                                       for v in ('bg', 'pv', 'npv')})
        else:
            batch_ds.to_zarr(fractional_cover_path, append_dim='time', zarr_format=2)

    # Touch _SUCCESS *after* the zarr write completes; its presence is what
    # the next call uses as the cache-validity check.
    with open(f'{fractional_cover_path}/_SUCCESS', 'w') as f:
        f.write(timestamp)
    # Re-open from disk: a lazy, zarr-backed view rather than the in-RAM
    # batches — downstream consumers slice what they need.
    return xr.open_zarr(fractional_cover_path, chunks=None, decode_coords='all')


def _temp_troi():
    import tempfile
    from datetime import date
    from troi import Config
    tmpdir = tempfile.mkdtemp(prefix='paddockts_fc_test_')
    cfg = Config(out_dir=tmpdir, tmp_dir=tmpdir)
    return Troi(
        bbox=[148.36265, -33.52606, 148.38265, -33.50606],
        start=date(2024, 1, 1), end=date(2024, 1, 21),
        stub=f'fc_{os.path.basename(tmpdir)}', config=cfg,
    )


def test_compute_writes_zarr_and_marker():
    """First call computes, writes fractional_cover.zarr, and touches _SUCCESS."""
    q = _temp_troi()
    ds = compute_fractional_cover(q)
    fc = Paths(q).fractional_cover
    if not exists(fc):
        return False
    if not exists(f'{fc}/_SUCCESS'):
        return False
    return all(name in ds.data_vars for name in ('bg', 'pv', 'npv'))


def test_repeated_call_uses_cache():
    """Second call with same troi reuses the zarr (no rewrite)."""
    q = _temp_troi()
    compute_fractional_cover(q)
    fc = Paths(q).fractional_cover
    mtime_before = os.path.getmtime(fc)
    compute_fractional_cover(q)
    mtime_after = os.path.getmtime(fc)
    return mtime_before == mtime_after


def test_missing_marker_triggers_recompute():
    """A cache with the zarr present but no _SUCCESS file is recomputed."""
    q = _temp_troi()
    compute_fractional_cover(q)
    fc = Paths(q).fractional_cover
    marker = f'{fc}/_SUCCESS'
    os.remove(marker)
    mtime_before = os.path.getmtime(fc)
    compute_fractional_cover(q)
    mtime_after = os.path.getmtime(fc)
    return exists(marker) and mtime_after > mtime_before


def test():
    return all([
        test_compute_writes_zarr_and_marker(),
        test_repeated_call_uses_cache(),
        test_missing_marker_triggers_recompute(),
    ])


if __name__ == '__main__':
    print(test())
