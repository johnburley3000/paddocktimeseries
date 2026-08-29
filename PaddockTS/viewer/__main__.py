"""``python -m PaddockTS.viewer <output_dir> [port]`` — launch the viewer.

For a Troi, prefer the Python API::

    from PaddockTS.viewer import serve
    serve(troi)
"""
import sys

from PaddockTS.viewer.serve import serve

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: python -m PaddockTS.viewer <output_dir> [port]')
        raise SystemExit(2)
    target = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    serve(target, port=port)
