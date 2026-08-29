# Environmental data (via the lab stores)

Climate, terrain, and soil context for the same bounding box and date
range as the Sentinel-2 pipeline. Each source lives in its own
machine-wide, self-filling store — nothing is ever downloaded twice,
and overlapping queries share every byte already fetched. PaddockTS
calls the stores directly; the packages are equally usable standalone.

| Source | Package | What it provides | Auth required |
|---|---|---|---|
| **Copernicus DEM 30 m** | [`pycopdem`](https://github.com/thestochasticman/pycopdem) | elevation + on-read slope / aspect / flow accumulation / TWI / HLI | none |
| **OzWALD** | [`pyozwald`](https://github.com/thestochasticman/pyozwald) | daily meteorology (~5 km) + 8-day biophysical series (~500 m) at AOI centre | none |
| **SILO** | [`pysilo`](https://github.com/thestochasticman/pysilo) | daily climate (T, rain, radiation, ET, vapour pressure) at AOI centre | email |
| **SLGA** | [`pyslga`](https://github.com/thestochasticman/pyslga) | ~90 m soil properties (16 attributes × 6 depths), clipped to AOI | TERN API key |

The Sentinel-2 → PaddockTS chain itself doesn't depend on any of these
— they're independent context layers, useful for downstream analyses
that combine remote sensing with weather, soil, or topography.

Every store follows the same design: a troi-agnostic core
(`get_ds(bbox, ...)` / `get_df(lat, lon, ...)`), a `*_troi` adapter
for pipelines that speak the shared `Troi`, and a `fill(...)` that
returns how much was actually downloaded (0 = fully cached).

---

## Terrain — Copernicus DEM 30 m (`pycopdem`)

One sparse global Zarr on the DEM's native 1-arc-second grid; a chunk
is fetched with a single windowed COG read and never re-downloaded.
Slope, aspect, flow accumulation (pysheds), TWI and Heat Load Index
are computed **on read**, never stored.

```python
from datetime import date
from troi.troi import Troi
from pycopdem.store import Store

q = Troi(
    bbox=[148.36265, -33.52606, 148.38265, -33.50606],
    start=date(2024, 1, 1),
    end=date(2024, 12, 31),
    stub="env_demo",
)

ds = Store(config=q.config).get_ds_troi(q, derivatives=('slope', 'twi'))
ds['elevation']   # (lat, lon), metres
ds['slope']       # degrees, computed on read
```

Dates on the troi are ignored — elevation is time-invariant. Use with
[`terrain_tiles_plot`](plotting.md#terrain-plot) to render elevation /
slope / aspect / flow accumulation.

---

## OzWALD — daily meteorology + 8-day biophysical (`pyozwald`)

Point series sampled at the AOI centre from NCI THREDDS (OPeNDAP),
stored per (grid point, variable, year) so an in-progress year keeps
re-fetching until complete, then never again.

```python
from pyozwald.store import Store

store = Store(config=q.config)
met = store.get_df_troi(q, cadence='daily')                     # Pg, Tmax, Tmin, Uavg, ...
veg = store.get_df_troi(q, cadence='8day',
                         variables=['NDVI', 'LAI', 'GPP', 'Ssoil'])
```

Daily meteorology snaps to OzWALD's ~5 km grid, the 8-day biophysical
variables to its ~500 m grid — nearby farms in the same cell share one
stored series.

---

## SILO — daily climate (`pysilo`)

Point series from the DataDrill endpoint at the AOI centre, snapped to
SILO's native 0.05° (~5 km) grid, with a coverage-span ledger so only
missing date ranges are ever requested. Requires a registration email
(`email` in `~/.config/Troi.json`, or `TROI_EMAIL`).

```python
from pysilo.store import Store

df = Store(config=q.config).get_df_troi(q)
df.columns   # date, daily_rain, max_temp, min_temp, radiation, vp, et_short_crop, ... (18 vars)
```

---

## SLGA — soil properties (`pyslga`)

National ~90 m COGs, one per attribute × depth, windowed-read per chunk
into a sparse store. Layer filenames are resolved from the TERN
datastore listing at first contact (release dates differ per
attribute). Pixel reads require a TERN API key (`tern_api_key` in
`~/.config/Troi.json`, or `TROI_TERN_KEY` — free from
<https://account.tern.org.au/>); cached reads need no key.

```python
from pyslga.store import Store

ds = Store(config=q.config).get_ds_troi(
    q, attributes=('Clay', 'Sand', 'Silt', 'pH_Water'),
    depths=('0-5cm', '5-15cm'))
ds['Clay_5-15cm']   # (lat, lon), percent
```

---

## DAESIM forcing

`PaddockTS.Environmental.daesim_forcing` assembles the DAESIM
climate-forcing table (SILO radiation + OzWALD daily meteorology +
8-day biophysical series forward-filled to daily, renamed to DAESIM's
vocabulary) from the stores, cached per stub as
`{out_dir}/{stub}_DAESim_forcing.csv`:

```python
from PaddockTS.Environmental.daesim_forcing import daesim_forcing

df = daesim_forcing(q)   # date + 10 DAESIM columns, one row per day
```

---

## Reference

Full API reference for each store lives in its own repository — see
the READMEs (each has a live-measured *Performance* section) and
module docstrings.

### `daesim_forcing`

::: PaddockTS.Environmental.daesim_forcing.daesim_forcing
