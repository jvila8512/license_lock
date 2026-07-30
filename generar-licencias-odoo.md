# Generar licencias Odoo desde PosJVL

> Especificación para agregar generación de licencias del módulo **license_lock** (Odoo 17) a la app **PosJVL** (Flutter Android).

---

## Tabla de contenidos

1. [Formato del código](#1-formato-del-código)
2. [Algoritmo HMAC-SHA256](#2-algoritmo-hmac-sha256)
3. [Planes disponibles](#3-planes-disponibles)
4. [Secret Key](#4-secret-key)
5. [Códigos de desarrollo](#5-códigos-de-desarrollo)
6. [Flujo de trabajo](#6-flujo-de-trabajo)
7. [Implementación en Dart](#7-implementación-en-dart)
8. [UI: selector de tipo de licencia](#8-ui-selector-de-tipo-de-licencia)
9. [Resumen de diferencias con PosJVL](#9-resumen-de-diferencias-con-posjvl)

---

## 1. Formato del código

```
ODOO-MENSUAL-2026-12-31-ABC123DEF456-0257ABB0
│     │         │           │           │
│     │         │           │           └─ Hash (8 chars HEX)
│     │         │           └───────────── Instance ID (12 chars)
│     │         └───────────────────────── Fecha expiración
│     └─────────────────────────────────── Plan
└───────────────────────────────────────── Prefijo fijo ODOO
```

| Parte | Ejemplo | Descripción |
|-------|---------|-------------|
| `ODOO` | `ODOO` | Prefijo fijo — identifica que es para Odoo |
| `PLAN` | `MENSUAL` | Ver sección 3 |
| `AAAA-MM-DD` | `2026-12-31` | Fecha de expiración |
| `INSTANCEID` | `ABC123DEF456` | Instance UUID de la instalación Odoo (12 chars, sin guiones) |
| `HASH` | `0257ABB0` | HMAC-SHA256, primeros 8 caracteres en HEX |

**Ejemplo completo:**
```
ODOO-MENSUAL-2026-12-31-ABC123DEF456-0257ABB0
```

---

## 2. Algoritmo HMAC-SHA256

Odoo usa **HMAC-SHA256** (no SHA256 plano como PosJVL). La diferencia clave: en HMAC la clave va **separada** de los datos, es el estándar criptográfico.

### 2.1 Pseudocódigo

```
data     = "ODOO-MENSUAL-2026-12-31-ABC123DEF456"   ← UTF-8
secret   = "MI_CLAVE_SECRETA"                        ← UTF-8
hash     = HMAC-SHA256(secret, data)
codigo   = data + "-" + hash.primeros_8_caracteres
```

### 2.2 Implementación en Dart

```dart
import 'dart:convert';
import 'package:crypto/crypto.dart';

// ⚠️ Usá una clave DISTINTA a la de PosJVL
const String odooSecretKey = "CAMBIA_ESTA_CLAVE_POR_UNA_PROPIA_Y_UNICA";

String generarLicenciaOdoo(
  String plan,
  DateTime fechaExpiracion,
  String instanceId,
) {
  final fechaStr = "${fechaExpiracion.year.toString().padLeft(4, '0')}-"
      "${fechaExpiracion.month.toString().padLeft(2, '0')}-"
      "${fechaExpiracion.day.toString().padLeft(2, '0')}";

  final data = utf8.encode("ODOO-$plan-$fechaStr-$instanceId");
  final key = utf8.encode(odooSecretKey);

  final hash = Hmac(sha256, key)
      .convert(data)
      .toString()
      .substring(0, 8)
      .toUpperCase();

  return "ODOO-$plan-$fechaStr-$instanceId-$hash";
}
```

---

## 3. Planes disponibles

| Nombre | Duración | Constante en Odoo |
|--------|----------|-------------------|
| `MENSUAL` | 30 días | `PLANES_DIAS['MENSUAL'] = 30` |
| `TRIMESTRAL` | 90 días | `PLANES_DIAS['TRIMESTRAL'] = 90` |
| `SEMESTRAL` | 180 días | `PLANES_DIAS['SEMESTRAL'] = 180` |
| `ANUAL` | 365 días | `PLANES_DIAS['ANUAL'] = 365` |

En la UI de PosJVL, al seleccionar "Odoo" mostrar estos planes en vez de los de PosJVL.

---

## 4. Secret Key

**IMPORTANTE**: usá una clave DISTINTA a la de PosJVL. Razón:

> Si algún día alguien decompila el APK de PosJVL y encuentra la clave de PosJVL, no querés que eso también comprometa las licencias de Odoo de tus clientes.

La clave debe ser:
- Mínimo 32 caracteres (entre más larga, mejor)
- La MISMA tanto en `license_manager.py` como en la app PosJVL
- NO compartida con PosJVL

Actualmente el módulo Odoo tiene un placeholder:
```python
SECRET_KEY = b"CAMBIA_ESTA_CLAVE_POR_UNA_PROPIA_Y_UNICA"
```

Antes de usar en producción, reemplazalo por una clave real.

### Cómo generar una clave segura

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Ejemplo: a7f3c9e1b2d4... (64 caracteres HEX)
```

---

## 5. Códigos de desarrollo

Para testing, el módulo Odoo acepta este código especial:

```
ODOO-MENSUAL-2099-12-31-DEVDEVDEVDEV-DEVDEVDE
```

Funciona solo si el parámetro `license_lock.allow_dev` está en `True` en Odoo (Configuración → Parámetros del sistema).

El instance_id `DEVDEVDEVDEV` y el hash `DEVDEVDE` son fijos — no pasan por HMAC.

---

## 6. Flujo de trabajo

```
1. Cliente instala license_lock en su Odoo
2. Cliente entra a Odoo → ve pantalla de bloqueo
         ↓
3. Cliente te envía por WhatsApp su instance_uuid
   (ej: "ABC123DEF456")
         ↓
4. Abrís PosJVL → seleccionás "Odoo" como tipo de licencia
         ↓
5. Ingresás:
   - Instance ID: "ABC123DEF456"
   - Plan: MENSUAL / TRIMESTRAL / SEMESTRAL / ANUAL
   - Vencimiento: [fecha que corresponda]
         ↓
6. PosJVL genera: ODOO-MENSUAL-2026-12-31-ABC123DEF456-0257ABB0
         ↓
7. Enviás el código al cliente por WhatsApp
         ↓
8. Cliente pega el código en la pantalla de bloqueo de Odoo
         ↓
9. Odoo valida la firma HMAC → si es correcta → desbloquea
```

---

## 7. Implementación en Dart

### 7.1 Dependencia

Agregar al `pubspec.yaml` de PosJVL:

```yaml
dependencies:
  crypto: ^3.0.0
```

### 7.2 Modelo

```dart
enum PlanOdoo {
  mensual('MENSUAL', 30),
  trimestral('TRIMESTRAL', 90),
  semestral('SEMESTRAL', 180),
  anual('ANUAL', 365);

  final String nombre;
  final int duracionDias;
  const PlanOdoo(this.nombre, this.duracionDias);
}
```

### 7.3 Servicio

```dart
import 'dart:convert';
import 'package:crypto/crypto.dart';

class OdooLicenseService {
  // ⚠️ USAR CLAVE DISTINTA A PosJVL
  static const String _secretKey = "MI_CLAVE_SECRETA_UNICA_PARA_ODOO";

  /// Genera un código de licencia para Odoo.
  static String generate({
    required PlanOdoo plan,
    required DateTime expirationDate,
    required String instanceId,
  }) {
    final fechaStr = "${expirationDate.year.toString().padLeft(4, '0')}-"
        "${expirationDate.month.toString().padLeft(2, '0')}-"
        "${expirationDate.day.toString().padLeft(2, '0')}";

    final data = utf8.encode("ODOO-${plan.nombre}-$fechaStr-$instanceId");
    final key = utf8.encode(_secretKey);

    final hash = Hmac(sha256, key)
        .convert(data)
        .toString()
        .substring(0, 8)
        .toUpperCase();

    return "ODOO-${plan.nombre}-$fechaStr-$instanceId-$hash";
  }

  /// Valida que el instance_id tenga formato correcto (12 chars HEX).
  static bool isValidInstanceId(String id) {
    return RegExp(r'^[A-F0-9]{12}$').hasMatch(id.toUpperCase());
  }
}
```

### 7.4 Uso

```dart
void main() {
  final codigo = OdooLicenseService.generate(
    plan: PlanOdoo.mensual,
    expirationDate: DateTime(2026, 12, 31),
    instanceId: "ABC123DEF456",
  );
  print(codigo); // ODOO-MENSUAL-2026-12-31-ABC123DEF456-XXXXXXX
}
```

---

## 8. UI: selector de tipo de licencia

En la pantalla de "Generar licencia" de PosJVL, agregar un toggle/segmented control:

```
┌─────────────────────────────┐
│  Tipo de licencia           │
│                             │
│  [📱 PosJVL]  [🏢 Odoo]    │
│                             │
│  ── según selección ────   │
│                             │
│  Plan:    [MENSUAL    ▼]   │
│  Vence:   [31/12/2026   ]  │
│  ID Inst: [ABC123DEF456  ] │
│                             │
│  [✨ Generar código]        │
└─────────────────────────────┘
```

Cuando está seleccionado **PosJVL**: se comporta como hasta ahora (planes FREE/NEGOCIO/PRO/MAX/MAXPRO, algoritmo SHA256, Android ID).

Cuando está seleccionado **Odoo**: muestra planes Odoo (MENSUAL/TRIMESTRAL/SEMESTRAL/ANUAL), campo "ID de instalación", algoritmo HMAC-SHA256.

---

## 9. Resumen de diferencias con PosJVL

| Aspecto | PosJVL (actual) | Odoo (nuevo) |
|---------|-----------------|--------------|
| **Prefijo** | `ADMIN` / `VENDEDOR` | `ODOO` |
| **Algoritmo** | `SHA256(data + secret)` | `HMAC-SHA256(secret, data)` |
| **Planes** | FREE, NEGOCIO, PRO, MAX, MAXPRO | MENSUAL, TRIMESTRAL, SEMESTRAL, ANUAL |
| **ID dispositivo** | Android ID (`ABC123XYZ`) | Instance UUID Odoo (`ABC123DEF456`) |
| **Secret key** | `PosJVL2024SecretKey1234` | **Una DISTINTA** |
| **Separador** | `-` | `-` (mismo) |
| **Largo hash** | 8 chars HEX | 8 chars HEX |

---

## Referencias

- Código del módulo: `models/license_manager.py`
- Tests: `tests/test_core.py`, `tests/test_revalidate.py`
- Especificación original de PosJVL: `licencias-api-especificacion.md`
