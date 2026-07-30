# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError

from . import license_manager  # _is_bypassed


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def button_immediate_uninstall(self):
        """Protege license_lock contra desinstalación sin licencia válida.

        Solo se puede desinstalar si:
        - La licencia está activa (status == 'valid'), O
        - Algún bypass está activo (SAFEMODE o master key)
        """
        for module in self:
            if module.name == 'license_lock':
                if license_manager._is_bypassed():
                    # Bypass activo → permitir
                    continue
                lic = self.env['license.manager'].sudo()._get_singleton()
                if lic.status != 'valid':
                    raise UserError(_(
                        "No puedes desinstalar \"License Lock\" sin una licencia "
                        "válida activa. Si necesitas recuperar el acceso, creá el "
                        "archivo SAFEMODE en la raíz del módulo o agregá "
                        "license_lock_master_key en odoo.conf."
                    ))
        return super().button_immediate_uninstall()
