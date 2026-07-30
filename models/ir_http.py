# -*- coding: utf-8 -*-
import time

from odoo import models
from odoo.http import request

from . import license_manager  # _safemode_active, _master_key_valid, _is_bypassed

# Rutas que SIEMPRE deben quedar accesibles, aunque el sistema esté bloqueado
ALLOWED_PREFIXES = (
    '/web/login', '/web/session', '/web/database',
    '/web/static', '/web/assets', '/website/static',
    '/license_lock',
    '/web/webclient/version_info', '/web/dataset',
    '/web/image', '/web/content',
    '/longpolling', '/bus',
)

SESSION_MAX_HOURS = 24 * 60 * 60


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        path = request.httprequest.path

        # --- BYPASS: SAFEMODE o master key saltan toda verificación ---
        if license_manager._is_bypassed():
            return super()._dispatch(endpoint)

        # Rutas permitidas siempre pasan
        if path.startswith(ALLOWED_PREFIXES):
            return super()._dispatch(endpoint)

        # Límite de sesión: 24hs
        if request.session.uid:
            login_ts = request.session.get('login_ts')
            now = time.time()
            if not login_ts:
                request.session['login_ts'] = now
            elif now - login_ts > SESSION_MAX_HOURS:
                request.session.logout(keep_db=True)
                return request.redirect('/web/login?session_expired=1')

        # Solo interceptamos /web (el escritorio)
        if path != '/web':
            return super()._dispatch(endpoint)

        # --- Verificación de licencia ---
        try:
            if request.session.uid:
                lic = request.env['license.manager'].sudo()._get_singleton()
                if lic.status != 'valid':
                    return request.redirect('/license_lock/blocked')
                if not request.session.get('license_gate_seen'):
                    return request.redirect('/license_lock/status')
        except Exception as e:
            import traceback
            _logger = __import__('logging').getLogger('license_lock')
            _logger.error("LICENSE CHECK FAILED: %s\n%s", e, traceback.format_exc())

        return super()._dispatch(endpoint)
