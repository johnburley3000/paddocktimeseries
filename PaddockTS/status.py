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
