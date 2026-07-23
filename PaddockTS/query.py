"""PaddockTS speaks the shared borevitz_lab Query — re-exported here.

The generic core (bbox, dates, stub, identity hashes, registry,
``from_lat_lon`` / ``build_from_paddocks`` constructors) lives in
:mod:`borevitz_lab.query`. PaddockTS adds no fields to it (no
inheritance anywhere in the ecosystem) — pipeline-specific output
locations live on :class:`PaddockTS.paths.Paths` instead.
"""
from borevitz_lab.query import Query  # noqa: F401
from borevitz_lab.config import Config, config as default_config  # noqa: F401
