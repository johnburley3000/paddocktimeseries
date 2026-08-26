"""Multi-year calendar of true-colour Sentinel-2 thumbnails per paddock.

Produces one page per paddock (largest area first), so each paddock
starts on a fresh page and can be compared across years. Rows are the
years in the query; columns are 48 evenly-spaced slots across the year
(4 per month). Each cell shows the Sentinel-2 RGB thumbnail of that
paddock at the observation closest to the slot's day-of-year, with
non-paddock pixels masked black.

Thumbnails are contrast-stretched (2–98 percentile per scene). Cells
whose nearest observation is mostly cloud-masked are filled with a
time-weighted blend of the nearest clear observations either side and
outlined in red; every page carries a legend marking them as
interpolated.

Each page is a matplotlib :class:`~matplotlib.figure.Figure` so that
when it's written into a PDF report by :mod:`PaddockTS.Plotting.make_pdf`,
the title / month / year labels remain *vector text* — readable at any
zoom, immune to the rasterized-PNG-embed shrink that capped text size
at ~13 pt in the previous PIL-composited version.

Public entry points:

- :func:`calendar_plot` — saves one PNG per paddock (matplotlib raster
  output) under ``query.out_dir``.
- :func:`iter_calendar_figures` — generator yielding ``(paddock_id,
  fig)`` tuples without writing anything to disk. Used by
  :mod:`PaddockTS.Plotting.make_pdf` to embed pages as vector-text PDF
  pages.
"""

from __future__ import annotations

import os
import glob
from pathlib import Path
from typing import Iterator

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from rasterio.features import rasterize

from borevitz_lab.query import Query
from PaddockTS.paths import Paths


# --- thumbnail prep --------------------------------------------------------

# A calendar cell is considered usable when at least _VALID_FRAC_THRESH of
# the paddock's pixels survived cloud masking in the chosen observation;
# below it the whole cell is replaced by temporal interpolation. Usable
# cells below _CLEAR_FULL_THRESH keep their clear pixels but have the
# masked ones gap-filled from the same interpolation. Both cases are
# outlined (see _build_paddock_figure).
_VALID_FRAC_THRESH = 0.6
_CLEAR_FULL_THRESH = 0.98
_INTERP_COLOR = 'red'


def _to_rgb(ds, time_idx):
    r = ds['nbart_red'].isel(time=time_idx).values.astype(np.float32)
    g = ds['nbart_green'].isel(time=time_idx).values.astype(np.float32)
    b = ds['nbart_blue'].isel(time=time_idx).values.astype(np.float32)
    rgb = np.stack([r, g, b], axis=-1)
    rgb[rgb == 0] = np.nan
    rgb /= 10000.0
    # Contrast: 2–98 percentile stretch over the scene's valid pixels,
    # computed jointly across bands so the hue is preserved. Falls back
    # to the old fixed gain when the scene is (near-)fully masked.
    lo, hi = np.nanpercentile(rgb, [2, 98])
    if np.isfinite(lo) and np.isfinite(hi) and hi > lo:
        rgb = (rgb - lo) / (hi - lo)
    else:
        rgb = rgb * 3
    rgb = np.clip(rgb, 0, 1)
    # NaNs (cloud-masked pixels) are preserved — _crop_all derives the
    # per-thumbnail validity mask from them before blacking them out.
    return rgb


_CALENDAR_BANDS = ('nbart_red', 'nbart_green', 'nbart_blue')


def _iter_year_datasets(query: Query, ds_sentinel2):
    """Yield ``(year, cleaned RGB dataset)`` one year at a time.

    Materialising the full query window at once is a memory hazard: an
    8-year, 11-band window is several GB after cleaning promotes to
    float, which OOM-kills 8 GB machines. Reading per year and only the
    RGB bands the calendar uses bounds the peak to a few hundred MB.
    A caller-supplied in-memory dataset is honoured and split instead.
    """
    if ds_sentinel2 is not None:
        years = np.unique(ds_sentinel2.time.dt.year.values)
        for year in years:
            year_mask = ds_sentinel2.time.dt.year.values == int(year)
            ds_year = ds_sentinel2.isel(time=year_mask)
            if ds_year.sizes['time']:
                yield int(year), ds_year
        return

    from datetime import date as _date
    from pysentinel2.cube import Cube
    cube = Cube(config=query.config)
    for year in range(query.start.year, query.end.year + 1):
        y0 = max(query.start, _date(year, 1, 1))
        y1 = min(query.end, _date(year, 12, 31))
        ds_year = cube.get_ds(query.bbox, y0, y1, clean=True, bands=_CALENDAR_BANDS)
        if ds_year.sizes['time']:
            yield int(year), ds_year


def _prepare_thumbnails(query: Query, paddocks_filepath: str,
                        ds_sentinel2, thumb_size: int):
    """Compute the per-paddock thumbnails once, reused across all pages.

    Returns
    -------
    paddocks_sorted : GeoDataFrame
        Paddocks sorted largest-area first.
    paddock_ids : list[int]
        Paddock IDs in the same order as ``paddocks_sorted``.
    years_data : dict[int, tuple[dict, dict]]
        ``{year: (obs_thumbs, slot_specs)}``. ``obs_thumbs`` is
        ``{obs_idx: {paddock_id: (rgb_thumb, valid_thumb)}}`` — the uint8
        thumbnail plus its boolean clear-pixel mask. ``slot_specs`` is
        ``{paddock_id: [spec] * 48}`` where each spec is one of
        ``('direct', obs_idx)`` — fully clear; ``('partial', obs_idx,
        prev_idx, next_idx, w)`` — mostly clear, masked pixels gap-filled
        from the ``w``-weighted blend of the neighbours; or ``('interp',
        prev_idx, next_idx, w)`` — mostly masked, whole cell replaced by
        the blend (``next_idx`` is ``None`` when only one side has a
        clear observation that year).
    """
    import itertools
    import rioxarray  # noqa: F401
    from PIL import Image
    from PaddockTS.utils import load_user_paddocks

    # Years stream through one at a time (see _iter_year_datasets); the
    # first year supplies the grid, which is identical across years.
    year_iter = _iter_year_datasets(query, ds_sentinel2)
    first = next(year_iter, None)
    if first is None:
        raise ValueError('No Sentinel-2 observations in the query window.')
    ref = first[1]

    paddocks = load_user_paddocks(paddocks_filepath)
    ds_crs = ref.rio.crs
    if paddocks.crs != ds_crs:
        paddocks = paddocks.to_crs(ds_crs)

    paddocks_sorted = paddocks.sort_values('area_ha', ascending=False).reset_index(drop=True)
    paddock_ids = [int(row['paddock']) for _, row in paddocks_sorted.iterrows()]

    transform = ref.rio.transform()
    h, w = ref.sizes['y'], ref.sizes['x']
    shapes = [(geom, pid) for geom, pid in zip(paddocks_sorted.geometry, paddock_ids)]
    mask = rasterize(shapes, out_shape=(h, w), transform=transform, fill=0, dtype=np.int32)

    pad = 2
    bboxes = {}
    mask_crops = {}
    for pid in paddock_ids:
        ys, xs = np.where(mask == pid)
        if len(ys) == 0:
            bboxes[pid] = None
        else:
            y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, h)
            x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, w)
            bboxes[pid] = (y0, y1, x0, x1)
            mask_crops[pid] = mask[y0:y1, x0:x1]

    black_thumb = np.zeros((thumb_size, thumb_size, 3), dtype=np.uint8)
    invalid_thumb = np.zeros((thumb_size, thumb_size), dtype=bool)

    def _crop_all(rgb):
        """Per-paddock ``(thumb, valid_thumb)`` pairs for one observation.

        ``valid_thumb`` is True where the thumbnail pixel is inside the
        paddock and survived cloud masking — used for per-pixel gap fill.
        """
        thumbs = {}
        for pid in paddock_ids:
            bbox = bboxes[pid]
            if bbox is None:
                thumbs[pid] = (black_thumb, invalid_thumb)
                continue
            y0, y1, x0, x1 = bbox
            crop = rgb[y0:y1, x0:x1].copy()
            crop[mask_crops[pid] != pid] = np.nan
            valid = ~np.isnan(crop).any(axis=-1)
            crop = np.nan_to_num(crop, nan=0.0)
            img = Image.fromarray((crop * 255).astype(np.uint8))
            vimg = Image.fromarray(valid.astype(np.uint8) * 255)
            thumbs[pid] = (
                np.array(img.resize((thumb_size, thumb_size), Image.NEAREST)),
                np.array(vimg.resize((thumb_size, thumb_size), Image.NEAREST)) > 0,
            )
        return thumbs

    n_slots = 48
    slot_centres = np.linspace(1, 365, n_slots + 1)
    slot_centres = (slot_centres[:-1] + slot_centres[1:]) / 2

    years_data: dict[int, tuple[dict, dict]] = {}
    for year, ds_year in itertools.chain([first], year_iter):
        obs_doy = ds_year.time.dt.dayofyear.values
        slot_to_obs = [int(np.argmin(np.abs(obs_doy - sc))) for sc in slot_centres]

        # Per-(observation, paddock) clear fraction: how much of the
        # paddock survived cloud masking. One band suffices — cleaning
        # masks all bands together.
        red = ds_year['nbart_red'].values
        clear_px = (red > 0) & ~np.isnan(red)
        clear_frac = {}
        for pid in paddock_ids:
            if bboxes[pid] is None:
                clear_frac[pid] = np.zeros(len(obs_doy))
                continue
            y0, y1, x0, x1 = bboxes[pid]
            in_paddock = mask_crops[pid] == pid
            clear_frac[pid] = clear_px[:, y0:y1, x0:x1][:, in_paddock].mean(axis=1)

        # Resolve each (paddock, slot) to one of: a fully clear direct
        # observation; a mostly-clear observation whose masked pixels get
        # gap-filled ('partial'); or a full temporal interpolation between
        # the nearest clear observations either side ('interp').
        slot_specs: dict[int, list] = {}
        needed: set[int] = set()
        for pid in paddock_ids:
            f = clear_frac[pid]
            valid_obs = np.where(f >= _VALID_FRAC_THRESH)[0]
            specs = []
            for j, sc in enumerate(slot_centres):
                k = slot_to_obs[j]
                if f[k] >= _CLEAR_FULL_THRESH or len(valid_obs) == 0:
                    specs.append(('direct', k))
                    needed.add(k)
                    continue
                doys = obs_doy[valid_obs]
                prev_c = valid_obs[doys <= sc]
                next_c = valid_obs[doys > sc]
                if len(prev_c) and len(next_c):
                    p, n = int(prev_c[-1]), int(next_c[0])
                    w = float((obs_doy[n] - sc) / (obs_doy[n] - obs_doy[p]))
                elif len(prev_c) or len(next_c):
                    p = int(prev_c[-1]) if len(prev_c) else int(next_c[0])
                    n, w = None, 1.0
                if f[k] >= _VALID_FRAC_THRESH:
                    specs.append(('partial', k, p, n, w))
                    needed.add(k)
                else:
                    specs.append(('interp', p, n, w))
                needed.add(p)
                if n is not None:
                    needed.add(n)
            slot_specs[pid] = specs

        obs_thumbs = {}
        for obs_idx in needed:
            rgb = _to_rgb(ds_year, obs_idx)
            obs_thumbs[obs_idx] = _crop_all(rgb)
        years_data[int(year)] = (obs_thumbs, slot_specs)

    return paddocks_sorted, paddock_ids, years_data


# --- per-page figure builder ----------------------------------------------

_MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Figure is sized to match the make_pdf landscape-A4 embed area, so PDF
# scaling is ~1:1 and matplotlib font sizes map straight to PDF points.
_FIG_W_IN = 10.89   # matches make_pdf's max_w
_FIG_H_IN = 7.47    # matches make_pdf's max_h
# Generous side margins so the grid sits visually centred on the page
# instead of bleeding to the edges.
_LEFT_MARGIN = 0.18      # fraction of fig width reserved for paddock labels
_RIGHT_MARGIN = 0.08     # blank gutter on the right of the grid
_TITLE_BAND = 0.06       # fraction of fig height for the title strip (top)
_HEADER_BAND = 0.04      # fraction of fig height for the month-name strip
_BOTTOM_MARGIN = 0.04    # blank gutter under the grid


# One page per paddock: rows are years, columns are the 48 month-slots,
# so the same paddock is seen year-over-year on a single page. Row height
# is fixed by _ROWS_REF so a paddock with few years keeps square-ish
# thumbnails (the grid is then vertically centred) instead of stretching.
_ROWS_REF = 8


def _build_paddock_figure(stub: str, paddock_id: int, label_text: str,
                          area_ha: float,
                          years_sorted: list[int], years_data: dict,
                          n_slots: int = 48, thumb_size: int = 64):
    """Build the matplotlib Figure for one paddock's multi-year calendar.

    The thumbnail grid is composited into a single numpy array and drawn
    via one ``imshow`` (fast). Title (paddock label, area, year range),
    month names, and per-row year labels are matplotlib text — vector
    when saved to PDF.

    Cells whose nearest observation was mostly cloud-masked are filled
    with a time-weighted blend of the nearest clear observations and
    outlined in red; every page carries a matching legend.
    """
    n_rows = len(years_sorted)
    grid_h = n_rows * thumb_size
    grid_w = n_slots * thumb_size
    grid = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    interp_cells: list[tuple[int, int]] = []
    for i, year in enumerate(years_sorted):
        obs_thumbs, slot_specs = years_data[year]
        specs = slot_specs[paddock_id]
        y0 = i * thumb_size

        def _blend(p, n, w):
            if n is None:
                return obs_thumbs[p][paddock_id][0]
            return (w * obs_thumbs[p][paddock_id][0].astype(np.float32)
                    + (1 - w) * obs_thumbs[n][paddock_id][0].astype(np.float32)
                    ).astype(np.uint8)

        for j in range(n_slots):
            spec = specs[j]
            if spec[0] == 'direct':
                tile = obs_thumbs[spec[1]][paddock_id][0]
            elif spec[0] == 'partial':
                _, k, p, n, w = spec
                base, valid = obs_thumbs[k][paddock_id]
                tile = np.where(valid[..., None], base, _blend(p, n, w))
                interp_cells.append((i, j))
            else:
                _, p, n, w = spec
                tile = _blend(p, n, w)
                interp_cells.append((i, j))
            x0 = j * thumb_size
            grid[y0:y0 + thumb_size, x0:x0 + thumb_size] = tile

    fig = plt.figure(figsize=(_FIG_W_IN, _FIG_H_IN))

    # Horizontal extent of the thumbnail grid (left edge = year-label
    # column ends; right edge = right gutter starts).
    grid_left = _LEFT_MARGIN
    grid_right = 1.0 - _RIGHT_MARGIN

    # Vertical: the band sits between the month-name strip and the bottom
    # margin. Row height is fixed by _ROWS_REF so a paddock with few years
    # keeps a consistent per-row height; the grid is then centred.
    band_top    = 1.0 - _TITLE_BAND - _HEADER_BAND
    band_bottom = _BOTTOM_MARGIN
    band_height = band_top - band_bottom
    rows_ref    = max(n_rows, _ROWS_REF)
    row_h_frac  = band_height / rows_ref
    visible_grid_h = row_h_frac * n_rows
    grid_top    = band_top - (band_height - visible_grid_h) / 2
    grid_bottom = grid_top - visible_grid_h

    grid_ax = fig.add_axes([grid_left, grid_bottom,
                            grid_right - grid_left, visible_grid_h])
    grid_ax.imshow(grid, aspect='auto', interpolation='nearest')
    grid_ax.set_xticks([])
    grid_ax.set_yticks([])
    for spine in grid_ax.spines.values():
        spine.set_visible(False)

    # Outline interpolated cells; the legend appears on every page so a
    # reader landing mid-report knows what an outlined cell means.
    from matplotlib.patches import Rectangle
    for i, j in interp_cells:
        grid_ax.add_patch(Rectangle(
            (j * thumb_size - 0.5, i * thumb_size - 0.5), thumb_size, thumb_size,
            fill=False, edgecolor=_INTERP_COLOR, linewidth=1.0,
        ))
    proxy = Rectangle((0, 0), 1, 1, fill=False,
                      edgecolor=_INTERP_COLOR, linewidth=1.2)
    fig.legend([proxy], ['interpolated (no clear observation)'],
               loc='lower center', frameon=False, fontsize=9)

    # Title: "Paddock 1, 32 ha, 2018 – 2025" (single-year drops the range)
    if len(years_sorted) == 1:
        year_text = f'{years_sorted[0]}'
    else:
        year_text = f'{years_sorted[0]} – {years_sorted[-1]}'
    fig.text(0.5, 1.0 - _TITLE_BAND / 2,
             f'{label_text}, {area_ha:.0f} ha, {year_text}',
             ha='center', va='center', fontsize=16, fontweight='bold')

    # Month labels — sit just above the grid so they follow it when centred.
    header_y = grid_top + _HEADER_BAND / 2
    grid_w_frac = grid_right - grid_left
    for m in range(12):
        slot_left = m * 4 + 0.5   # centre of the leftmost slot of this month
        x = grid_left + (slot_left / n_slots) * grid_w_frac
        fig.text(x, header_y, _MONTH_NAMES[m],
                 ha='center', va='center', fontsize=11)

    # Year labels (one per row, right-aligned just to the left of the grid)
    label_x = grid_left - 0.005
    for i, year in enumerate(years_sorted):
        y = grid_top - (i + 0.5) * row_h_frac
        fig.text(label_x, y, str(year),
                 ha='right', va='center', fontsize=11)

    return fig


# --- public API ------------------------------------------------------------

def iter_calendar_figures(query: Query, paddocks_filepath: str | None = None,
                          ds_sentinel2: xr.Dataset | None = None,
                          thumb_size: int = 64,
                          label_col: str | None = None,
                          ) -> Iterator[tuple[int, plt.Figure]]:
    """Yield ``(paddock_id, fig)`` — one page per paddock.

    Each figure shows that paddock across every year in the query (years
    as rows, months as columns), so the same paddock can be compared
    year-over-year, and every paddock starts on a fresh page. Paddocks
    are yielded largest-area first.

    Does not write to disk. Used by :mod:`PaddockTS.Plotting.make_pdf`
    to embed each page directly into the report PDF as a vector-text
    page. The caller is responsible for ``plt.close(fig)`` after
    consuming each Figure.
    """
    if paddocks_filepath is None:
        paddocks_filepath = Paths(query).sam_paddocks

    # ds_sentinel2 may be None: _prepare_thumbnails then streams the
    # cleaned RGB window from the cube one year at a time (memory-bounded).
    paddocks_sorted, paddock_ids, years_data = _prepare_thumbnails(
        query, paddocks_filepath, ds_sentinel2, thumb_size,
    )
    years_sorted = sorted(years_data)

    for orig_idx, pid in enumerate(paddock_ids):
        row = paddocks_sorted.iloc[orig_idx]
        if label_col is not None:
            label_text = str(row[label_col])
        else:
            label_text = f'Paddock {row["paddock"]}'
        fig = _build_paddock_figure(
            stub=query.stub, paddock_id=pid, label_text=label_text,
            area_ha=float(row['area_ha']),
            years_sorted=years_sorted, years_data=years_data,
            thumb_size=thumb_size,
        )
        yield pid, fig


def calendar_plot(query: Query, ds_sentinel2: xr.Dataset | None = None,
                  paddocks_filepath: str | None = None,
                  thumb_size: int = 64,
                  label_col: str | None = None) -> list[str]:
    """Render and save one calendar PNG per paddock.

    Each PNG shows that paddock across every year in the query. They are
    matplotlib-rasterized at 200 dpi for standalone viewing; for the PDF
    report, :mod:`PaddockTS.Plotting.make_pdf` calls
    :func:`iter_calendar_figures` directly so the text stays vector.

    Args:
        query: The :class:`borevitz_lab.query.Query`.
        ds_sentinel2: Optional in-memory cleaned Sentinel-2 dataset. If
            ``None``, opened (or downloaded + cleaned) from
            the pysentinel2 cube (cloud-masked, on read).
        paddocks_filepath: Path to the paddocks file. If ``None``,
            defaults to ``Paths(query).sam_paddocks``.
        thumb_size: Edge length of each thumbnail in pixels (input
            resolution; matplotlib resizes for display). Default 64.
        label_col: Column in the paddocks GeoDataFrame to use for the
            per-page title. ``None`` → ``"P{id}  {area:.0f}ha"``.

    Returns:
        list[str]: Paths of the generated PNGs (one per paddock).
    """
    if paddocks_filepath is None:
        paddocks_filepath = Paths(query).sam_paddocks

    out_stem = Path(paddocks_filepath).stem
    os.makedirs(query.out_dir, exist_ok=True)

    # Clean up any existing calendar PNGs for this stem first.
    for old in glob.glob(f'{query.out_dir}/{out_stem}_calendar_*.png'):
        os.remove(old)

    out_paths: list[str] = []
    for pid, fig in iter_calendar_figures(
        query, paddocks_filepath=paddocks_filepath, ds_sentinel2=ds_sentinel2,
        thumb_size=thumb_size, label_col=label_col,
    ):
        out_path = f'{query.out_dir}/{out_stem}_calendar_p{pid:02d}.png'
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
        print(f'Saved to {out_path}')
        out_paths.append(out_path)
    return out_paths


def test():
    from PaddockTS.utils import get_example_query
    query = get_example_query()
    calendar_plot(query)


if __name__ == '__main__':
    test()
