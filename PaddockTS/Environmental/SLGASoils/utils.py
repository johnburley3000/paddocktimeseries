import atexit
import os
import re
import tempfile
from functools import lru_cache
from os import environ

import requests

from .slgasoils import SLGASoils
from PaddockTS.config import config

slga_soils = SLGASoils()

_SLGA_BASE = ('https://data.tern.org.au/model-derived/slga/NationalMaps/'
              'SoilAndLandscapeGrid')


def load_tern_api_key(api_key: str = None) -> str:
    api_key = config.tern_api_key if api_key is None else api_key
    if api_key is None:
        raise ValueError('Set tern_api_key in ~/.config/PaddockTS.json or pass api_key parameter')
    return api_key


# Cache the temp file path so we only write the key to disk once per process.
_TERN_HEADER_FILE: str | None = None


def _setup_tern_auth(api_key: str) -> None:
    """Configure GDAL to authenticate against the TERN COG datastore.

    TERN requires an ``x-api-key`` HTTP header on every COG read; GDAL
    picks it up from ``GDAL_HTTP_HEADER_FILE``. We write the header to a
    process-local temp file once, register an ``atexit`` hook to clean it
    up, then point the env var at it. The legacy ``GDAL_HTTP_USERPWD``
    (basic-auth) variable is cleared so a stale value can't interfere.
    """
    global _TERN_HEADER_FILE
    if _TERN_HEADER_FILE is None:
        fd, path = tempfile.mkstemp(prefix='tern_apikey_', suffix='.txt')
        with os.fdopen(fd, 'w') as f:
            f.write(f'x-api-key: {api_key}\n')
        atexit.register(lambda p=path: os.path.exists(p) and os.remove(p))
        _TERN_HEADER_FILE = path
    environ['GDAL_HTTP_HEADER_FILE'] = _TERN_HEADER_FILE
    environ.pop('GDAL_HTTP_USERPWD', None)


@lru_cache(maxsize=None)
def _slga_dir_listing(attr_code: str, api_key: str) -> tuple:
    """Filenames in the SLGA v2 directory for ``attr_code`` (cached per process).

    Each SLGA attribute is published on its own release date (e.g. CLY/SND on
    2021-09-02 but AWC on 2021-06-14 and BDW on 2023-06-07), so the COG
    filename's date suffix cannot be hardcoded — it is resolved from the TERN
    datastore directory listing.
    """
    r = requests.get(f'{_SLGA_BASE}/{attr_code}/v2/',
                     headers={'x-api-key': api_key}, timeout=60)
    r.raise_for_status()
    return tuple(re.findall(
        rf'{attr_code}_\d{{3}}_\d{{3}}_EV_[A-Za-z_]+_\d{{8}}\.tif', r.text))


def get_cog_url(attribute: str, depth: str, api_key: str = None) -> str:
    """Resolve the expected-value SLGA v2 COG URL for ``attribute`` at ``depth``.

    The release date varies per attribute, so it is resolved from the datastore
    directory listing (requires a TERN api key, loaded from config if not
    passed) rather than a hardcoded filename.
    """
    attr_code = slga_soils.attribute_codes.get(attribute)
    if attr_code is None:
        raise ValueError(
            f"Unknown SLGA attribute '{attribute}'. "
            f"Known: {sorted(slga_soils.attribute_codes)}"
        )
    if depth not in slga_soils.depth_codes:
        raise ValueError(
            f"Unknown SLGA depth '{depth}'. "
            f"Known: {sorted(slga_soils.depth_codes)}"
        )
    depth_start, depth_end = slga_soils.depth_codes[depth]
    api_key = load_tern_api_key(api_key)
    matches = [f for f in _slga_dir_listing(attr_code, api_key)
               if f.startswith(f'{attr_code}_{depth_start}_{depth_end}_EV_')]
    if not matches:
        raise RuntimeError(
            f'No SLGA EV COG for {attribute} ({attr_code}) {depth} in the '
            f'datastore listing at {_SLGA_BASE}/{attr_code}/v2/'
        )
    return f'{_SLGA_BASE}/{attr_code}/v2/{sorted(matches)[-1]}'

