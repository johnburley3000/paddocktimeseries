"""Small-ROI get_outputs on the per-rect fill: a ~2x2 km box straddling
the Milgadara farm's eastern coverage boundary, calendar year 2024."""
from datetime import date

from troi import Troi
from PaddockTS.get_outputs import get_outputs

q = Troi(
    bbox=[148.512, -34.415, 148.535, -34.395],
    start=date(2024, 1, 1),
    end=date(2024, 12, 31),
    stub="smallroi_edge_2024",
)

get_outputs(q)
print("DONE: small ROI")
