"""
Tests for license.update.wizard — the backend flow to update the license
(main form shows the code readonly; the wizard is the only write path).
"""
from unittest.mock import MagicMock


def _wizard_cls():
    from license_lock.models.license_manager import LicenseUpdateWizard
    return LicenseUpdateWizard


class TestLicenseUpdateWizard:

    def test_apply_writes_key_revalidates_and_reopens_form(self):
        """action_apply: writes key to the singleton, revalidates, reopens form."""
        Wiz = _wizard_cls()
        env = MagicMock(name='env')
        wiz = Wiz(env=env)
        wiz.license_key = 'ADMIN-NEGOCIO-2027-09-24-DEV-DEV'

        action = wiz.action_apply()

        mgr = env.__getitem__.return_value
        rec = mgr._get_singleton.return_value
        rec.write.assert_called_once_with(
            {'license_key': 'ADMIN-NEGOCIO-2027-09-24-DEV-DEV'})
        rec._revalidate.assert_called_once_with()
        mgr.action_open_license.assert_called_once_with()
        assert action == mgr.action_open_license.return_value

    def test_apply_uses_license_manager_model(self):
        """The wizard always goes through license.manager (singleton + action)."""
        Wiz = _wizard_cls()
        env = MagicMock(name='env')
        wiz = Wiz(env=env)
        wiz.license_key = 'ODOO-ANY'

        wiz.action_apply()

        env.__getitem__.assert_any_call('license.manager')
