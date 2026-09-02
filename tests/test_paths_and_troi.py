"""Paths derivation and the Troi identity/registry contract."""

from datetime import date

import pytest

from troi import Troi, Config
from PaddockTS.paths import Paths


BBOX = [148.36265, -33.52606, 148.38265, -33.50606]


def _troi(cfg, stub='paths_test', bbox=None, start=date(2022, 1, 1),
          end=date(2022, 12, 31)):
    return Troi(bbox=bbox or BBOX, start=start, end=end, stub=stub, config=cfg)


@pytest.fixture
def cfg(tmp_path):
    return Config(out_dir=str(tmp_path / 'out'), tmp_dir=str(tmp_path / 'tmp'))


def test_paths_layout(cfg):
    q = _troi(cfg)
    paths = Paths(q)
    assert paths.cache_dir == f'{cfg.tmp_dir}/paddockts/{q.bbox_hash}/{q.time_hash}'
    for attr in ('fractional_cover', 'preseg', 'sam_mask', 'sam_raw', 'sam_paddocks'):
        assert getattr(paths, attr).startswith(paths.cache_dir)
    import os
    assert os.path.isdir(paths.cache_dir)


def test_same_region_and_dates_share_cache(cfg):
    """Two stubs over the same bbox x dates resolve to one cache dir."""
    a = Paths(_troi(cfg, stub='stub_a'))
    b = Paths(_troi(cfg, stub='stub_b'))
    assert a.cache_dir == b.cache_dir


def test_different_bbox_gets_different_cache(cfg):
    a = Paths(_troi(cfg, stub='here'))
    shifted = [c + 0.01 for c in BBOX]
    b = Paths(_troi(cfg, stub='there', bbox=shifted))
    assert a.cache_dir != b.cache_dir


def test_registry_rejects_stub_reuse_with_different_dates(cfg):
    _troi(cfg, stub='taken')
    with pytest.raises(ValueError):
        _troi(cfg, stub='taken', end=date(2023, 12, 31))


def test_registry_idempotent_on_exact_match(cfg):
    q1 = _troi(cfg, stub='same')
    q2 = _troi(cfg, stub='same')
    assert q1.bbox_hash == q2.bbox_hash and q1.time_hash == q2.time_hash
