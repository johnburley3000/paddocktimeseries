from datetime import date

from troi.troi import Troi
from PaddockTS.Plotting.calendar_plot import calendar_plot

# 5-paddock cluster subset of the Milgadara farm (>=5 ha, chosen by
# nearest-centroid growth from the largest paddock).
fp = "artifacts/Milgadara_subset5.gpkg"

q = Troi.build_from_paddocks(
    paddocks_filepath=fp,
    start=date(2018, 1, 1),
    end=date(2025, 12, 31),
    stub="Milgadara_subset5_2018-25",
    label_col="title",
)

# Pre-fill the cube with higher I/O concurrency than the plotting
# path's default; the render's own fill then finds nothing missing.
from pysentinel2.cube import Cube
Cube(config=q.config).fill_troi(q, threads=16)

paths = calendar_plot(q, paddocks_filepath=fp, label_col="title")
print(f"DONE: {len(paths)} calendar pages")
