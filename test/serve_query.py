# Serve the interactive viewer over a troi's outputs.
#
# Build (or re-use) a Troi, then launch the Streamlit viewer pointed at its
# output directory. Assumes get_outputs(q) has already produced plots/videos
# for this troi — the viewer only reads what's on disk, it doesn't run the
# pipeline.
#
#   python test/serve_troi.py
#
# Local: opens your browser. Over SSH: runs headless and prints the
# `ssh -L` port-forward command to view it in your local browser.
#
# Needs the viewer extra:  pip install 'PaddockTS[viewer]'

from datetime import date
from troi.troi import Troi
from PaddockTS.viewer import serve


troi = Troi(
    bbox=[148.36265, -33.52606, 148.38265, -33.50606],  # [W, S, E, N]
    start=date(2022, 1, 1),
    end=date(2023, 12, 31),
    stub="test_mode1",
)

serve(troi)
