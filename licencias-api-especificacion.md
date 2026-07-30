# Sistema de Gestión de Licencias — PosJVL

> **Propósito:** Documento técnico para que un agente Python construya una app web de gestión de licencias  
> **App:** PosJVL (Flutter Android)  
> **Stack sugerido:** Python + SQLite/PostgreSQL + Flask/FastAPI + HTML/JS o React  

---

## Índice

1. [Descripción General](#1-descripción-general)
2. [Modelo de Datos](#2-modelo-de-datos)
3. [Planes (Seed Data)](#3-planes-seed-data)
4. [Algoritmo de Generación de Licencias](#4-algoritmo-de-generación-de-licencias)
5. [Algoritmo de Validación de Licencias](#5-algoritmo-de-validación-de-licencias)
6. [API de la App — Endpoints desde la App Flutter](#6-api-de-la-app--endpoints-desde-la-app-flutter)
7. [Pantallas de la Interfaz Web](#7-pantallas-de-la-interfaz-web)
8. [Flujo de Trabajo Completo](#8-flujo-de-trabajo-completo)
9. [Funcionalidades Específicas](#9-funcionalidades-específicas)
10. [Códigos de Desarrollo (DEV)](#10-códigos-de-desarrollo-dev)

---

## 1. Descripción General

El sistema de licencias permite al Super Admin vender acceso a la app PosJVL por períodos de tiempo con diferentes niveles de funcionalidad (planes). El negocio es:

> El Super Admin crea clientes → les asigna planes → genera licencias → cobra por WhatsApp → el cliente activa en su app

### Conceptos Clave

| Concepto | Descripción |
|----------|-------------|
| **Cliente** | Dueño de un negocio que compra una licencia |
| **Plan** | Nivel de servicio (FREE, NEGOCIO, PRO, MAX, MAXPRO) con precio, duración y límites |
| **Licencia** | Código único generado para un cliente + plan específico |
| **Código de licencia** | String con formato `TIPO-PLAN-FECHA-ANDROIDID-HASH` que el cliente ingresa en la app |

---

## 2. Modelo de Datos

### 2.1 Tabla: `clientes`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `nombre` | TEXT | Nombre del cliente |
| `telefono` | TEXT | Teléfono (con código de país, ej: +535XXXXXXX) |
| `negocio` | TEXT | Nombre del negocio (nullable) |
| `email` | TEXT | Email (nullable) |
| `notas` | TEXT | Notas internas (nullable) |
| `active` | BOOLEAN | `true` = activo, `false` = desactivado (soft delete) |
| `created_at` | DATETIME | Fecha de registro |

**SQL DDL:**
```sql
CREATE TABLE clientes (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL,
    negocio TEXT,
    email TEXT,
    notas TEXT,
    active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 Tabla: `license_planes`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | TEXT | Primary key (ej: "FREE", "PRO") |
| `nombre` | TEXT | Nombre del plan |
| `precio` | REAL | Precio en CUP |
| `descripcion` | TEXT | Descripción del plan (nullable) |
| `dias_duracion` | INTEGER | Duración en días |
| `max_productos` | INTEGER | Máximo de productos permitidos |
| `max_vendedores` | INTEGER | Máximo de vendedoras permitidas |
| `activa` | BOOLEAN | `true` = disponible, `false` = desactivado |

**SQL DDL:**
```sql
CREATE TABLE license_planes (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    precio REAL NOT NULL,
    descripcion TEXT,
    dias_duracion INTEGER NOT NULL,
    max_productos INTEGER NOT NULL,
    max_vendedores INTEGER NOT NULL,
    activa BOOLEAN NOT NULL DEFAULT 1
);
```

### 2.3 Tabla: `licencias_cliente`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `cliente_id` | TEXT | Foreign key → `clientes.id` |
| `codigo` | TEXT | Código de licencia completo (único) |
| `plan` | TEXT | Nombre del plan (FREE, PRO, etc.) |
| `fecha_creacion` | DATETIME | Fecha de creación de la licencia |
| `fecha_expiracion` | DATETIME | Fecha de expiración |
| `fecha_cancelacion` | DATETIME | Fecha de cancelación (nullable) |
| `estado` | TEXT | `activa`, `vencida`, `cancelada` |
| `precio_pagado` | REAL | Precio que pagó el cliente |
| `dispositivo_id` | TEXT | Android ID del dispositivo (nullable, se llena al activar) |
| `notas` | TEXT | Notas internas (nullable) |
| `created_at` | DATETIME | Fecha de registro |

**SQL DDL:**
```sql
CREATE TABLE licencias_cliente (
    id TEXT PRIMARY KEY,
    cliente_id TEXT NOT NULL,
    codigo TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL,
    fecha_creacion DATETIME NOT NULL,
    fecha_expiracion DATETIME NOT NULL,
    fecha_cancelacion DATETIME,
    estado TEXT NOT NULL DEFAULT 'activa',
    precio_pagado REAL NOT NULL DEFAULT 0,
    dispositivo_id TEXT,
    notas TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);
```

### Diagrama de Relaciones

```
clientes (1) ──── (N) licencias_cliente
                              │
                              │ plan
                              ▼
                        license_planes
```

---

## 3. Planes (Seed Data)

Estos son los 5 planes que se crean al inicializar la base de datos:

| Nombre | Precio (CUP) | Duración | Max Productos | Max Vendedores |
|--------|:-----------:|:--------:|:------------:|:--------------:|
| **FREE** | $0 | 15 días | 100 | 1 |
| **NEGOCIO** | $3,000 | 31 días | 100 | 1 |
| **PRO** | $8,000 | 90 días | 200 | 2 |
| **MAX** | $16,000 | 180 días | 300 | 3 |
| **MAXPRO** | $30,000 | 365 días | 1000 | 5 |

**SQL Seed:**
```sql
INSERT INTO license_planes (id, nombre, precio, descripcion, dias_duracion, max_productos, max_vendedores, activa) VALUES
('FREE', 'FREE', 0, 'Plan gratuito - 15 días de prueba', 15, 100, 1, 1),
('NEGOCIO', 'NEGOCIO', 3000, 'Plan negocio - 31 días', 31, 100, 1, 1),
('PRO', 'PRO', 8000, 'Plan profesional - 90 días', 90, 200, 2, 1),
('MAX', 'MAX', 16000, 'Plan máximo - 180 días', 180, 300, 3, 1),
('MAXPRO', 'MAXPRO', 30000, 'Plan máximo pro - 365 días', 365, 1000, 5, 1);
```

---

## 4. Algoritmo de Generación de Licencias

### 4.1 Formato del Código

```
TIPO-PLAN-AAAA-MM-DD-ANDROIDID-HASH
```

Donde:
| Parte | Ejemplo | Descripción |
|-------|---------|-------------|
| `TIPO` | `ADMIN` | Tipo de usuario (ADMIN, VENDEDOR) |
| `PLAN` | `PRO` | Nombre del plan |
| `AAAA-MM-DD` | `2027-12-31` | Fecha de expiración |
| `ANDROIDID` | `ABC123XYZ` | Identificador del dispositivo Android |
| `HASH` | `0A07ABA4` | Hash SHA256 (primeros 8 caracteres) |

**Ejemplo de código generado:**
```
ADMIN-PRO-2027-12-31-ABC123XYZ-0A07ABA4
```

### 4.2 Secret Key

La clave secreta para generar el hash es:

```
PosJVL2024SecretKey1234
```

### 4.3 Algoritmo Paso a Paso

```python
import hashlib
from datetime import datetime

SECRET_KEY = "PosJVL2024SecretKey1234"

def generate_license_code(tipo: str, plan: str, fecha_expiracion: datetime, android_id: str) -> str:
    """
    Genera un código de licencia para un dispositivo específico.
    
    Args:
        tipo: Tipo de usuario (ADMIN, VENDEDOR)
        plan: Nombre del plan (FREE, NEGOCIO, PRO, MAX, MAXPRO)
        fecha_expiracion: Fecha de expiración de la licencia
        android_id: Android ID del dispositivo destino
    
    Returns:
        Código de licencia completo: TIPO-PLAN-AAAA-MM-DD-ANDROIDID-HASH
    """
    # 1. Formatear fecha como AAAA-MM-DD
    fecha_str = fecha_expiracion.strftime('%Y-%m-%d')
    
    # 2. Crear string para hashear
    data_to_hash = f"{tipo.upper()}-{plan.upper()}-{fecha_str}-{android_id.upper()}-{SECRET_KEY}"
    
    # 3. Generar hash SHA256 y tomar primeros 8 caracteres
    hash_obj = hashlib.sha256(data_to_hash.encode('utf-8'))
    hash_result = hash_obj.hexdigest()[:8].upper()
    
    # 4. Armar código completo
    codigo = f"{tipo.upper()}-{plan.upper()}-{fecha_str}-{android_id.upper()}-{hash_result}"
    
    return codigo
```

### 4.4 Notas Importantes

- El `android_id` se obtiene del dispositivo destino. Si no se conoce, se puede preguntar al cliente o pedirle que lo envíe.
- El hash verifica INTEGRIDAD y AUTENTICIDAD del código — sin el secret key, no se puede generar un código válido.
- Los códigos de desarrollo (DEV) usan `DEV` como android_id y son válidos sin verificación de hash (ver sección 10).

---

## 5. Algoritmo de Validación de Licencias

La validación ocurre en la app Flutter, pero acá está el algoritmo completo para que el backend pueda verificar si un código es válido:

```python
import hashlib
from datetime import datetime

SECRET_KEY = "PosJVL2024SecretKey1234"

# Códigos de desarrollo que siempre son válidos
DEV_CODES = [
    "ADMIN-FREE-2027-12-31-DEV-DEV",
    "ADMIN-NEGOCIO-2099-12-31-DEV-DEV",
    "ADMIN-PRO-2027-12-31-DEV-DEV",
    "VENDEDOR-PRO-2027-12-31-DEV-DEV",
    "ADMIN-MAX-2027-12-31-DEV-DEV",
    "ADMIN-MAXPRO-2027-12-31-DEV-DEV",
]

TIPOS_VALIDOS = ["ADMIN", "VENDEDOR", "ALMACENERO"]
PLANES_VALIDOS = ["FREE", "NEGOCIO", "PRO", "MAX", "MAXPRO"]


def validate_license(code: str, device_android_id: str = None) -> dict:
    """
    Valida un código de licencia.
    
    Returns:
        dict con: { "is_valid": bool, "is_expired": bool, 
                    "tipo": str, "plan": str, 
                    "fecha_expiracion": datetime,
                    "error_message": str }
    """
    parts = code.strip().upper().split('-')
    
    # Formato mínimo: TIPO-PLAN-FECHA-ANDROIDID-HASH (6+ partes)
    if len(parts) < 6:
        return {"is_valid": False, "error_message": "Código inválido"}
    
    tipo, plan = parts[0], parts[1]
    fecha_str = f"{parts[2]}-{parts[3]}-{parts[4]}"
    android_id_in_code = parts[5]
    hash_recibido = parts[6] if len(parts) > 6 else ""
    
    # Validar tipo
    if tipo not in TIPOS_VALIDOS:
        return {"is_valid": False, "error_message": "Tipo de licencia inválido"}
    
    # Validar plan
    if plan not in PLANES_VALIDOS:
        return {"is_valid": False, "error_message": "Plan de licencia inválido"}
    
    # Validar fecha
    try:
        fecha_vencimiento = datetime.strptime(fecha_str, "%Y-%m-%d")
    except ValueError:
        return {"is_valid": False, "error_message": "Fecha inválida"}
    
    if fecha_vencimiento < datetime.now():
        return {"is_valid": False, "is_expired": True, "error_message": "Licencia vencida"}
    
    # Si es código DEV, validar contra lista
    if code.strip().upper() in DEV_CODES:
        return {
            "is_valid": True,
            "tipo": tipo,
            "plan": plan,
            "fecha_expiracion": fecha_vencimiento,
        }
    
    # Verificar dispositivo
    if device_android_id and android_id_in_code != device_android_id.upper():
        return {"is_valid": False, "error_message": "Esta licencia no corresponde a este dispositivo"}
    
    # Verificar hash
    data_to_hash = f"{tipo}-{plan}-{fecha_str}-{android_id_in_code}-{SECRET_KEY}"
    hash_esperado = hashlib.sha256(data_to_hash.encode('utf-8')).hexdigest()[:8].upper()
    
    if hash_recibido != hash_esperado:
        return {"is_valid": False, "error_message": "Código no autorizado"}
    
    return {
        "is_valid": True,
        "tipo": tipo,
        "plan": plan,
        "fecha_expiracion": fecha_vencimiento,
    }
```

---

## 6. API de la App — Endpoints desde la App Flutter

La app Flutter necesita que el backend exponga estos endpoints:

### 6.1 Validar Licencia

```
POST /api/licencias/validar

Request:
{
    "codigo": "ADMIN-PRO-2027-12-31-ABC123-0A07ABA4",
    "dispositivo_id": "ABC123XYZ"   // Android ID
}

Response (válida):
{
    "is_valid": true,
    "plan": "PRO",
    "fecha_expiracion": "2027-12-31",
    "limites": {
        "max_productos": 200,
        "max_vendedores": 2
    }
}

Response (inválida):
{
    "is_valid": false,
    "error_message": "Código no autorizado"
}

Response (vencida):
{
    "is_valid": false,
    "is_expired": true,
    "error_message": "Licencia vencida",
    "fecha_expiracion": "2026-01-15"
}
```

### 6.2 Obtener Planes Disponibles

```
GET /api/planes

Response:
{
    "planes": [
        {
            "id": "PRO",
            "nombre": "PRO",
            "precio": 8000,
            "descripcion": "Plan profesional - 90 días",
            "dias_duracion": 90,
            "max_productos": 200,
            "max_vendedores": 2
        },
        ...
    ]
}
```

### 6.3 Generar Licencia (uso del Super Admin)

```
POST /api/licencias/generar

Request:
{
    "cliente_id": "uuid-del-cliente",
    "plan": "PRO",
    "tipo": "ADMIN",
    "dispositivo_id": "ABC123XYZ",   // opcional, puede ir después
    "precio_pagado": 8000
}

Response:
{
    "licencia_id": "uuid",
    "codigo": "ADMIN-PRO-2027-12-31-ABC123-0A07ABA4",
    "fecha_creacion": "2026-06-21",
    "fecha_expiracion": "2026-09-19",
    "plan": "PRO",
    "precio_pagado": 8000
}
```

### 6.4 Renovar Licencia

```
POST /api/licencias/renovar

Request:
{
    "licencia_id": "uuid",
    "nuevo_plan": "MAX",     // opcional (puede subir de plan)
    "dias_extension": 90,    // días a agregar
    "precio_pagado": 16000
}

Response:
{
    "licencia_id": "uuid",
    "codigo": "ADMIN-MAX-2027-03-21-ABC123-NUEVOHASH",
    "nueva_fecha_expiracion": "2027-03-21"
}
```

### 6.5 Cancelar Licencia

```
POST /api/licencias/cancelar

Request:
{
    "licencia_id": "uuid"
}

Response:
{
    "success": true,
    "estado": "cancelada",
    "fecha_cancelacion": "2026-06-21"
}
```

### 6.6 Enviar Código por WhatsApp

```
POST /api/licencias/enviar-whatsapp

Request:
{
    "licencia_id": "uuid",
    "telefono": "+535XXXXXXX"
}

Response:
{
    "success": true,
    "mensaje": "Código enviado por WhatsApp"
}
```

Nota: este endpoint abre `https://wa.me/{telefono}?text={mensaje}` donde el mensaje contiene el código de licencia, el plan, y la fecha de expiración.

---

## 7. Pantallas de la Interfaz Web

La app web debe tener 4 secciones principales (como el Super Admin en la app Flutter), idealmente con tabs o navegación lateral:

### 7.1 Dashboard (Inicio)

**Qué muestra:**
- **Cards de estadísticas:**
  - Licencias activas (conteo)
  - Licencias vencidas (conteo)
  - Ingresos totales (suma de precios pagados de todas las licencias activas)
  - Clientes registrados (conteo)
- **Licencias por estado:** Activas / Vencidas / Canceladas (conteo visual)
- **Próximas a vencer:** Lista de licencias que expiran en los próximos 7 días (con cliente, plan, fecha)
- **Licencias recientes:** Últimas 5 licencias creadas

**Acciones:** Ninguna (es informativo).

### 7.2 Clientes (CRUD)

**Funcionalidades:**
- Lista de clientes con: nombre, teléfono, negocio, fecha de registro
- Buscador por nombre o teléfono
- **Crear nuevo cliente:** formulario con nombre, teléfono, negocio (opcional), email (opcional), notas (opcional)
- **Editar cliente:** modificar datos existentes
- **Desactivar/Reactivar cliente:** soft delete (el historial se conserva)

**Detalles:**
- Al desactivar un cliente, se oculta de los listados principales pero el historial de licencias se mantiene
- Un cliente desactivado no puede recibir nuevas licencias

### 7.3 Planes de Precios (CRUD)

**Funcionalidades:**
- Lista de planes con: nombre, precio, duración, máx. productos, máx. vendedores
- **Crear nuevo plan:** nombre, precio, descripción, duración (días), máx. productos, máx. vendedores
- **Editar plan:** precio, descripción, duración, límites
- **Activar/Desactivar plan:** un plan desactivado no se puede asignar a nuevas licencias

**Validaciones:**
- El nombre del plan debe ser único
- Si se desactiva un plan, las licencias existentes con ese plan siguen activas

### 7.4 Licencias (Gestión)

**Funcionalidades:**
- **Lista completa** con buscador (por cliente) y filtros (Todas / Activas / Vencidas / Canceladas)
- **Paginación** (20 licencias por página)
- **Estadísticas en cabecera:** Total, Activas, Vencidas, Canceladas
- **Crear licencia:**
  1. Seleccionar cliente (dropdown con búsqueda)
  2. Seleccionar plan
  3. Opcional: Android ID del dispositivo
  4. Opcional: precio personalizado (por defecto el precio del plan)
  5. Generar código → mostrar en pantalla + enviar por WhatsApp con link directo
- **Ver detalle de licencia:** popup o página con:
  - Código de licencia completo
  - Cliente (nombre, teléfono)
  - Plan
  - Fecha de creación, expiración
  - Estado (activa/vencida/cancelada)
  - Fecha de cancelación (si aplica)
  - Precio pagado
  - Dispositivo ID (si se activó)
  - Notas
- **Cancelar licencia:** confirmación → cambia estado a `cancelada` y registra fecha
- **Renovar licencia:**
  1. Seleccionar nuevo plan (opcional, puede mantener el mismo)
  2. Ingresar días de extensión
  3. Ingresar precio pagado
  4. Se genera NUEVO código de licencia
  5. Se actualiza la fecha de expiración
- **Enviar por WhatsApp:** botón que abre WhatsApp con el código pre-escrito

---

## 8. Flujo de Trabajo Completo

### 8.1 Crear Cliente + Licencia (desde 0)

```
1. Super Admin entra a la web
2. Va a "Clientes" → "Nuevo Cliente"
3. Completa: nombre, teléfono, negocio
4. Guarda → cliente creado
5. Va a "Licencias" → "Nueva Licencia"
6. Selecciona el cliente recién creado
7. Selecciona plan "PRO"
8. Opcional: ingresa Android ID del dispositivo del cliente
9. Toca "Generar Licencia"
10. Sistema:
    a. Genera código: ADMIN-PRO-2026-09-19-ANDROIDID-HASH
    b. Guarda en BD
    c. Muestra el código en pantalla
11. Toca "Enviar por WhatsApp"
12. Se abre WhatsApp con el código listo para enviar al cliente
```

### 8.2 Cliente Activa en su App

```
1. Cliente abre PosJVL en su Android
2. Va a "Activar Licencia"
3. Ingresa el código que recibió por WhatsApp
4. App valida el código (contra la BD local o API)
5. App guarda: fecha de activación, código, plan
6. ¡App lista para usar!
```

### 8.3 Renovar Licencia Vencida

```
1. Cliente contacta al Super Admin
2. Super Admin busca la licencia en "Licencias"
3. Toca "Renovar"
4. Selecciona plan (puede subir de plan)
5. Ingresa días y precio
6. Sistema genera nuevo código y actualiza fecha
7. Envía por WhatsApp al cliente
8. Cliente ingresa el nuevo código en la app
```

### 8.4 Cancelar Licencia (por impago, etc.)

```
1. Super Admin busca la licencia
2. Toca "Cancelar"
3. Confirma la cancelación
4. Sistema cambia estado a "cancelada" y registra fecha
5. La app del cliente ya no puede validar la licencia
```

---

## 9. Funcionalidades Específicas

### 9.1 Envío por WhatsApp

Cuando el Super Admin hace clic en "Enviar por WhatsApp", se abre un link con:

```
https://wa.me/{telefono_cliente}?text={mensaje_codificado}
```

El mensaje debe contener:
```
🎉 ¡Licencia PosJVL activada!

📋 Plan: PRO
📅 Vence: 19/09/2026
🔑 Código: ADMIN-PRO-2026-09-19-ABC123-0A07ABA4

📲 Ingresá este código en tu app PosJVL para activarla.
```

### 9.2 Cancelación de Licencia

- Una licencia cancelada NO se puede reactivar
- El cliente ya no puede usar la app con ese código
- La cancelación es irreversible
- Se registra `fecha_cancelacion` y estado `cancelada`

### 9.3 Renovación

- Al renovar, se genera un NUEVO código de licencia
- El nuevo código se guarda en la misma licencia (UPDATE)
- La fecha de expiración se extiende desde la fecha actual + días

### 9.4 Cálculo de Ingresos Totales

```python
def calcular_ingresos_totales():
    """
    Suma el precio_pagado de todas las licencias con estado 'activa'
    """
    total = db.execute(
        "SELECT SUM(precio_pagado) FROM licencias_cliente WHERE estado = 'activa'"
    ).fetchone()[0]
    return total or 0
```

### 9.5 Licencias Próximas a Vencer

```python
def get_licencias_proximas_a_vencer(dias=7):
    """
    Devuelve licencias que expiran en los próximos N días
    """
    from datetime import datetime, timedelta
    hoy = datetime.now()
    limite = hoy + timedelta(days=dias)
    
    return db.execute("""
        SELECT l.*, c.nombre as cliente_nombre, c.telefono 
        FROM licencias_cliente l
        JOIN clientes c ON l.cliente_id = c.id
        WHERE l.estado = 'activa'
        AND l.fecha_expiracion BETWEEN ? AND ?
        ORDER BY l.fecha_expiracion ASC
    """, (hoy, limite)).fetchall()
```

---

## 10. Códigos de Desarrollo (DEV)

Para pruebas y desarrollo, existen códigos especiales que **siempre son válidos** sin importar el hash:

```python
DEV_CODES = [
    "ADMIN-FREE-2027-12-31-DEV-DEV",      # Admin, plan FREE, hasta 2027
    "ADMIN-NEGOCIO-2099-12-31-DEV-DEV",    # Admin, plan NEGOCIO, hasta 2099
    "ADMIN-PRO-2027-12-31-DEV-DEV",        # Admin, plan PRO, hasta 2027
    "VENDEDOR-PRO-2027-12-31-DEV-DEV",     # Vendedor, plan PRO
    "ADMIN-MAX-2027-12-31-DEV-DEV",        # Admin, plan MAX
    "ADMIN-MAXPRO-2027-12-31-DEV-DEV",     # Admin, plan MAXPRO
]
```

Cuando se valida un código DEV, se salta:
- Verificación de hash
- Verificación de Android ID
- Solo se verifica que el código esté en la lista

---

## Notas Técnicas para el Desarrollador Python

1. **Framework sugerido:** FastAPI (liviano, async, documentación automática)
2. **Base de datos:** SQLite para desarrollo (fácil), PostgreSQL para producción
3. **ORM sugerido:** SQLAlchemy + Alembic para migraciones
4. **WhatsApp:** Usar `https://wa.me/{telefono}?text={mensaje}` (no requiere API de WhatsApp Business)
5. **UUID:** Generar con `uuid.uuid4()` para IDs
6. **Fechas:** Siempre almacenar en UTC, convertir a local para mostrar
7. **Validación:** El algoritmo SHA256 está en la app Flutter — debe coincidir EXACTAMENTE
8. **Formato del código:** `TIPO-PLAN-AAAA-MM-DD-ANDROIDID-HASH` — no cambiar el separador `-`

---

*Documento generado para el desarrollo de un sistema de gestión de licencias en Python.*  
*PosJVL — Sistema POS para Pequeños Negocios © 2026*
