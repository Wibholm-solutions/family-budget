"""Backward-compatibility shim.

All logic has moved to src/db/. This module re-exports everything
so existing `from src import database as db` and
`from src.database import X` imports continue working.

DB_PATH writes (e.g. conftest's `db.DB_PATH = temp_path`) are intercepted
by _ShimModule and propagated to src.db.connection.DB_PATH.
"""

import sys as _sys
import types as _types

import src.db.connection as _conn
from src.db import *  # noqa: F403


class _ShimModule(_types.ModuleType):
    """Module subclass that intercepts DB_PATH assignment.

    Python data descriptors (properties with __get__ + __set__) take
    precedence over instance __dict__ entries, so the property always wins.
    """

    @property
    def DB_PATH(self):
        return _conn.DB_PATH

    @DB_PATH.setter
    def DB_PATH(self, value):
        _conn.DB_PATH = value


# Replace this module in sys.modules with the shim instance
_current = _sys.modules[__name__]
_shim = _ShimModule(__name__)
_shim.__dict__.update({k: v for k, v in _current.__dict__.items()
                       if k != '_ShimModule'})
_shim.__file__ = __file__
_shim.__package__ = __package__
_sys.modules[__name__] = _shim
