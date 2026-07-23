"""Cache-validity check for the computed fractional-cover zarr.

A valid cache requires both the zarr directory and a ``_SUCCESS`` marker
file *inside* it (written by :func:`compute_fractional_cover` only after
the zarr write completes). Without the marker the zarr is treated as a
partial / interrupted write and recomputed.
"""

from os.path import exists


def check_if_valid_fractional_cover_exists(fractional_cover_path: str) -> bool:
    """Return True iff a successfully-written fractional-cover zarr is on disk."""
    return exists(fractional_cover_path) and exists(f'{fractional_cover_path}/_SUCCESS')


def test_no_zarr_no_marker():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        return check_if_valid_fractional_cover_exists(f'{tmpdir}/missing.zarr') is False


def test_zarr_without_marker():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        zarr_path = f'{tmpdir}/data.zarr'
        os.makedirs(zarr_path)
        return check_if_valid_fractional_cover_exists(zarr_path) is False


def test_zarr_with_marker():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        zarr_path = f'{tmpdir}/data.zarr'
        os.makedirs(zarr_path)
        open(f'{zarr_path}/_SUCCESS', 'w').close()
        return check_if_valid_fractional_cover_exists(zarr_path) is True


def test():
    return all([
        test_no_zarr_no_marker(),
        test_zarr_without_marker(),
        test_zarr_with_marker(),
    ])


if __name__ == '__main__':
    print(test())
