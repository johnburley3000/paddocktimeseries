"""Derived on-disk locations of PaddockTS's own artifacts.

PaddockTS consumes its input data (Sentinel-2, climate, terrain, soils)
as in-memory datasets from the machine-wide stores — pysentinel2,
pysilo, pyozwald, pycopdem, pyslga — which own their caching. The only
artifacts PaddockTS itself writes are the products of its pipeline:
the fractional-cover cube, the SAM segmentation chain, the per-paddock
time series, and the plots/report in ``troi.out_dir``.

Intermediates cacheable across stubs live under a region x time cache
keyed by the Troi's identity hashes; rule of thumb across the lab's
packages: user-settable inputs → Config, derived locations → Paths.
No inheritance — composition only.
"""
from attrs import frozen, field
from os import makedirs

from troi.troi import Troi


@frozen
class Paths:
    """Where the PaddockTS pipeline writes for one Troi.

    Attributes:
        troi: The :class:`troi.troi.Troi` the paths are keyed by.
        cache_dir: Region x time cache
            (``{config.tmp_dir}/paddockts/{bbox_hash}/{time_hash}``).
            Created on init. Two stubs with the same bbox and dates share
            every artifact below.
        fractional_cover: Fractional-cover Zarr (bg/pv/npv) written by
            :func:`PaddockTS.FractionalCover.compute_fractional_cover`.
        preseg: NDWI Fourier-feature presegmentation image feeding SAM.
        sam_mask: SAM mask raster.
        sam_raw: Raw SAM polygons before filtering.
        sam_paddocks: Filtered paddock polygons (GeoPackage).

    Example:
        ```python
        from PaddockTS.paths import Paths

        paths = Paths(troi)
        paths.fractional_cover  # '.../paddockts/<bbox_hash>/<time_hash>/fractional_cover.zarr'
        ```
    """

    troi: Troi

    cache_dir: str = field(init=False)
    fractional_cover: str = field(init=False)
    preseg: str = field(init=False)
    sam_mask: str = field(init=False)
    sam_raw: str = field(init=False)
    sam_paddocks: str = field(init=False)

    cache_dir.default(lambda s: (f'{s.troi.config.tmp_dir}/paddockts/'
                                 f'{s.troi.bbox_hash}/{s.troi.time_hash}'))
    fractional_cover.default(lambda s: f'{s.cache_dir}/fractional_cover.zarr')
    preseg.default(lambda s: f'{s.cache_dir}/preseg.tif')
    sam_mask.default(lambda s: f'{s.cache_dir}/sam_mask.tif')
    sam_raw.default(lambda s: f'{s.cache_dir}/sam_raw.gpkg')
    sam_paddocks.default(lambda s: f'{s.cache_dir}/sam_paddocks.gpkg')

    def __attrs_post_init__(s):
        makedirs(s.cache_dir, exist_ok=True)


def _temp_troi():
    import tempfile
    from datetime import date
    from troi.config import Config
    tmpdir = tempfile.mkdtemp(prefix='paddockts_paths_test_')
    return Troi(
        bbox=[148.36265, -33.52606, 148.38265, -33.50606],
        start=date(2020, 1, 1), end=date(2021, 12, 31),
        stub='paddockts_paths_test',
        config=Config(out_dir=tmpdir, tmp_dir=tmpdir),
    )


def test_paths_derive_from_troi_hashes():
    from os.path import exists
    q = _temp_troi()
    paths = Paths(q)
    return (
        paths.cache_dir == f'{q.config.tmp_dir}/paddockts/{q.bbox_hash}/{q.time_hash}'
        and paths.fractional_cover == f'{paths.cache_dir}/fractional_cover.zarr'
        and paths.sam_paddocks == f'{paths.cache_dir}/sam_paddocks.gpkg'
        and exists(paths.cache_dir)
    )


def test_same_identity_shares_cache():
    """Two stubs over the same bbox x dates resolve to one cache dir."""
    from datetime import date
    q1 = _temp_troi()
    q2 = Troi(bbox=q1.bbox, start=date(2020, 1, 1), end=date(2021, 12, 31),
               stub='another_stub', config=q1.config)
    return Paths(q1).cache_dir == Paths(q2).cache_dir


def test():
    return all([
        test_paths_derive_from_troi_hashes(),
        test_same_identity_shares_cache(),
    ])


if __name__ == '__main__':
    print(test())
