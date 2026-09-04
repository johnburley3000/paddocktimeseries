"""Stage-by-stage smoke test over user-provided Milgadara paddocks.

Runs each PaddockTS stage individually (rather than through
``get_outputs``) so intermediate outputs can be inspected. Sentinel-2
now comes from the machine-wide pysentinel2 cube (cloud-masked, with
the five indices on read); everything downstream is unchanged.
"""
from datetime import date
from troi import Troi

paddocks_fp = "artifacts/Milgadara_paddock-polygons_2024-12-17_12-45-58.json"

q = Troi.build_from_paddocks(
    paddocks_filepath=paddocks_fp,
    start=date(2018, 1, 1),
    end=date(2025, 12, 31),
    stub="Milgadara_2018-25",
    label_col="title",
)

from pysentinel2.cube import Cube
from pysentinel2.derive import INDICES
from PaddockTS.FractionalCover import compute_fractional_cover
from PaddockTS.PaddockSegmentation.get_paddocks import get_paddocks
from PaddockTS.Phenology.make_paddock_time_series import make_paddock_time_series
from PaddockTS.Phenology.make_smoothed_paddock_time_series import make_smoothed_paddock_time_series
from PaddockTS.Phenology.make_yearly_paddock_time_series import make_yearly_paddock_time_series

# Cloud-masked window + the five spectral indices, straight from the cube.
ds = Cube(config=q.config).get_ds_troi(q, indices=tuple(INDICES))
fc = compute_fractional_cover(q, ds_sentinel2=ds)
# paddocks = get_paddocks(q, ds_sentinel2=ds)  # SAM — slow, run interactively
ts = make_paddock_time_series(q, ds_sentinel2=ds, paddocks_filepath=paddocks_fp)
yearly = make_yearly_paddock_time_series(q, paddocks_filepath=paddocks_fp)
smoothed = make_smoothed_paddock_time_series(
    q, paddocks_filepath=paddocks_fp,
    days=10,          # 10-day median resample
    window_length=7,  # Savitzky-Golay window (odd; coerced if even)
    polyorder=2,      # SG polynomial order (< window_length)
)
