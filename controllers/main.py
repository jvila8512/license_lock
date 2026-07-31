# -*- coding: utf-8 -*-
from datetime import date

from odoo import http
from odoo.http import request


class LicenseLockController(http.Controller):

    def _render(self, blocked):
        rec = request.env['license.manager'].sudo()._get_singleton()
        today = date.today()
        days_remaining = False
        if rec.expires_on:
            delta = rec.expires_on - today
            days_remaining = delta.days  # positivo = quedan, negativo = vencida hace X

        return request.render('license_lock.license_page_template', {
            'blocked': blocked,
            'status': rec.status,
            'plan': dict(rec._fields['plan'].selection).get(rec.plan) if rec.plan else False,
            'plan_code': rec.plan,
            'expires_on': rec.expires_on,
            'days_remaining': days_remaining,
            'license_key': rec.license_key,
            'error_message': rec.error_message,
            'instance_uuid': rec.instance_uuid,
            'company_name': request.env.company.name,
            'user_name': request.env.user.name,
        })

    @http.route('/license_lock/status', type='http', auth='user', website=False)
    def status_page(self, **kwargs):
        """Pantalla de estado de licencia. Muestra días restantes y formulario
        para actualizar. Siempre accesible, incluso si la licencia expiró."""
        rec = request.env['license.manager'].sudo()._get_singleton()
        request.session['license_gate_seen'] = True
        return self._render(blocked=False)

    @http.route('/license_lock/blocked', type='http', auth='user', website=False)
    def blocked_page(self, **kwargs):
        """Pantalla de bloqueo total. No deja pasar a /web."""
        return self._render(blocked=True)

    @http.route('/license_lock/apply', type='http', auth='user', methods=['POST'], csrf=True)
    def apply_license(self, license_key=None, **kwargs):
        rec = request.env['license.manager'].sudo()._get_singleton()
        rec.write({'license_key': license_key})
        rec._revalidate()
        if rec.status == 'valid':
            request.session['license_gate_seen'] = True
        return request.redirect('/license_lock/status')
