#!/usr/bin/env python
"""Test runner for license_lock unit tests.

Usage:
    python run_tests.py            # all tests
    python run_tests.py -v         # verbose
    python run_tests.py -k crypto  # filter by keyword

Sets up Odoo import guard before pytest discovers test modules.
Bypasses a pytest CLI edge case on Windows where conftest.py's
import guard doesn't run before the addon's ``__init__.py``.
"""
import os
import sys

# ── Ensure addon parent is on sys.path ──────────────────────────────────────
_addon_dir = os.path.normpath(os.path.join(os.path.dirname(__file__)))
_addon_parent = os.path.normpath(os.path.join(_addon_dir, ".."))
if _addon_parent not in sys.path:
    sys.path.insert(0, _addon_parent)

# ── Odoo import guard (same as tests/conftest.py) ───────────────────────────
from unittest.mock import MagicMock


class _FakeModel:
    """Stand-in for ``odoo.models.Model`` so LicenseManager becomes a real
    subclass with real methods (not a MagicMock)."""
    _auto = False

    def __init__(self, env=None):
        self.env = env

    def __init_subclass__(cls, **kwargs):
        pass

    def ensure_one(self):
        return self

    def write(self, vals):
        return True


_odoo = MagicMock(name="odoo")
_odoo.api = MagicMock(name="odoo.api")
_odoo.fields = MagicMock(name="odoo.fields")
_odoo.exceptions = MagicMock(name="odoo.exceptions")
_odoo.http = MagicMock(name="odoo.http")
_odoo.models = MagicMock(name="odoo.models")
_odoo.models.Model = _FakeModel

for _mod in ["odoo", "odoo.api", "odoo.fields", "odoo.exceptions", "odoo.http", "odoo.models"]:
    sys.modules[_mod] = (
        _odoo if _mod == "odoo" else getattr(_odoo, _mod.split(".")[-1])
    )
# ─────────────────────────────────────────────────────────────────────────────

import pytest

sys.exit(pytest.main(sys.argv[1:] if len(sys.argv) > 1 else ["tests/", "-v", "--no-header"]))
