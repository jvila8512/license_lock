"""
pytest conftest for license_lock unit tests.

IMPORTANT: No module-level imports from ``license_lock`` — they happen
inside fixtures so the Odoo import guard runs first.
"""
import os
import sys
from unittest import mock
from unittest.mock import MagicMock

import pytest

# ── Odoo import guard (module level, BEFORE any license_lock import) ─────────
_addon_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_addon_parent = os.path.normpath(os.path.join(_addon_dir, ".."))
if _addon_parent not in sys.path:
    sys.path.insert(0, _addon_parent)


class _FakeModel:
    """Stand-in for ``odoo.models.Model``.

    A plain Python class so that ``LicenseManager(_FakeModel)`` creates a
    *real* subclass with real methods (not a MagicMock).  This lets tests
    call ``LicenseManager._revalidate(rec)`` as an unbound method.
    """
    _auto = False

    def __init__(self, env=None):
        self.env = env

    def __init_subclass__(cls, **kwargs):
        pass

    def ensure_one(self):
        return self

    def write(self, vals):
        return True


# Build a fake ``odoo`` module tree that looks enough like the real thing
# for ``license_manager.py`` to import successfully.
_odoo = MagicMock(name="odoo")
_odoo.api = MagicMock(name="odoo.api")
_odoo.fields = MagicMock(name="odoo.fields")
_odoo.exceptions = MagicMock(name="odoo.exceptions")
_odoo.http = MagicMock(name="odoo.http")
_odoo.models = MagicMock(name="odoo.models")
_odoo.models.Model = _FakeModel

sys.modules["odoo"] = _odoo
sys.modules["odoo.api"] = _odoo.api
sys.modules["odoo.fields"] = _odoo.fields
sys.modules["odoo.exceptions"] = _odoo.exceptions
sys.modules["odoo.http"] = _odoo.http
sys.modules["odoo.models"] = _odoo.models
# ──────────────────────────────────────────────────────────────────────────────

# NOTE: No ``from license_lock.models…`` at module level — everything is lazy.


# ---------------------------------------------------------------------------
# SHARED FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_secret_key():
    """Patch SECRET_KEY to a deterministic test value for all tests."""
    from license_lock.models import license_manager

    with mock.patch.object(
        license_manager, "SECRET_KEY", b"TEST_SECRET_32_CHARS_0123456789"
    ):
        yield


@pytest.fixture
def instance_id():
    """12-char uppercase hex ID, matching the ``database.uuid`` pattern."""
    return "ABC123DEF456"


@pytest.fixture
def make_valid_code(instance_id):
    """Generate a real HMAC-SHA256 signed license code for testing."""
    from license_lock.models.license_manager import _compute_hash

    def _make(plan, fecha_str, inst_id=None):
        inst_id = inst_id or instance_id
        h = _compute_hash(plan, fecha_str, inst_id)
        return f"ODOO-{plan}-{fecha_str}-{inst_id}-{h}"

    return _make
