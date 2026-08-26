"""Aggregate per-pixel Sentinel-2 data into per-paddock medians.

Rasterises the paddock polygons onto the Sentinel-2 grid, then for every
band in the dataset computes the per-paddock median across pixels at
each timestep. The result is the central time-series dataset that
downstream stages (yearly split, smoothing, phenology, plotting) consume.
"""

import warnings
import numpy as np
import xarray as xr
from borevitz_lab.query import Query

def _band_medians(band_array, paddock_pixel_idx):
    """Per-paddock NaN-aware median across pixels, for every timestep.

    band_array:        np.ndarray (time, y, x)
    paddock_pixel_idx: list of 1D index arrays into the flattened (y*x) grid,
        one per paddock in output order. An empty array yields an all-NaN row.

    Returns (n_paddocks, time) float64. Vectorised over time: each paddock's
    median is computed for all timesteps in one ``np.nanmedian(..., axis=1)``
    call rather than looping per timestep — same numbers as the old per-pixel
    loop, no Python-level T loop.
    """
    T = band_array.shape[0]
    flat = band_array.reshape(T, -1)
    out  = np.full((len(paddock_pixel_idx), T), np.nan, dtype=np.float64)

    with warnings.catch_warnings():
        # All-NaN pixel set at a timestep → nanmedian returns NaN (what we
        # want) but warns; the old code guarded this per timestep instead.
        warnings.filterwarnings('ignore', r'All-NaN slice encountered', RuntimeWarning)
        for i, idx in enumerate(paddock_pixel_idx):
            if idx.size:
                out[i] = np.nanmedian(flat[:, idx], axis=1)

    return out

def make_paddock_time_series(query: Query, ds_sentinel2=None, paddocks_filepath=None, crs="epsg:6933"):
    """Compute per-paddock medians for every band at every timestep.

    Steps:

    1. Compute the five spectral indices (NDVI, CFI, NIRv, NDTI, CAI)
       and add them to the input dataset.
    2. Rasterise paddock polygons to integer IDs aligned with the
       Sentinel-2 grid.
    3. For each band, in parallel across processes, compute the
       per-paddock NaN-aware median across pixels at every timestep.
    4. Stitch results back into an xarray Dataset on dims
       ``(paddock, time)`` and persist as Zarr v2 to
       ``{paddocks_filepath stem}_timeseries.zarr``.

    Args:
        query: The :class:`borevitz_lab.query.Query`.
        ds_sentinel2: Optional in-memory Sentinel-2 dataset (with the five
            indices already added, or they will be computed). If ``None``,
            the cloud-masked window with indices comes from the
            pysentinel2 cube.
        paddocks_filepath: Path to a GeoPackage (.gpkg) containing paddock
            polygons (must include a ``paddock`` column for IDs). If
            ``None``, defaults to ``Paths(query).sam_paddocks`` (loaded or
            generated via :func:`PaddockTS.PaddockSegmentation.get_paddocks`).
        crs: Equal-area CRS to write onto the dataset for
            georeferencing the rasterised mask. Defaults to EPSG:6933
            (WGS84 / NSIDC EASE-Grid 2.0 Global).

    Returns:
        xarray.Dataset: Per-paddock medians on dims ``(paddock, time)``
        with one data variable per Sentinel-2 band and per spectral
        index. Also persisted to ``{paddocks_filepath stem}_timeseries.zarr``.
    """
    import rasterio.features
    from affine import Affine
    import pandas as pd
    from datetime import datetime
    from os import makedirs
    from os.path import exists
    from pathlib import Path
    import geopandas as gpd
    from pysentinel2.derive import INDICES

    if ds_sentinel2 is None:
        from pysentinel2.cube import Cube
        ds_sentinel2 = Cube(config=query.config).get_ds_query(query)
    # Indices are NOT materialised onto the dataset: five float32
    # full-window arrays are ~3.5 GB for a multi-year query. Each index
    # is computed transiently in the median loop below and freed.

    if paddocks_filepath is None:
        from PaddockTS.paths import Paths
        paddocks_filepath = Paths(query).sam_paddocks
        if not exists(paddocks_filepath):
            from PaddockTS.PaddockSegmentation.get_paddocks import get_paddocks
            get_paddocks(query)

    # Use load_user_paddocks to ensure 'paddock' column exists
    from PaddockTS.utils import load_user_paddocks
    paddocks = load_user_paddocks(paddocks_filepath)

    ds = ds_sentinel2

    # 1) Ensure CRS is written
    ds = ds.rio.write_crs(crs, inplace=False)

    # Reproject paddocks to match the dataset CRS
    if paddocks.crs != ds.rio.crs:
        paddocks = paddocks.to_crs(ds.rio.crs)

    pol = paddocks
    transform = ds.rio.transform()
    H, W = ds.rio.height, ds.rio.width

    # 2) Build a mapping from paddock label (string) -> integer ID for rasterization
    #    This works whether pol.paddock is int, string, or mixed.
    paddock_labels = pol["paddock"].astype(str)
    # unique labels in a stable order
    unique_labels = pd.Index(paddock_labels.unique().tolist())
    int_ids = np.arange(1, len(unique_labels) + 1, dtype=np.int32)  # start at 1, 0 = background
    label_to_int = dict(zip(unique_labels, int_ids))

    # integer paddock IDs for each polygon row
    poly_ids = paddock_labels.map(label_to_int).to_numpy(dtype=np.int32)

    # 3) Rasterize once using integer IDs
    shapes = [(geom, int(pid)) for geom, pid in zip(pol.geometry, poly_ids)]
    mask = rasterio.features.rasterize(
        shapes,
        out_shape=(H, W),
        transform=transform,
        fill=0,              # background
        dtype=np.int32,
    )
    mask_flat   = mask.ravel()

    # These are the IDs we’ll compute medians for, and their corresponding labels
    paddock_ids  = int_ids.tolist()             # integer IDs in order
    paddock_strs = unique_labels.astype(str).tolist()  # original labels as strings

    # 4) Bands are converted one at a time inside the median loop below —
    #    the cleaned cube keeps reflectance int16 with a nodata sentinel,
    #    and converting every band to float at once is exactly the
    #    multi-GB footprint the int16 pipeline exists to avoid.
    def _band_as_float(var):
        vals = ds[var].values
        if not np.issubdtype(vals.dtype, np.integer):
            return vals
        nodata = ds[var].attrs.get('nodata')
        fvals = vals.astype(np.float32)
        if nodata is not None:
            fvals[vals == nodata] = np.nan
        fvals[fvals == 0] = np.nan
        return fvals

    # Precompute the flat pixel indices for each paddock once — shared across
    # every band, so the mask comparison isn't repeated per band.
    paddock_pixel_idx = [np.flatnonzero(mask_flat == pid) for pid in paddock_ids]

    # 5) Per-paddock NaN-aware median for each band, in-process. The previous
    #    ProcessPoolExecutor deadlocked when this stage ran inside the
    #    get_outputs Sentinel-2 worker thread: the spawned subprocesses
    #    inherited the dashboard's redirected fd 2, and the result-queue feeder
    #    thread blocked on a full pipe so fut.result() never returned. The
    #    median is now vectorised over time, so a plain loop is fast enough and
    #    spawns nothing.
    results = {
        var: _band_medians(_band_as_float(var), paddock_pixel_idx)
        for var in ds.data_vars
    }
    # Spectral indices, one transient float32 array at a time.
    for name, fn in INDICES.items():
        if name not in results:
            results[name] = _band_medians(fn(ds), paddock_pixel_idx)

    # Fractional cover per-paddock medians, from the per-query FC zarr
    # (computed earlier in the pipeline from this same cleaned window, so
    # the time axes match; guarded in case a caller mixes windows). Was
    # lost in the store refactor — the manuscript's drought-exposure
    # analysis reads ``bg`` from the smoothed series.
    from PaddockTS.paths import Paths as _Paths
    fc_path = _Paths(query).fractional_cover
    if exists(fc_path):
        fc = xr.open_zarr(fc_path, chunks=None, decode_coords='all')
        if (fc.time.size == ds.sizes['time']
                and fc.sizes['y'] == ds.sizes['y']
                and fc.sizes['x'] == ds.sizes['x']):
            for name in ('bg', 'pv', 'npv'):
                if name in fc.data_vars:
                    results[name] = _band_medians(fc[name].values, paddock_pixel_idx)
        else:
            print(f'fractional cover zarr has {fc.time.size} frames vs window '
                  f'{ds.sizes["time"]} — skipping FC columns in the time series')

    # 6) Stitch back into xarray
    coords = {
        "paddock": paddock_strs,              # original paddock labels (strings)
        "time": ds.coords["time"],
        "spatial_ref": np.int32(ds.rio.crs.to_epsg()),
    }
    data_vars = {
        var: (("paddock", "time"), results[var])
        for var in results
    }
    result = xr.Dataset(data_vars, coords=coords)

    paddocks_path = Path(paddocks_filepath)
    zarr_path = f'{query.tmp_dir}/{paddocks_path.stem}_timeseries.zarr'
    makedirs(query.tmp_dir, exist_ok=True)
    timestamp = datetime.utcnow().isoformat() + 'Z'
    result = result.assign_attrs(paddock_timeseries_computed_at=timestamp)
    result.to_zarr(zarr_path, mode='w', zarr_format=2)
    # _SUCCESS marker for cache-validity check (matches the contract used by
    # download_sentinel2 / compute_indices / compute_fractional_cover).
    with open(f'{zarr_path}/_SUCCESS', 'w') as f:
        f.write(timestamp)
    print(f'Saved to {zarr_path}')
    return result


def test():
    from PaddockTS.utils import get_example_query

    query = get_example_query()
    result = make_paddock_time_series(query)
    print(result)
    for var in result.data_vars:
        print(f'{var}: {float(result[var].mean()):.3f}')


if __name__ == '__main__':
    test()
