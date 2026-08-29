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

get_outputs(
    q,
    skip_sam=True,
    paddocks_filepath=paddocks_fp
)

# note: if skip_sam = True in get_output(), must specify paddocks_filepath. This is so that users can re-run get_outputs with different paddocks for the same query.

# Also run it with samgeo so we can compare outputs with auto- and userprovided- paddock boundaries.
get_outputs(
    q,
    skip_sam=False,
)
