"""Interactive viewer for PaddockTS outputs.

``scan_outputs`` discovers and groups a run's plots / videos / report from
``troi.out_dir``; ``serve`` launches a Streamlit app over them (handling the
local-vs-SSH split automatically).

    from PaddockTS.viewer import serve
    serve(troi)
"""
from PaddockTS.viewer.scan import scan_outputs, OutputSet, Asset
from PaddockTS.viewer.serve import serve

__all__ = ['scan_outputs', 'OutputSet', 'Asset', 'serve']
