"""Fractional-cover unmixing against the bundled TFLite models.

Fully offline: the model files ship inside the package.
"""

import numpy as np
import pytest

from PaddockTS.FractionalCover._unmix import get_model, unmix_fractional_cover


@pytest.fixture(scope='module')
def model():
    return get_model(n=4)


GREEN_VEG = [0.03, 0.05, 0.04, 0.35, 0.18, 0.09]   # blue..swir3
DRY_SOIL = [0.08, 0.12, 0.18, 0.25, 0.35, 0.30]


def _reflectance(ny=4, nx=4, seed=0):
    """Plausible 6-band surface reflectance: a mix of vegetation and
    soil spectra with small noise (the MLP was trained on real spectra,
    so uniform random input is out-of-distribution)."""
    rng = np.random.default_rng(seed)
    ref = np.empty((6, ny, nx), dtype=np.float32)
    veg = rng.random((ny, nx)) < 0.5
    for b in range(6):
        ref[b] = np.where(veg, GREEN_VEG[b], DRY_SOIL[b])
    ref += rng.normal(0, 0.01, ref.shape).astype(np.float32)
    return np.clip(ref, 0.01, 0.6)


def test_output_shape_and_range(model):
    fractions = unmix_fractional_cover(_reflectance(), fc_model=model)
    assert fractions.shape == (3, 4, 4)
    assert np.all(np.isfinite(fractions))
    # The MLP is unconstrained, but fractions should stay near [0, 1].
    assert fractions.min() > -0.5 and fractions.max() < 1.5


def test_fractions_sum_near_one(model):
    fractions = unmix_fractional_cover(_reflectance(), fc_model=model)
    totals = fractions.sum(axis=0)
    assert np.all(np.abs(totals - 1.0) < 0.35)


def test_deterministic(model):
    a = unmix_fractional_cover(_reflectance(seed=7), fc_model=model)
    b = unmix_fractional_cover(_reflectance(seed=7), fc_model=model)
    np.testing.assert_array_equal(a, b)


def test_all_four_models_load_and_run():
    ref = _reflectance(ny=2, nx=2)
    for n in (1, 2, 3, 4):
        fractions = unmix_fractional_cover(ref, fc_model=get_model(n=n))
        assert fractions.shape == (3, 2, 2)
        assert np.all(np.isfinite(fractions))
