# -*- coding: utf-8 -*-
"""
Sistema de licencia OFFLINE para Odoo 17, usando el mismo esquema que
PosJVL: código firmado con HMAC-SHA256 + clave secreta compartida,
sin necesidad de internet ni servidor remoto.

Formato del código:
    ODOO-<PLAN>-<AAAA-MM-DD>-<INSTANCEID>-<HASH>

    PLAN        -> DIARIO, MENSUAL, TRIMESTRAL, SEMESTRAL, ANUAL
    AAAA-MM-DD  -> fecha de expiración
    INSTANCEID  -> primeros 12 caracteres del UUID de la base de datos
                   de Odoo (sin guiones), identifica a ESTA instalación
    HASH        -> primeros 8 caracteres del HMAC-SHA256

Igual que en PosJVL, sin la clave secreta no se puede generar un
código válido, aunque alguien vea el algoritmo completo (es open
source, como el resto de Odoo Community).
"""
import hmac
import hashlib
import logging
import os
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SAFEMODE y MASTER KEY — mecanismos de recovery para el desarrollador
# ---------------------------------------------------------------------------
# SAFEMODE: si existe el archivo SAFEMODE en la raíz del módulo, se saltea
#            toda verificación de licencia. No requiere reiniciar Odoo.
# MASTER KEY: si odoo.conf tiene license_lock_master_key=<valor>, se saltea
#             toda verificación de licencia. Requiere reiniciar Odoo.
#
# La desinstalación del módulo también está protegida: solo se puede
# desinstalar si hay licencia válida O algún bypass está activo.

SAFEMODE_FILENAME = 'SAFEMODE'


def _safemode_active():
    module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.exists(os.path.join(module_dir, SAFEMODE_FILENAME))


def _master_key_valid():
    return bool(config.get('license_lock_master_key'))


def _is_bypassed():
    if _safemode_active():
        _logger.info("License check BYPASSED via SAFEMODE file")
        return True
    if _master_key_valid():
        _logger.info("License check BYPASSED via master key in odoo.conf")
        return True
    return False

# ---------------------------------------------------------------------------
# CLAVE SECRETA
# ---------------------------------------------------------------------------
# IMPORTANTE: genera tu propia clave con generate_odoo_license.py --genkey
# y reemplázala aquí. Debe ser EXACTAMENTE la misma clave que uses en el
# script/servicio con el que generas los códigos para tus clientes.
#
# Usa una clave DISTINTA a la de PosJVL (SECRET_KEY de tu spec de
# licencias-api-especificacion.md). Si algún día decompilan el APK de
# PosJVL y encuentran esa clave, no quieres que eso también comprometa
# las licencias de Odoo de tus clientes.
SECRET_KEY = b"58623619674d4124b2c8e8d434c180bc52bedc9df8f3e741490117a9f884af55"

PLANES_DIAS = {
    'DIARIO': 1,
    'MENSUAL': 30,
    'TRIMESTRAL': 90,
    'SEMESTRAL': 180,
    'ANUAL': 365,
}

# Códigos de desarrollo, útiles mientras pruebas el módulo. Se aceptan
# SOLO si además el parámetro de sistema 'license_lock.allow_dev' está
# puesto en 'True' (que tú controlas por instalación, no viene activado
# por defecto). Bórralos o deja el parámetro en False antes de entregar
# el módulo a un cliente real.
DEV_CODES = [
    "ODOO-MENSUAL-2099-12-31-DEVDEVDEVDEV-DEVDEVDE",
]

# Tolerancia para el detector de retroceso de reloj. Si el reloj del
# servidor aparece más atrás que la última fecha vista menos este
# margen, se considera manipulación.
CLOCK_TOLERANCE_DAYS = 1


def _instance_short_id(env):
    """ID corto de esta instalación de Odoo, derivado del UUID de la
    base de datos que Odoo genera automáticamente. Es el equivalente
    al Android ID en PosJVL: identifica UNA instalación específica.
    """
    full_uuid = env['ir.config_parameter'].sudo().get_param('database.uuid', '')
    return full_uuid.replace('-', '').upper()[:12]


def _compute_hash(plan, fecha_str, instance_id):
    data = f"ODOO-{plan}-{fecha_str}-{instance_id}".encode('utf-8')
    return hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()[:8].upper()


def _parse_and_verify(code, instance_id, allow_dev=False):
    """Valida un código de licencia contra ESTA instalación.

    Devuelve (dict con {'plan','fecha_expiracion'}, None) si es válido,
    o (None, mensaje_error) si no.
    """
    code = (code or '').strip().upper()
    if not code:
        return None, "No hay código de licencia."

    if allow_dev and code in DEV_CODES:
        # Solo para pruebas: se acepta sin verificar hash ni instancia.
        return {'plan': code.split('-')[1], 'fecha_expiracion': date(2099, 12, 31)}, None

    parts = code.split('-')
    if len(parts) != 7 or parts[0] != 'ODOO':
        return None, "Formato de código inválido."

    _, plan, y, m, d, id_in_code, hash_recibido = parts

    if plan not in PLANES_DIAS:
        return None, "Plan de licencia desconocido."

    fecha_str = f"{y}-{m}-{d}"
    try:
        fecha_expiracion = date(int(y), int(m), int(d))
    except ValueError:
        return None, "Fecha inválida en el código."

    if id_in_code != instance_id:
        return None, "Esta licencia fue emitida para otra instalación de Odoo."

    hash_esperado = _compute_hash(plan, fecha_str, id_in_code)
    if not hmac.compare_digest(hash_recibido, hash_esperado):
        return None, "Código no autorizado (firma inválida)."

    return {'plan': plan, 'fecha_expiracion': fecha_expiracion}, None


class LicenseManager(models.Model):
    _name = 'license.manager'
    _description = 'Gestor de Licencia Mensual (offline)'
    _rec_name = 'plan'

    license_key = fields.Text(string='Código de licencia')
    instance_uuid = fields.Char(
        string='ID de esta instalación', compute='_compute_instance_uuid', store=False,
        help='Envía este código al proveedor para que te genere la licencia.')

    plan = fields.Selection([
        ('DIARIO', 'Diario (1 día)'),
        ('MENSUAL', 'Mensual (30 días)'),
        ('TRIMESTRAL', 'Trimestral (90 días)'),
        ('SEMESTRAL', 'Semestral (180 días)'),
        ('ANUAL', 'Anual (365 días)'),
    ], readonly=True)
    expires_on = fields.Date(string='Vence el', readonly=True)

    status = fields.Selection([
        ('unset', 'Sin licencia'),
        ('valid', 'Activa'),
        ('expired', 'Expirada'),
        ('invalid', 'Inválida'),
        ('clock_tampered', 'Reloj del sistema alterado'),
    ], default='unset', readonly=True, string='Estado')

    last_check = fields.Datetime(string='Última verificación', readonly=True)
    last_seen_date = fields.Date(string='Última fecha confiable vista', readonly=True)
    error_message = fields.Char(string='Detalle', readonly=True)

    def _compute_instance_uuid(self):
        for rec in self:
            full = self.env['ir.config_parameter'].sudo().get_param('database.uuid', '')
            rec.instance_uuid = full.replace('-', '').upper()[:12]

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    def action_apply_license(self):
        self.ensure_one()
        self._revalidate()
        return True

    def _revalidate(self):
        self.ensure_one()
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)

        # --- 1. Detector de retroceso de reloj -----------------------------
        last_seen = self.last_seen_date
        if last_seen and today < (last_seen - timedelta(days=CLOCK_TOLERANCE_DAYS)):
            self.write({
                'status': 'clock_tampered',
                'error_message': (
                    'La fecha del sistema retrocedió respecto a la última vez '
                    'que se verificó (%s -> %s). Revisa el reloj del servidor.'
                    % (last_seen, today)
                ),
                'last_check': now,
            })
            return

        trusted_today = max(today, last_seen) if last_seen else today

        # --- 2. Validar firma del código ------------------------------------
        instance_id = _instance_short_id(self.env)
        allow_dev = self.env['ir.config_parameter'].sudo().get_param(
            'license_lock.allow_dev', 'False') == 'True'

        data, err = _parse_and_verify(self.license_key, instance_id, allow_dev=allow_dev)

        vals = {
            'last_check': now,
            'last_seen_date': trusted_today,
        }

        if err:
            vals.update({'status': 'invalid', 'error_message': err, 'plan': False, 'expires_on': False})
            self.write(vals)
            return

        vals.update({'plan': data['plan'], 'expires_on': data['fecha_expiracion']})

        if data['fecha_expiracion'] < trusted_today:
            vals.update({
                'status': 'expired',
                'error_message': 'La licencia venció el %s.' % data['fecha_expiracion'],
            })
        else:
            vals.update({'status': 'valid', 'error_message': False})

        self.write(vals)

    @api.model
    def cron_check_license(self):
        rec = self._get_singleton()
        rec._revalidate()

    @api.model
    def is_blocked(self):
        rec = self._get_singleton()
        return rec.status not in ('valid',)
