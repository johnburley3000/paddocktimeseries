"""Topography figure: elevation, flow accumulation, aspect, and slope.

Asks the machine-wide pycopdem store for the elevation window and its
derivatives -- computed there on the native 30 m grid, on a window
buffered by a kilometre so edge pixels see their real neighbours, with
a Gaussian smoother applied before flow analysis (sharp DEMs give flow
algorithms striped artefacts):

- elevation (m)
- D8 flow accumulation (cells)
- aspect (degrees clockwise from north)
- slope (degrees)
- topographic wetness index (TWI; computed but not plotted)

The four panels are reprojected onto the Sentinel-2 grid for easy
overlay against other PaddockTS outputs (display only; the store never
resamples), then to EPSG:4326 for plotting, and saved as a single PNG.
"""

from matplotlib import pyplot as plt
from matplotlib import colors
import numpy as np
import xarray as xr
from rasterio.enums import Resampling
from troi import Troi
from os import makedirs


def terrain_tiles_plot(troi: Troi, ds_sentinel2=None, sigma: int = 10):
    """Plot a 2 × 2 panel of elevation, flow accumulation, aspect, and slope.

    Args:
        troi: The :class:`troi.Troi`. Output is written to
            ``{troi.out_dir}/{troi.stub}_topography.png``.
        ds_sentinel2: Optional in-memory Sentinel-2 dataset, used as the
            spatial reference grid that the terrain tiles are
            reprojected onto. If ``None``, the cloud-masked window is
            read from the pysentinel2 cube.
        sigma: Standard deviation of the Gaussian smoother applied to
            the DEM before flow analysis, in pixels. Larger values
            produce smoother, less-striped flow fields at the cost of
            losing fine drainage detail. Default 10.

    Returns:
        str: Filesystem path of the generated PNG.
    """
    makedirs(troi.out_dir, exist_ok=True)

    # Native 30 m elevation + derivatives from the store (buffered and
    # smoothed there), as lat/lon DataArrays with a CRS for reproject_match.
    import rioxarray  # noqa: F401 — registers the .rio accessor
    from pycopdem.store import Store as _DemStore
    native = _DemStore(config=troi.config).get_ds_troi(
        troi, derivatives=('slope', 'aspect', 'accumulation', 'twi'),
        buffer_m=1000, smooth_sigma=sigma)
    native = native.rename({'lat': 'y', 'lon': 'x'}).rio.write_crs('EPSG:4326')

    # Reference grid: the S2 pixel grid, reconstructed deterministically
    # from the troi bbox on pysentinel2's fixed global grid. No cube
    # read — loading the cleaned window here materialises the full time
    # range a second time, concurrently with the S2 worker thread, which
    # OOMs 8 GB machines.
    if ds_sentinel2 is None:
        from odc.geo.xr import xr_zeros
        from pysentinel2 import grid as s2grid
        # Tight (pixel-snapped) window, matching what Cube.get_ds delivers
        # to every other product — chunk-snapped would pad the topography
        # ~3.6x beyond the bbox the rest of the report covers.
        ds_ref = xr_zeros(
            s2grid.geobox_for_window(s2grid.tight_window_for_bbox(troi.bbox)),
            dtype='uint8')
    else:
        ds_ref = ds_sentinel2.isel(time=0) if 'time' in ds_sentinel2.dims else ds_sentinel2

    # Put each layer on the Sentinel-2 grid for display.
    resampling = {
        'elevation': Resampling.average,
        'accumulation': Resampling.max,
        'aspect': Resampling.nearest,
        'slope': Resampling.average,
        'twi': Resampling.average,
    }
    ds = xr.Dataset({
        name: native[name].rio.reproject_match(ds_ref, resampling=resamp)
        for name, resamp in resampling.items()
    }).rename({'elevation': 'terrain'})

    # Clip 1 cell border (edge artifacts from reprojection)
    ds = ds.isel(y=slice(1, -1), x=slice(1, -1))

    # Reproject to EPSG:4326 for plotting
    ds_4326 = ds.rio.reproject('EPSG:4326')
    left, bottom, right, top = ds_4326.rio.bounds()
    extent = (left, right, bottom, top)

    dem_plot = ds_4326['terrain'].values
    acc_plot = ds_4326['accumulation'].values
    slope_plot = ds_4326['slope'].values
    aspect_plot = ds_4326['aspect'].values

    # Plot
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    (ax1, ax2), (ax3, ax4) = axes

    # Elevation
    im = ax1.imshow(dem_plot, cmap='terrain', interpolation='bilinear', extent=extent, origin='upper')
    ax1.set_title('Elevation')
    fig.colorbar(im, ax=ax1, label='m')
    levels = np.arange(np.floor(np.nanmin(dem_plot)), np.ceil(np.nanmax(dem_plot)), 10)
    if len(levels) > 1:
        contours = ax1.contour(dem_plot, levels=levels, colors='black',
                               linewidths=0.5, alpha=0.5, extent=extent, origin='upper')
        ax1.clabel(contours, inline=True, fontsize=8, fmt='%1.0f')

    # Accumulation
    acc_safe = np.where(acc_plot > 0, acc_plot, 1)
    im = ax2.imshow(acc_safe, cmap='cubehelix', norm=colors.LogNorm(1, max(np.nanmax(acc_plot), 2)),
                    interpolation='bilinear', extent=extent, origin='upper')
    ax2.set_title('Flow Accumulation')
    fig.colorbar(im, ax=ax2, label='upstream cells')

    # Aspect (degrees clockwise from north; hsv wraps so N and N meet)
    im = ax3.imshow(aspect_plot, cmap='hsv', vmin=0, vmax=360, extent=extent, origin='upper')
    ax3.set_title('Aspect')
    cbar = fig.colorbar(im, ax=ax3)
    cbar.set_ticks([0, 90, 180, 270, 360])
    cbar.set_ticklabels(['N', 'E', 'S', 'W', 'N'])

    # Slope
    im = ax4.imshow(slope_plot, cmap='Purples', extent=extent, origin='upper')
    ax4.set_title('Slope')
    fig.colorbar(im, ax=ax4, label='degrees')

    for ax in [ax1, ax2, ax3, ax4]:
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')

    plt.tight_layout()
    out_path = f'{troi.out_dir}/{troi.stub}_topography.png'
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f'  saved: {out_path}')
    return out_path


def test():
    from PaddockTS.utils import get_example_troi
    q = get_example_troi()
    terrain_tiles_plot(q)


if __name__ == '__main__':
    test()
