# License Lock - Control de Licencia para Odoo 17

Módulo Odoo 17 para control de licencia offline con firma HMAC-SHA256. Bloquea el acceso al sistema si la licencia mensual/trimestral/semestral/anual no está activa.

## Características

- Licencia firmada con HMAC-SHA256 + clave secreta, sin servidor remoto
- Atada al UUID de la base de datos de cada instalación
- Detecta manipulación del reloj del sistema
- Bloquea el backend si la licencia expira o es inválida
- Pantalla de ingreso de nuevo código de licencia

## Stack

- Odoo 17 Community
- Python 3.11+
- pytest 9.1.1 (tests)
