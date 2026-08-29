"""The demo-notebook Milgadara run (demo/Milgadara_demonstration.ipynb),
as a script: full farm, both paddock modes, via get_outputs."""
from datetime import date

from troi import Troi
from PaddockTS.get_outputs import get_outputs

paddocks_fp = "artifacts/Milgadara_paddock-polygons_2024-12-17_12-45-58.json"

q = Troi.build_from_paddocks(
    paddocks_filepath=paddocks_fp,
    start=date(2018, 1, 1),
    end=date(2025, 12, 31),
    stub="Milgadara_2018-25",
    label_col="title",
)

get_outputs(q, skip_sam=True, paddocks_filepath=paddocks_fp)
get_outputs(q, skip_sam=False)
print("DONE: demo run, both modes")
