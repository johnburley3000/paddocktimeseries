from os.path import exists
from troi import Troi


def status(troi: Troi) -> dict[str, bool]:
    s = troi.stub
    return {
        'sentinel2_video': exists(f'{troi.out_dir}/{s}_sentinel2.mp4'),
        'sentinel2_paddocks_video': exists(f'{troi.out_dir}/{s}_sentinel2_paddocks.mp4'),
        'fractional_cover_video': exists(f'{troi.out_dir}/{s}_fractional_cover.mp4'),
        'fractional_cover_paddocks_video': exists(f'{troi.out_dir}/{s}_fractional_cover_paddocks.mp4'),
    }


def gaps(troi: Troi) -> dict:
    """Every store's completeness audit for the troi, no network.

    Returns ``{store: troi.ledger.GapReport}`` for the stores
    ``run_environmental`` fills: DEM, OzWALD daily, SILO, SLGA, and the
    Sentinel-2 cube. ``report.complete`` is False while anything is
    ``never_fetched`` or ``claimed_in_progress``; ``report.summary()``
    says what and why.
    """
    from pycopdem.store import Store as _Dem
    from pyozwald.store import Store as _Oz
    from pysilo.store import Store as _Silo
    from pyslga.store import Store as _Slga
    from pysentinel2.cube import Cube as _Cube
    cfg = troi.config
    return {
        'copdem': _Dem(config=cfg).gaps_troi(troi),
        'ozwald_daily': _Oz(config=cfg).gaps_troi(troi, cadence='daily'),
        'silo': _Silo(config=cfg).gaps_troi(troi),
        'slga': _Slga(config=cfg).gaps_troi(troi),
        'sentinel2': _Cube(config=cfg).gaps_troi(troi),
    }


def print_gaps(troi: Troi) -> bool:
    """Print each store's audit; True iff every store is complete."""
    ok = True
    for name, report in gaps(troi).items():
        ok &= report.complete
        print(f'{name}: ' + report.summary().replace('\n', ' | '))
    return ok


if __name__ == '__main__':
    import sys
    from PaddockTS.utils import get_example_troi
    troi = get_example_troi()
    if '--gaps' in sys.argv:
        print_gaps(troi)
    else:
        print(status(troi))
