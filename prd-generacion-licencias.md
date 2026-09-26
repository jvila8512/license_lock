# PRD: Generación de licencias — license_lock

> Define los formatos de código de licencia, el algoritmo de generación, la validación
> del lado de Odoo y el flujo completo emisión → desbloqueo. Sirve como referencia única
> para generar licencias nuevas y para mantener el módulo.

**Estado:** vigente (Odoo 17 · módulo `license_lock`)
**Código fuente de verdad:** `models/license_manager.py`

---

## Rápido: generar una licencia de producción

1. Pedirle al cliente su **instance ID** (lo muestra la pantalla de licencia, 12 caracteres).
2. Elegir **plan** y **fecha de vencimiento**.
3. Calcular el hash con el algoritmo de la sección 2 (HMAC-SHA256, clave secreta compartida).
4. Armar el código: `ODOO-<PLAN>-<AAAA-MM-DD>-<INSTANCEID>-<HASH>` y enviárselo al cliente.

**Verificación:** el código generado contra el módulo → el estado en Odoo pasa a `valid`
y muestra los días restantes.

---

## 1. Formatos de licencia

| Formato | Ejemplo | Uso | Requiere |
|---------|---------|-----|----------|
| **Producción** | `ODOO-ANUAL-2027-09-24-ABC123DEF456-0257ABB0` | Clientes reales | Clave secreta + instance ID |
| **DEV hardcodeada** | `ADMIN-NEGOCIO-2027-09-24-DEV-DEV` | Desarrollo local | `license_lock.allow_dev=True` |
| **DEV_CODES** | `ODOO-MENSUAL-2099-12-31-DEVDEVDEVDEV-DEVDEVDE` | Testing del módulo | `license_lock.allow_dev=True` |

### 1.1 Anatomía del formato de producción

```
ODOO-MENSUAL-2026-12-31-ABC123DEF456-0257ABB0
│     │         │           │           │
│     │         │           │           └─ Hash HMAC (8 chars HEX, mayúsculas)
│     │         │           └───────────── Instance ID (12 chars)
│     │         └───────────────────────── Fecha de expiración (AAAA-MM-DD)
│     └─────────────────────────────────── Plan
└───────────────────────────────────────── Prefijo fijo ODOO
```

- **7 segmentos** separados por `-`. Cualquier otra cantidad → *"Formato de código inválido."*
- El **hash se calcula SOLO sobre** `ODOO-<PLAN>-<AAAA-MM-DD>-<INSTANCEID>` (sin el hash, obviamente).
- La fecha del código es el **vencimiento**, no la emisión.

### 1.2 Formato DEV hardcodeada

```
ADMIN-NEGOCIO-2027-09-24-DEV-DEV
│            │           │
│            │           └─ Sufijo fijo DEV-DEV
│            └────────────── Fecha de expiración (AAAA-MM-DD)
└─────────────────────────── Identificador de plan fijo
```

- **Sin firma HMAC ni instance ID:** sirve en cualquier instalación (razón por la que
  está tras el gate `allow_dev`).
- Regex exacta: `^ADMIN-NEGOCIO-(\d{4})-(\d{2})-(\d{2})-DEV-DEV$`
- Mes/día con dos dígitos obligatorios (`2027-9-24` NO matchea).

---

## 2. Algoritmo de generación (producción)

**Primeros 5 pasos en seco:**

| # | Paso | Detalle |
|---|------|---------|
| 1 | Normalizar fecha | `AAAA-MM-DD` con ceros a la izquierda (`2026-09-05`) |
| 2 | Armar el payload | `"ODOO-{plan}-{fecha}-{instance_id}"` en UTF-8 |
| 3 | Calcular HMAC | `HMAC-SHA256(secret_key, payload)` |
| 4 | Truncar | Primeros **8 caracteres** del `hexdigest`, en **MAYÚSCULAS** |
| 5 | Concatenar | `payload + "-" + hash` |

**Gotcha conocido:** el payload incluye el prefijo `ODOO-`. Olvidarlo genera un hash
que no coincide nunca — es el error más común al implementar el generador.

### 2.1 Referencia en Python (generador / verificador)

```python
import hmac, hashlib

SECRET_KEY = b"<CLAVE_SECRETA_64_HEX>"   # igual a license_manager.py

def generar_licencia(plan: str, fecha: str, instance_id: str) -> str:
    """fecha: 'AAAA-MM-DD'; instance_id: 12 chars, p.ej. 'ABC123DEF456'."""
    data = f"ODOO-{plan}-{fecha}-{instance_id}".encode("utf-8")
    h = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()[:8].upper()
    return f"{data.decode()}-{h}"

# Ejemplo:
# generar_licencia('ANUAL', '2027-09-24', 'ABC123DEF456')
#  -> 'ODOO-ANUAL-2027-09-24-ABC123DEF456-XXXXXXXX'
```

La implementación equivalente en **Dart (PosJVL)** está en `generar-licencias-odoo.md`.

### 2.2 Secret Key

- Clave **HMAC compartida**: la misma en `models/license_manager.py` y en el generador.
- **Distinta a la de PosJVL** (compromiso de una no debe comprometer la otra).
- 64 caracteres HEX (32 bytes): `python -c "import secrets; print(secrets.token_hex(32))"`.
- Nunca se expone en esta documentación ni en el repo del cliente.

---

## 3. Planes

| Plan | Duración | Constante |
|------|----------|-----------|
| `DIARIO` | 1 día | `PLANES_DIAS['DIARIO'] = 1` |
| `MENSUAL` | 30 días | `PLANES_DIAS['MENSUAL'] = 30` |
| `TRIMESTRAL` | 90 días | `PLANES_DIAS['TRIMESTRAL'] = 90` |
| `SEMESTRAL` | 180 días | `PLANES_DIAS['SEMESTRAL'] = 180` |
| `ANUAL` | 365 días | `PLANES_DIAS['ANUAL'] = 365` |

- Plan desconocido en formato producción → *"Plan de licencia desconocido."*
- `ADMIN-NEGOCIO` solo existe en el formato DEV (no está en `PLANES_DIAS`).

---

## 4. Validación del lado de Odoo

Orden exacto en `_parse_and_verify()`:

```
¿código vacío?                          → "No hay código de licencia."
¿allow_dev y está en DEV_CODES?         → OK, expira 2099-12-31
¿allow_dev y matchea regex DEV?         → OK, plan ADMIN-NEGOCIO + fecha del código
¿allow_dev=False y matchea regex DEV?   → "Código DEV deshabilitado (…)"
split('-') != 7 o prefijo != ODOO        → "Formato de código inválido."
plan fuera de PLANES_DIAS                → "Plan de licencia desconocido."
fecha ilegible (p.ej. 2026-13-40)        → "Fecha inválida en el código."
instance != instance_id local            → "…emitida para otra instalación…"
HMAC no coincide                         → "Código no autorizado (firma inválida)."
```

Después del parse, `_revalidate()` evalúa el estado final:

1. **Reloj:** si `last_seen_date` está más de 1 día adelante de hoy → `clock_tampered` (no se acepta nada).
2. **Vencimiento:** `expires_on < hoy` (día de confianza) → `expired`; si no → `valid`.
3. Cada resultado queda registrado: `status`, `last_check`, `error_message`, `last_seen_date`.

### 4.1 Cuándo se revalida

| Mecanismo | Frecuencia |
|-----------|------------|
| Al aplicar el código (formulario o botón) | manual |
| Chequeo inline al entrar a `/web` (si `expires_on < hoy` y status `valid`) | cada acceso |
| Cron `cron_check_license` | diario |

### 4.2 Gate de rutas (ir_http._dispatch)

- **Siempre accesibles:** `/web/login`, `/web/static`, `/license_lock/*`, assets, bus.
- **Solo se intercepta `/web` autenticado:** sin licencia `valid` → redirect a
  `/license_lock/blocked`; con licencia pero sin ver la pantalla de estado →
  redirect a `/license_lock/status`.
- **Sesión:** máximo 24 h; después → logout y vuelta al login.
- **Bypasses** (antes de todo lo anterior): archivo `SAFEMODE` en la raíz del módulo
  (sin reinicio) o parámetro `license_lock_master_key` en `odoo.conf` (con reinicio).

---

## 5. Flujo completo

```
1. Cliente instala license_lock  →  pantalla de licencia con su instance ID
2. Te envía el instance ID (WhatsApp)
3. Generás el código (sección 2) y se lo devolvés
4. Cliente lo pega en:
     • web:  /license_lock/status  →  "Aplicar licencia"
     • menú: Licencia → Configurar licencia  →  "Aplicar / Revalidar"
5. Odoo valida (sección 4) → status=valid  →  botón "Ir al escritorio"
6. Cron diario + chequeo en cada entrada a /web mantienen el estado al día
7. Al vencer → pantalla de bloqueo (solo login/assets/rutas de licencia siguen vivos)
```

---

## 6. Seguridad — resumen de decisiones

| Decisión | Motivo |
|----------|--------|
| HMAC-SHA256 (no SHA256 plano) | Estándar criptográfico; clave separada de los datos |
| Hash truncado a 8 HEX | Legible para el cliente; 32 bits + secreto suficiente offline |
| Instance ID embebido en el payload | La licencia no sirve en otra instalación |
| Clave secreta distinta de PosJVL | Aislar compromisos entre productos |
| Formato DEV tras gate `allow_dev` | Sin gate, cualquiera se auto-emite licencias |
| Detector de reloj atrasado | Evita borrar días cambiando la fecha del servidor |
| Código open source | La seguridad es la clave, no el algoritmo |

**Entrega a cliente:** dejar `license_lock.allow_dev=False` (o ausente) — los formatos
DEV mueren y solo acepta códigos firmados.

---

## 7. Generador en Flutter (Dart)

Código y pasos para que una app Flutter (PosJVL u otra) genere las licencias
de este módulo. Es la misma especificación que `generar-licencias-odoo.md`,
consolidada acá para tener un solo documento de referencia.

### 7.1 Dependencia

```yaml
# pubspec.yaml
dependencies:
  crypto: ^3.0.0
```

### 7.2 Código del generador

```dart
import 'dart:convert';
import 'package:crypto/crypto.dart';

/// MISMA clave que SECRET_KEY en models/license_manager.py (64 hex).
/// NUNCA reutilices la clave de PosJVL.
const String _odooSecretKey = 'CLAVE_64_HEX_IGUAL_A_license_manager';

enum PlanOdoo {
  diario('DIARIO', 1),
  mensual('MENSUAL', 30),
  trimestral('TRIMESTRAL', 90),
  semestral('SEMESTRAL', 180),
  anual('ANUAL', 365);

  final String nombre;
  final int duracionDias;
  const PlanOdoo(this.nombre, this.duracionDias);
}

/// Formato producción: ODOO-<PLAN>-<AAAA-MM-DD>-<INSTANCEID>-<HASH8>
String generarLicenciaOdoo({
  required PlanOdoo plan,
  required DateTime fechaExpiracion,
  required String instanceId,
}) {
  final fecha = '${fechaExpiracion.year.toString().padLeft(4, '0')}-'
      '${fechaExpiracion.month.toString().padLeft(2, '0')}-'
      '${fechaExpiracion.day.toString().padLeft(2, '0')}';

  // ⚠️ El payload INCLUYE el prefijo 'ODOO-' — es el error más común
  // olvidarlo: el hash nunca coincidiría.
  final payload = 'ODOO-${plan.nombre}-$fecha-$instanceId';

  final hash = Hmac(sha256, utf8.encode(_odooSecretKey))
      .convert(utf8.encode(payload))
      .toString()
      .substring(0, 8)
      .toUpperCase();

  return '$payload-$hash';
}

/// Formato DEV hardcodeable: ADMIN-NEGOCIO-<AAAA-MM-DD>-DEV-DEV
/// Solo funciona si el destino tiene license_lock.allow_dev=True.
String generarLicenciaDev({required DateTime fechaExpiracion}) {
  final fecha = '${fechaExpiracion.year.toString().padLeft(4, '0')}-'
      '${fechaExpiracion.month.toString().padLeft(2, '0')}-'
      '${fechaExpiracion.day.toString().padLeft(2, '0')}';
  return 'ADMIN-NEGOCIO-$fecha-DEV-DEV';
}

/// Instance ID: 12 chars HEX (lo muestra la pantalla de licencia de Odoo).
bool instanceIdValido(String id) =>
    RegExp(r'^[A-F0-9]{12}$').hasMatch(id.toUpperCase());
```

### 7.3 Pasos en la app

1. **Inputs del usuario:** instance ID (pegado por el cliente desde la
   pantalla de licencia), plan (dropdown con `PlanOdoo`), fecha de
   vencimiento (date picker).
2. **Validar** el instance ID con `instanceIdValido()` antes de generar.
3. **Generar** con `generarLicenciaOdoo(...)`.
4. **Enviar** el código al cliente (WhatsApp/copia al portapapeles).
5. El cliente lo pega en Odoo (`/license_lock` o menú Licencia →
   Actualizar licencia) y pasa a `valid`.

### 7.4 Reglas críticas

- [ ] La clave del generador es **idéntica** a `SECRET_KEY` de `license_manager.py`
- [ ] Clave **distinta** a la de PosJVL
- [ ] Payload **con** el prefijo `ODOO-`
- [ ] Fecha con `padLeft(2/4, '0')` → `2027-09-04`, nunca `2027-9-4`
- [ ] Hash: 8 caracteres HEX en mayúsculas
- [ ] Formato DEV solo para desarrollo (requiere `allow_dev=True` en destino)

---

## Checklist antes de emitir una licencia

- [ ] Instancia: 12 caracteres, obtenidos de la pantalla de licencia del cliente
- [ ] Plan: uno de la tabla de la sección 3
- [ ] Fecha: `AAAA-MM-DD` con ceros a la izquierda
- [ ] Payload **con** prefijo `ODOO-`
- [ ] Hash: 8 chars HEX en mayúsculas, clave correcta (la de Odoo, no la de PosJVL)
- [ ] Código armado con 7 segmentos separados por `-`

---

## Referencias

- Implementación: `models/license_manager.py` (`_parse_and_verify`, `_revalidate`, `PLANES_DIAS`)
- Gate de rutas: `models/ir_http.py` (`_dispatch`)
- Generador Dart (PosJVL): `generar-licencias-odoo.md`
- Tests: `tests/test_core.py` (formatos y crypto), `tests/test_revalidate.py` (estados)
