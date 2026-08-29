from datetime import date

from troi import Troi
from PaddockTS.get_outputs import get_outputs

fp = "artifacts/Milgadara_subset5.gpkg"

q = Troi.build_from_paddocks(
    paddocks_filepath=fp,
    start=date(2018, 1, 1),
    end=date(2025, 12, 31),
    stub="Milgadara_subset5_2018-25",
    label_col="title",
)

get_outputs(q, paddocks_filepath=fp, label_col="title")
print("DONE: full pipeline")
