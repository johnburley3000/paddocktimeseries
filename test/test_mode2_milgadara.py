from datetime import date
from troi.troi import Troi
from PaddockTS.get_outputs import get_outputs

paddocks_fp = "artifacts/Milgadara_paddock-polygons_2024-12-17_12-45-58.json"

q = Troi.build_from_paddocks(
    paddocks_filepath=paddocks_fp,
    start=date(2018, 1, 1),
    end=date(2018, 12, 31),
    stub="Migadara_2018",
    label_col="title",
)

get_outputs(
    q,
    skip_sam=True,
    paddocks_filepath=paddocks_fp
)

# note: if skip_sam = True in get_output(), must specify paddocks_filepath. This is so that users can re-run get_outputs with different paddocks for the same troi.
