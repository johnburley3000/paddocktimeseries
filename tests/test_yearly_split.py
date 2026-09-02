"""Calendar-year split with day-of-year alignment."""

import numpy as np
import pandas as pd
import xarray as xr

from PaddockTS.Phenology.make_yearly_paddock_time_series import (
    split_paddock_time_series_by_year)


def test_split_by_year():
    time = pd.date_range('2021-11-01', '2022-03-01', freq='10D')
    ds = xr.Dataset(
        {'NDVI': (('paddock', 'time'),
                  np.random.default_rng(0).random((2, time.size)))},
        coords={'paddock': ['1', '2'], 'time': time},
    )
    by_year = split_paddock_time_series_by_year(ds)

    assert set(by_year) == {2021, 2022}
    total = sum(d.sizes['time'] for d in by_year.values())
    assert total == time.size

    for year, ds_year in by_year.items():
        assert ds_year.attrs['year'] == year
        assert (ds_year.time.dt.year == year).all()
        # doy coordinate matches the calendar day-of-year of each timestamp.
        np.testing.assert_array_equal(
            ds_year.doy.values, ds_year.time.dt.dayofyear.values)
