"""
Tests for license.update.wizard — the backend flow to update the license
(main form shows the code readonly; the wizard is the only write path).

On rejection the wizard returns a sticky danger notification (display_notification)
with the license form as `next`, so the user gets a LOUD message instead of a
silent bounce.
"""
from unittest.mock import MagicMock


def _wizard_cls():
    from license_lock.models.license_manager import LicenseUpdateWizard
    return LicenseUpdateWizard


def _make_wiz(status='valid', error=False, key='ODOO-ANY'):
    """Build a wizard with a mocked env; returns (wiz, mgr, rec)."""
    env = MagicMock(name='env')
    wiz = _wizard_cls()(env=env)
    wiz.license_key = key
    mgr = env.__getitem__.return_value
    rec = mgr._get_singleton.return_value
    rec.status = status
    rec.error_message = error
    return wiz, mgr, rec


class TestLicenseUpdateWizard:

    def test_apply_valid_reopens_form(self):
        """Valid key: writes, revalidates, returns the plain form action."""
        wiz, mgr, rec = _make_wiz(status='valid', key='ADMIN-NEGOCIO-2027-09-24-DEV-DEV')

        action = wiz.action_apply()

        rec.write.assert_called_once_with(
            {'license_key': 'ADMIN-NEGOCIO-2027-09-24-DEV-DEV'})
        rec._revalidate.assert_called_once_with()
        mgr.action_open_license.assert_called_once_with()
        assert action == mgr.action_open_license.return_value

    def test_apply_uses_license_manager_model(self):
        """The wizard always goes through license.manager (singleton + action)."""
        wiz, mgr, rec = _make_wiz()

        wiz.action_apply()

        env = wiz.env
        env.__getitem__.assert_any_call('license.manager')

    def test_apply_rejected_returns_danger_notification(self):
        """Rejected key: sticky danger toast + reopen form showing the error."""
        wiz, mgr, rec = _make_wiz(
            status='invalid',
            error='Código no autorizado (firma inválida).',
            key='ODOO-TRIAL-2026-10-11-2AC6AC6756D8-90CDC44DQ',
        )
        form_action = mgr.action_open_license.return_value

        action = wiz.action_apply()

        # sigue escribiendo y revalidando (queda en estado invalid)
        rec.write.assert_called_once_with(
            {'license_key': 'ODOO-TRIAL-2026-10-11-2AC6AC6756D8-90CDC44DQ'})
        rec._revalidate.assert_called_once_with()
        # pero devuelve la notificación roja, no el form a secas
        assert action['tag'] == 'display_notification'
        assert action['type'] == 'ir.actions.client'
        params = action['params']
        assert params['type'] == 'danger'
        assert params['sticky'] is True
        assert params['title'] == 'Código de licencia RECHAZADO'
        assert 'firma inválida' in params['message']
        assert params['next'] == form_action

    def test_apply_rejected_falls_back_generic_message(self):
        """If revalidation left no error text, a generic message is used."""
        wiz, mgr, rec = _make_wiz(status='invalid', error=False)

        action = wiz.action_apply()

        assert action['params']['message'] == 'El código no es válido.'
