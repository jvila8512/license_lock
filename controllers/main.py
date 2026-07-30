# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class LicenseLockController(http.Controller):

    def _render(self, blocked):
        rec = request.env['license.manager'].sudo()._get_singleton()
        return request.render('license_lock.license_page_template', {
            'blocked': blocked,
            'status': rec.status,
            'plan': dict(rec._fields['plan'].selection).get(rec.plan) if rec.plan else False,
            'expires_on': rec.expires_on,
            'error_message': rec.error_message,
            'instance_uuid': rec.instance_uuid,
            'company_name': request.env.company.name,
            'user_name': request.env.user.name,
        })

    @http.route('/license_lock/status', type='http', auth='user', website=False)
    def status_page(self, **kwargs):
        rec = request.env['license.manager'].sudo()._get_singleton()
        if rec.status != 'valid':
            return request.redirect('/license_lock/blocked')
        request.session['license_gate_seen'] = True
        return self._render(blocked=False)

    @http.route('/license_lock/blocked', type='http', auth='user', website=False)
    def blocked_page(self, **kwargs):
        return self._render(blocked=True)

    @http.route('/license_lock/apply', type='http', auth='user', methods=['POST'], csrf=True)
    def apply_license(self, license_key=None, **kwargs):
        rec = request.env['license.manager'].sudo()._get_singleton()
        rec.write({'license_key': license_key})
        rec._revalidate()
        if rec.status == 'valid':
            request.session['license_gate_seen'] = True
            return request.redirect('/license_lock/status')
        return request.redirect('/license_lock/blocked')
