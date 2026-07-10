from attrs import frozen, field, Factory as F
from typing_extensions import Self
from os.path import expanduser
from tabulate import tabulate
from typing import Optional
from os.path import exists
from os import makedirs
from json import load
import os

build_from_out_dir = F(lambda s: f'{s.out_dir}/queries.json', takes_self=True)
_out = expanduser('~/Documents/PaddockTS-Outputs')
_tmp = expanduser('~/Downloads/PaddockTS-Tmp')
@frozen
class Config:
    out_dir: str = _out
    tmp_dir: str = _tmp
    hash_file: str = field(default=build_from_out_dir)
    email: Optional[str] = None
    tern_api_key: Optional[str] = None

    def __post_init__(s: Self):
        makedirs(s.out_dir, exist_ok=True)
        makedirs(s.tmp_dir, exist_ok=True)
    
    def __str__(s: Self):
        return tabulate(
            [
                ['out_dir', s.out_dir],
                ['tmp_dir', s.tmp_dir],
                ['hash_file', s.hash_file],
                ['email', s.email if bool(s.email) else 'NOT SET'],
                ['tern_api_key', 'SET' if bool(s.tern_api_key) else 'NOT SET']
            ]
        )

_out = os.getenv("PADDOCKTS_OUTDIR", expanduser('~/Documents/PaddockTS-Outputs'))
_tmp = os.getenv("PADDOCKTS_TMPDIR", expanduser('~/Downloads/PaddockTS-Tmp'))
_email = os.getenv("PADDOCKTS_EMAIL") # default None
_tern_api_key = os.getenv("PADDOCKTS_TERN_KEY") # default None
_default = Config(_out, _tmp, email=_email, tern_api_key=_tern_api_key)

confpath = os.getenv("PADDOCKTS_CONFIG", os.path.expanduser('~/.config/PaddockTS.json'))
config = Config(**load(open(confpath))) if exists(confpath) else _default


if __name__ == '__main__':
    _config = Config(_out, _tmp)
    print(_config)
