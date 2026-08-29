from datetime import date
from troi.troi import Troi
from PaddockTS.get_outputs import get_outputs

troi = Troi(
    bbox=[148.36265, -33.52606, 148.38265, -33.50606],  # [W, S, E, N]
    start=date(2022, 1, 1),
    end=date(2023, 12, 31),
    stub="test_mode1",
)

get_outputs(troi, show_log=True)

