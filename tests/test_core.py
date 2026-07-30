"""Tests for :func:`_compute_hash` and :func:`_parse_and_verify`.

All imports from ``license_lock`` are done inside test functions / classes
so that the conftest Odoo import guard runs first.
"""

import re
from datetime import date

import pytest


def _import():
    """Lazy-import the module under test (after conftest guard has fired)."""
    from license_lock.models.license_manager import (
        DEV_CODES,
        PLANES_DIAS,
        _compute_hash,
        _parse_and_verify,
    )

    return DEV_CODES, PLANES_DIAS, _compute_hash, _parse_and_verify


HEX8_RE = re.compile(r"^[0-9A-F]{8}$")

# ── _compute_hash ───────────────────────────────────────────────────────────


class TestComputeHash:
    """TC-CRYPTO-01 through TC-CRYPTO-03."""

    def test_deterministic(self):
        """TC-CRYPTO-01: same input → same hash."""
        _, _, _compute_hash, _ = _import()
        h1 = _compute_hash("MENSUAL", "2026-12-31", "ABC123DEF456")
        h2 = _compute_hash("MENSUAL", "2026-12-31", "ABC123DEF456")
        assert h1 == h2
        assert HEX8_RE.match(h1)

    @pytest.mark.parametrize("plan", sorted(["MENSUAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"]))
    def test_all_plans_produce_valid_hash(self, plan):
        """TC-CRYPTO-02: every plan type produces non-empty 8-char hex."""
        _, _, _compute_hash, _ = _import()
        h = _compute_hash(plan, "2026-12-31", "ABC123DEF456")
        assert len(h) == 8
        assert HEX8_RE.match(h)

    def test_different_inputs_differ(self):
        """TC-CRYPTO-03: different inputs produce different hashes."""
        _, _, _compute_hash, _ = _import()
        h1 = _compute_hash("MENSUAL", "2026-01-01", "ABC123DEF456")
        h2 = _compute_hash("MENSUAL", "2026-06-15", "ABC123DEF456")
        assert h1 != h2

        h3 = _compute_hash("ANUAL", "2026-01-01", "ABC123DEF456")
        assert h1 != h3


# ── _parse_and_verify ───────────────────────────────────────────────────────


class TestParseAndVerify:
    """TC-CRYPTO-04 through TC-CRYPTO-13."""

    # -- valid path -----------------------------------------------------------

    @pytest.mark.parametrize("plan", ["MENSUAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL"])
    def test_valid_code_all_plans(self, make_valid_code, instance_id, plan):
        """TC-CRYPTO-04: freshly generated valid code for every plan."""
        _, _, _compute_hash, _parse_and_verify = _import()

        code = make_valid_code(plan, "2026-12-31")
        result, err = _parse_and_verify(code, instance_id)
        assert err is None
        assert result["plan"] == plan
        assert result["fecha_expiracion"] == date(2026, 12, 31)

    # -- error: empty / whitespace-only input ---------------------------------

    @pytest.mark.parametrize("bad_input", [None, "", "  ", "\t"])
    def test_empty_input(self, instance_id, bad_input):
        """TC-CRYPTO-05: empty / None / whitespace → error."""
        _, _, _, _parse_and_verify = _import()
        result, err = _parse_and_verify(bad_input, instance_id)
        assert result is None
        assert err == "No hay código de licencia."

    # -- error: malformed format ----------------------------------------------

    @pytest.mark.parametrize(
        "bad_code",
        [
            "SHORT",                                      # single token
            "ODOO-MENSUAL-2026",                          # too few parts
            "ODOO-MENSUAL-2026-12-31-ABC123-EXTRA-MORE",  # too many parts
            "NOT-ODOO-MENSUAL-2026-12-31-ABC123-HASH",    # wrong prefix
            "FOO-BAR-BAZ-QUX-QUUX-CORGE-GRAULT",          # doesn't start with ODOO
        ],
    )
    def test_invalid_format(self, instance_id, bad_code):
        """TC-CRYPTO-06: malformed format → error."""
        _, _, _, _parse_and_verify = _import()
        result, err = _parse_and_verify(bad_code, instance_id)
        assert result is None
        assert err == "Formato de código inválido."

    # -- error: unknown plan --------------------------------------------------

    def test_unknown_plan(self, make_valid_code, instance_id):
        """TC-CRYPTO-07: plan not in PLANES_DIAS → error."""
        _, PLANES_DIAS, _, _parse_and_verify = _import()

        code = make_valid_code("MENSUAL", "2026-12-31")
        mutated = code.replace("MENSUAL", "BIMESTRAL", 1)
        result, err = _parse_and_verify(mutated, instance_id)
        assert result is None
        assert err == "Plan de licencia desconocido."

    # -- error: invalid date --------------------------------------------------

    @pytest.mark.parametrize(
        "bad_code",
        [
            "ODOO-MENSUAL-2026-13-01-ABC123-XXXXXXXX",   # month=13
            "ODOO-MENSUAL-2026-00-01-ABC123-XXXXXXXX",   # month=0
            "ODOO-MENSUAL-2026-01-32-ABC123-XXXXXXXX",   # day=32
            "ODOO-MENSUAL-2026-01-00-ABC123-XXXXXXXX",   # day=0
        ],
    )
    def test_invalid_date(self, instance_id, bad_code):
        """TC-CRYPTO-08: unparseable date → error."""
        _, _, _, _parse_and_verify = _import()
        result, err = _parse_and_verify(bad_code, instance_id)
        assert result is None
        assert err == "Fecha inválida en el código."

    # -- error: instance mismatch ---------------------------------------------

    def test_instance_mismatch(self, make_valid_code, instance_id):
        """TC-CRYPTO-09: instance_id differs from code → error."""
        _, _, _, _parse_and_verify = _import()

        code = make_valid_code("MENSUAL", "2026-12-31")
        wrong_id = "ZZZZZZZZZZZZ"
        result, err = _parse_and_verify(code, wrong_id)
        assert result is None
        assert err == "Esta licencia fue emitida para otra instalación de Odoo."

    # -- error: corrupted hash ------------------------------------------------

    def test_corrupted_hash(self, make_valid_code, instance_id):
        """TC-CRYPTO-10: last character of hash altered → error."""
        _, _, _, _parse_and_verify = _import()

        code = make_valid_code("MENSUAL", "2026-12-31")
        corrupted = code[:-1] + ("0" if code[-1] != "0" else "1")
        result, err = _parse_and_verify(corrupted, instance_id)
        assert result is None
        assert err == "Código no autorizado (firma inválida)."

    # -- dev code with allow_dev=True -----------------------------------------

    def test_dev_code_with_flag(self, instance_id):
        """TC-CRYPTO-11: DEV code accepted when allow_dev=True."""
        DEV_CODES, _, _, _parse_and_verify = _import()
        dev_code = DEV_CODES[0]
        result, err = _parse_and_verify(dev_code, instance_id, allow_dev=True)
        assert err is None
        assert result["plan"] == "MENSUAL"
        assert result["fecha_expiracion"] == date(2099, 12, 31)

    # -- dev code with allow_dev=False ----------------------------------------

    def test_dev_code_without_flag(self, instance_id):
        """TC-CRYPTO-12: DEV code rejected when allow_dev=False."""
        DEV_CODES, _, _, _parse_and_verify = _import()
        dev_code = DEV_CODES[0]
        result, err = _parse_and_verify(dev_code, instance_id, allow_dev=False)
        assert result is None
        # Falls through to normal validation → instance mismatch
        # (DEV code has "DEVDEVDEVDEV" as instance_id, not our fixture)
        assert err is not None

    # -- case insensitivity ---------------------------------------------------

    def test_case_insensitivity(self, make_valid_code, instance_id):
        """TC-CRYPTO-13: lowercase / mixed-case input is uppercased internally."""
        _, _, _, _parse_and_verify = _import()

        valid_code = make_valid_code("MENSUAL", "2026-12-31")
        for variant in [valid_code.lower(), valid_code.title()]:
            result, err = _parse_and_verify(variant, instance_id)
            assert err is None
            assert result["plan"] == "MENSUAL"
