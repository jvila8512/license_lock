"""Tests for :meth:`LicenseManager._revalidate`.

All 5 status branches are covered using mocked Odoo infrastructure.
All imports from ``license_lock`` are done inside fixtures / test functions
so that the conftest Odoo import guard runs first.
"""

from datetime import date, datetime
from unittest import mock

import pytest


# Fixed point-in-time used by all revalidation tests.
FIXED_DATETIME = datetime(2026, 7, 28, 12, 0, 0)
FIXED_DATE = date(2026, 7, 28)


# ── fixture: set up mocked Odoo environment ─────────────────────────────────


@pytest.fixture
def revalidate_env(instance_id):
    """Return a MagicMock configured as a LicenseManager record.

    The fixture patches module-level singletons (``fields.Datetime.now``,
    ``fields.Date.context_today``, ``_instance_short_id``), then yields a
    mock record with pre-wired ``env``, ``write()``, and ``ensure_one()``.

    Tests MUST call the real method via::

        LicenseManager._revalidate(rec)
    """
    from license_lock.models import license_manager as lm

    with mock.patch.object(
        lm.fields.Datetime, "now", return_value=FIXED_DATETIME
    ), mock.patch.object(
        lm.fields.Date, "context_today", return_value=FIXED_DATE
    ), mock.patch.object(
        lm, "_instance_short_id", return_value=instance_id
    ):
        rec = mock.MagicMock()
        rec.ensure_one = mock.MagicMock()
        rec.write = mock.MagicMock()

        # Wire config-parameter lookups.
        def _get_param(key, default=""):
            params = {
                "database.uuid": "550e8400-e29b-41d4-a716-446655440000",
                "license_lock.allow_dev": "False",
            }
            return params.get(key, default)

        rec.env.__getitem__.return_value.sudo.return_value.get_param.side_effect = (
            _get_param
        )

        # Default field values — tests override as needed.
        rec.last_seen_date = None
        rec.license_key = None

        yield rec


# ── test helpers ────────────────────────────────────────────────────────────


def _call_revalidate(rec):
    """Invoke the real ``LicenseManager._revalidate()`` on the mock record."""
    from license_lock.models.license_manager import LicenseManager

    LicenseManager._revalidate(rec)


def _write_status(rec):
    """Extract the ``status`` value from the last ``write()`` call."""
    assert rec.write.called, "Expected write() to have been called"
    args, _ = rec.write.call_args
    return args[0]["status"]


def _write_error(rec):
    """Extract the ``error_message`` value from the last ``write()`` call."""
    assert rec.write.called, "Expected write() to have been called"
    args, _ = rec.write.call_args
    return args[0].get("error_message")


# ── _revalidate — branch tests ──────────────────────────────────────────────


class TestRevalidate:
    """TC-REVAL-01 through TC-REVAL-05."""

    def test_clock_tampered(self, revalidate_env):
        """TC-REVAL-01: clock tampering detected → status ``clock_tampered``."""
        rec = revalidate_env
        rec.last_seen_date = date(2026, 7, 30)  # 2 days ahead of FIXED_DATE

        _call_revalidate(rec)

        assert _write_status(rec) == "clock_tampered"
        assert "retrocedió" in _write_error(rec)

    def test_no_previous_license(self, revalidate_env):
        """TC-REVAL-02: no ``last_seen_date`` + invalid key → status ``invalid``."""
        rec = revalidate_env
        rec.last_seen_date = None
        rec.license_key = None

        _call_revalidate(rec)

        assert _write_status(rec) == "invalid"
        assert "No hay código de licencia" in _write_error(rec)

    def test_valid_license(self, revalidate_env, make_valid_code, instance_id):
        """TC-REVAL-03: valid code with future expiry → status ``valid``."""
        rec = revalidate_env
        rec.last_seen_date = date(2026, 7, 27)  # yesterday
        rec.license_key = make_valid_code("MENSUAL", "2026-12-31", instance_id)

        _call_revalidate(rec)

        assert _write_status(rec) == "valid"
        assert _write_error(rec) is False  # explicitly set to False

    def test_expired_license(self, revalidate_env, make_valid_code, instance_id):
        """TC-REVAL-04: valid code with past expiry → status ``expired``."""
        rec = revalidate_env
        rec.last_seen_date = date(2026, 7, 27)  # yesterday
        rec.license_key = make_valid_code("MENSUAL", "2026-01-15", instance_id)

        _call_revalidate(rec)

        assert _write_status(rec) == "expired"
        assert "venció" in _write_error(rec)

    def test_invalid_code(self, revalidate_env):
        """TC-REVAL-05: garbage license key → status ``invalid``."""
        rec = revalidate_env
        rec.last_seen_date = date(2026, 7, 27)
        rec.license_key = "GARBAGE-KEY-THAT-WILL-NEVER-PARSE"

        _call_revalidate(rec)

        assert _write_status(rec) == "invalid"
        assert _write_error(rec) is not None
