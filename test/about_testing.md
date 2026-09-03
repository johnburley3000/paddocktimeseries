# About testing

Two layers:

- **`tests/` (repo root)** — the automated offline unit suite (pytest,
  synthetic inputs, no network). Runs in CI on every push:
  `pip install -e '.[tests]' && pytest`.
- **`test/` (this directory)** — end-to-end acceptance scripts against
  the live data services (DEA, SILO, OzWALD, …), run manually.

Each .py script here creates a troi and runs get_outputs()

## First, test mode 1: user provided AOI and date range
```
python test/test_mode1.py
```

## Second, test mode 2: user provides paddock polygons and date range
This depends on artifacts/*.gpkg as specified in Troi.build_from_paddocks() 
```
python test/test_mode2.py # provides .gpkg from hand-drawn polygons somewhere in WA. 
python test/test_mode2_milgadara.py # provides a .json from Agriweb for milgadara
```
## Third, test with user-provided paddocks but run functions individally i.e. don't use get_outputs()
```
python test/slow.py # for this, I used milgadara paddocks .gpkg and 2018-2025.
```

## Fourth, do the full Milgadara demo, replicating the outputs shown in manuscript.
This will take ~2 hrs or so to run the pipeline, then run the jupyter notebook 
```
python demo/Milgadara_2018-25_case_study.py
jupyter lab demo/Milgadara_demonstration.ipynb
```

## Results
### jtb Sept 3 2026 on Mac
test/test_mode1.py -- works

test/test_mode2.py -- works

test/test_mode2_milgadara.py -- works

python test/slow.py -- finished running when copy-pasted into python. (waiting retest)

demo/Milgadara_2018-25_case_study.py -- (waiting retest)

