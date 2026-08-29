"""Render a true-colour Sentinel-2 timeline as an MP4 video.

Each frame is a normalised RGB composite from the ``nbart_red``,
``nbart_green``, ``nbart_blue`` bands with the acquisition date stamped
in the top-right corner. Frames are written as PNGs to a temporary
directory, then encoded to H.264 with ``ffmpeg`` (``libopenh264``).
"""

import cv2
import numpy as np
import xarray as xr
from troi import Troi


def _to_rgb(ds, time_idx):
    r = ds['nbart_red'].isel(time=time_idx).values.astype(np.float32)
    g = ds['nbart_green'].isel(time=time_idx).values.astype(np.float32)
    b = ds['nbart_blue'].isel(time=time_idx).values.astype(np.float32)
    rgb = np.stack([r, g, b], axis=-1)
    rgb[rgb == 0] = np.nan
    rgb /= 10000.0
    rgb = np.clip(rgb * 3, 0, 1)
    rgb = np.nan_to_num(rgb, nan=0.0)
    return rgb


def sentinel2_video(troi: Troi, ds_sentinel2=None, fps: int = 4, min_size: int = 1080):
    """Encode the Sentinel-2 cube as a true-colour H.264 video.

    Args:
        troi: The :class:`troi.Troi`. Output is written to
            ``{troi.out_dir}/{troi.stub}_sentinel2.mp4``.
        ds_sentinel2: Optional in-memory Sentinel-2 dataset. If ``None``,
            the cloud-masked window is read from the pysentinel2 cube.
        fps: Frames per second. Default 4.
        min_size: Minimum dimension (height or width) of the output
            video, in pixels. Smaller cubes are upscaled with
            nearest-neighbour to ensure legibility; H.264 requires even
            dimensions, so the final size is rounded down to even.

    Returns:
        str: Filesystem path of the generated MP4.

    Raises:
        RuntimeError: If the ``ffmpeg`` invocation returns a non-zero
            exit code.
    """
    if ds_sentinel2 is None:
        from pysentinel2.cube import Cube
        ds = Cube(config=troi.config).get_ds_troi(troi, clean=True)
    else:
        ds = ds_sentinel2
    n_times = ds.sizes['time']
    dates = ds.time.values
    h, w = ds.sizes['y'], ds.sizes['x']

    scale = max(1, min_size / max(h, w))
    out_h, out_w = int(h * scale) // 2 * 2, int(w * scale) // 2 * 2  # H.264 needs even dimensions

    import os
    import subprocess
    import tempfile

    os.makedirs(troi.out_dir, exist_ok=True)
    out_path = f'{troi.out_dir}/{troi.stub}_sentinel2.mp4'

    # write frames as PNGs, then encode with ffmpeg for H.264
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(n_times):
            rgb = _to_rgb(ds, i)
            frame = (rgb * 255).astype(np.uint8)
            if scale != 1:
                frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_NEAREST)

            date_str = str(np.datetime_as_string(dates[i], unit='D'))
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = out_h / 600
            thickness = max(1, int(out_h / 400))
            (tw, th), _ = cv2.getTextSize(date_str, font, font_scale, thickness)
            x_pos = out_w - tw - 15
            y_pos = th + 15
            cv2.putText(frame, date_str, (x_pos, y_pos), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite(f'{tmpdir}/frame_{i:04d}.png', bgr)

        result = subprocess.run([
            'ffmpeg', '-y', '-framerate', str(fps),
            '-i', f'{tmpdir}/frame_%04d.png',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            out_path,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError(f'ffmpeg failed with code {result.returncode}')

    print(f'Saved video to {out_path}')
    return out_path



def test():
    from PaddockTS.utils import get_example_troi
    sentinel2_video(get_example_troi())

if __name__ == '__main__':
    test()
