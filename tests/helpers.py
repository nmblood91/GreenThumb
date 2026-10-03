"""Shared fixtures for the test scripts.

These are plain assert scripts rather than a pytest suite, so there is no
conftest to hang fixtures off. This module is the equivalent: imported by name,
with tests/run_all.py putting the repo root on PYTHONPATH.
"""

import tempfile
from pathlib import Path

from greenthumb.history import HistoryStore


def temp_store() -> HistoryStore:
    """A throwaway history database. Tests must never touch the real one."""
    return HistoryStore(Path(tempfile.mkdtemp()) / "test.db")


def temp_state() -> Path:
    """A throwaway settings file. Tests must never touch the real one."""
    return Path(tempfile.mkdtemp()) / "state.json"
