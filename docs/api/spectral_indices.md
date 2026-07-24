# Spectral indices (via pysentinel2)

The five indices — NDVI, CFI, NIRv, NDTI, CAI — live in
[`pysentinel2.derive`](https://github.com/thestochasticman/pysentinel2)
and are computed **on read** from cloud-masked reflectance (nothing is
stored):

```python
from pysentinel2.cube import Cube

ds = Cube(config=q.config).get_ds_query(
    q, indices=('NDVI', 'CFI', 'NIRv', 'NDTI', 'CAI'))
ds['NDVI']   # (time, y, x) float32, NaN where cloudy / nodata
```

Requesting indices implies `clean=True`, so formulas always see
cloud-masked reflectance (DN 0 and nodata are treated as missing, DN
values scaled by 1/10000).

| Index | Formula | Use |
|---|---|---|
| NDVI | `(NIR − Red) / (NIR + Red)` | green vegetation vigour |
| CFI | `NDVI × (Red + 2·Green − Blue)` | crop foliage contrast |
| NIRv | `NDVI × NIR` | GPP proxy |
| NDTI | `(SWIR2 − SWIR3) / (SWIR2 + SWIR3)` | tillage / crop residue |
| CAI | `0.5·(SWIR2 + SWIR3) − NIR` | dry plant matter vs bare soil |

Full reference: `pysentinel2.derive` module docstrings.
