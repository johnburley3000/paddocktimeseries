"""Phenology metrics on a synthetic single-peak NDVI year.

Drives the vendored phenolopy through ``estimate_phenology`` with a
known curve: one smooth peak mid-year, so SoS < PoS < EoS and exactly
one season must come back for every paddock.
"""

import numpy as np
from pathlib import Path

from PaddockTS.Phenology.estimate_phenology import estimate_phenology

from conftest import synthetic_yearly_ndvi


def test_single_peak_orders_sos_pos_eos(tmp_troi):
    ds_yearly = {2022: synthetic_yearly_ndvi()}
    results = estimate_phenology(tmp_troi, ds_yearly=ds_yearly,
                                 paddocks_filepath='synthetic.gpkg')

    assert set(results) == {2022}
    df = results[2022]
    assert len(df) == 2  # both paddocks survived min_observations

    for _, row in df.iterrows():
        assert row.sos_times < row.pos_times < row.eos_times
        assert row.num_peaks == 1
        # Peak of a 0.2 + 0.5*sin^2 curve sits near 0.7.
        assert 0.55 < row.pos_values < 0.85
        # Peak lands mid-year for a curve peaking at the DOY midpoint.
        assert 120 < row.pos_times < 250


def test_csv_written_with_year_column(tmp_troi):
    ds_yearly = {2022: synthetic_yearly_ndvi()}
    estimate_phenology(tmp_troi, ds_yearly=ds_yearly,
                       paddocks_filepath='synthetic.gpkg')
    csv = Path(tmp_troi.out_dir) / 'synthetic_phenology.csv'
    assert csv.exists()
    import pandas as pd
    df = pd.read_csv(csv)
    assert df.columns[0] == 'year'
    assert (df['year'] == 2022).all()


def test_sparse_paddocks_skipped(tmp_troi):
    """A year with fewer observations than min_observations is skipped."""
    ds = synthetic_yearly_ndvi(n_obs=10)
    results = estimate_phenology(tmp_troi, ds_yearly={2022: ds},
                                 paddocks_filepath='synthetic.gpkg',
                                 min_observations=25)
    assert results == {}
