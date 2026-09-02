"""The _SUCCESS cache-marker contract shared by every cached artifact.

Zarr stores carry the marker inside the directory; single-file
artifacts (GeoTIFF, GeoPackage) carry it as a ``._SUCCESS`` sibling. A
data file without its marker (a run killed mid-write) must read as
invalid so the stage recomputes.
"""

import os

from PaddockTS.utils import check_if_valid_zarr_exists
from PaddockTS.FractionalCover.check_if_valid_fractional_cover_exists import (
    check_if_valid_fractional_cover_exists)
from PaddockTS.PaddockSegmentation.check_if_valid_paddocks_exists import (
    check_if_valid_paddocks_exists)
from PaddockTS.PaddockSegmentation.check_if_valid_preseg_exists import (
    check_if_valid_preseg_exists)


def test_zarr_marker_contract(tmp_path):
    zarr = tmp_path / 'data.zarr'
    assert not check_if_valid_zarr_exists(str(zarr))          # nothing there
    zarr.mkdir()
    assert not check_if_valid_zarr_exists(str(zarr))          # no marker: invalid
    (zarr / '_SUCCESS').touch()
    assert check_if_valid_zarr_exists(str(zarr))              # marker: valid


def test_fractional_cover_uses_zarr_contract(tmp_path):
    zarr = tmp_path / 'fc.zarr'
    zarr.mkdir()
    assert not check_if_valid_fractional_cover_exists(str(zarr))
    (zarr / '_SUCCESS').touch()
    assert check_if_valid_fractional_cover_exists(str(zarr))


def test_single_file_sibling_marker_contract(tmp_path):
    for name, check in (('p.gpkg', check_if_valid_paddocks_exists),
                        ('p.tif', check_if_valid_preseg_exists)):
        f = tmp_path / name
        assert not check(str(f))                              # nothing there
        f.touch()
        assert not check(str(f))                              # no marker: invalid
        (tmp_path / f'{name}._SUCCESS').touch()
        assert check(str(f))                                  # marker: valid


def test_marker_alone_is_not_enough(tmp_path):
    """A stray marker with no data file must not validate the cache."""
    (tmp_path / 'p.gpkg._SUCCESS').touch()
    assert not check_if_valid_paddocks_exists(str(tmp_path / 'p.gpkg'))
