# -*- coding: utf-8 -*-
{
    'name': 'License Lock - Control de Licencia Mensual',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'Bloquea el sistema si la licencia mensual no está activa',
    'description': """
Módulo de control de licencia mensual/trimestral/semestral/anual para
instalaciones de Odoo 17 sin acceso a internet.

- Licencia firmada con HMAC-SHA256 + clave secreta (mismo esquema que
  PosJVL), sin necesidad de servidor remoto.
- Atada al UUID de la base de datos de esta instalación: una licencia
  no sirve en otra instancia.
- Detecta manipulación del reloj del sistema.
- Bloquea el acceso al backend si la licencia expira o es inválida,
  dejando accesible únicamente la pantalla para introducir un nuevo
  código.
""",
    'author': 'Javier',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/license_views.xml',
        'views/templates.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
