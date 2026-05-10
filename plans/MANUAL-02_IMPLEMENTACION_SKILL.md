# MANUAL 2: Implementación Completa de una Skill desde Cero

> **Propósito:** Este manual explica el proceso completo para implementar una nueva skill en el sistema Propifai, desde la planificación hasta la ejecución y monitoreo en producción.
>
> **Público:** Desarrolladores que necesitan agregar nuevas capacidades al sistema de skills.

---

## Índice

1. [Visión General del Sistema](#1-visión-general-del-sistema)
2. [Arquitectura del Sistema de Skills](#2-arquitectura-del-sistema-de-skills)
3. [Flujo de Trabajo Completo](#3-flujo-de-trabajo-completo)
4. [Paso 1: Planificar la Skill](#4-paso-1-planificar-la-skill)
5. [Paso 2: Escribir el Código Python](#5-paso-2-escribir-el-código-python)
6. [Paso 3: Crear la Skill en el Dashboard](#6-paso-3-crear-la-skill-en-el-dashboard)
7. [Paso 4: Probar la Skill](#7-paso-4-probar-la-skill)
8. [Paso 5: Monitorear la Skill](#8-paso-5-monitorear-la-skill)
9. [Método Alternativo: Crear Archivo Directamente](#9-método-alternativo-crear-archivo-directamente)
10. [Integración con el Chat Inteligente](#10-integración-con-el-chat-inteligente)
11. [Integración con la API REST](#11-integración-con-la-api-rest)
12. [Manejo de Cache](#12-manejo-de-cache)
13. [Seguridad y Permisos](#13-seguridad-y-permisos)
14. [Solución de Problemas](#14-solución-de-problemas)

---

## 1. Visión General del Sistema

El sistema de skills de Propifai es un **motor de capacidades autónomas** que permite:

- **Ejecutar lógica de negocio** de forma estandarizada
- **Ser invocado desde múltiples canales:** Dashboard web, Chat IA, API REST, MCP
- **Auto-descubrimiento:** Las skills se registran automáticamente al crearse
- **Cache inteligente:** Resultados frecuentes se cachean en Redis o memoria local
- **Métricas y monitoreo:** Cada ejecución se registra con latencia, estado y metadata

### Canales de invocación:

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Dashboard   │────▶│                  │     │              │
│  (Web UI)    │     │   SkillOrchestrator │────▶│   Skill      │
├─────────────┤     │                  │     │   (Python)   │
│  Chat IA     │────▶│  (Motor central) │     │              │
│  (DeepSeek)  │     │                  │     └──────────────┘
├─────────────┤     └──────────────────┘
│  API REST    │────▶
│  (DRF/JSON)  │
├─────────────┤
│  MCP Server  │────▶
└─────────────┘
```

---

## 2. Arquitectura del Sistema de Skills

### Estructura de directorios:

```
webapp/intelligence/
├── services/
│   ├── skill_base.py          ← Clases base (Skill, SkillParameter, SkillResult, SkillRegistry)
│   ├── __init__.py
│   └── ...
├── skills/
│   ├── __init__.py            ← Auto-descubrimiento y create_skill_system()
│   ├── registry.py            ← DynamicSkillRegistry (descubrimiento dinámico)
│   ├── orchestrator.py        ← SkillOrchestrator (ejecución, cache, métricas)
│   ├── cache.py               ← SkillCache (Redis + local)
│   ├── acm_analisis.py        ← Skill: Análisis financiero ACM
│   ├── reporte_precios.py     ← Skill: Reporte de precios por zona
│   ├── matching.py            ← Skill: Matching oferta-demanda
│   ├── busqueda_exacta.py     ← Skill: Búsqueda exacta de propiedades
│   └── examples/
│       ├── __init__.py
│       └── math_skills.py     ← Skills de ejemplo (suma, resta, etc.)
├── models.py                  ← SkillExecution (modelo de persistencia)
├── views.py                   ← Vistas del dashboard de skills
├── urls.py                    ← URLs del dashboard
├── serializers.py             ← SkillExecutionSerializer
├── templates/intelligence/
│   ├── skills_dashboard.html  ← Dashboard principal
│   ├── skills_detail.html     ← Detalle de skill
│   ├── skills_create.html     ← Crear/editar skill
│   ├── skills_metrics.html    ← Métricas avanzadas
│   └── skills_logs.html       ← Logs de ejecución
└── static/intelligence/
    ├── css/skills_dashboard.css
    └── js/skills_dashboard.js, skills_metrics.js
```

### Componentes clave:

| Componente | Archivo | Función |
|---|---|---|
| `Skill` (ABC) | `services/skill_base.py` | Clase base que deben heredar todas las skills |
| `SkillParameter` | `services/skill_base.py` | Definición de parámetros de entrada |
| `SkillResult` | `services/skill_base.py` | Resultado estandarizado |
| `DynamicSkillRegistry` | `skills/registry.py` | Descubre y registra skills automáticamente |
| `SkillOrchestrator` | `skills/orchestrator.py` | Orquesta ejecución con cache y métricas |
| `SkillCache` | `skills/cache.py` | Cache en Redis + memoria local |
| `SkillExecution` | `models.py` | Persistencia de ejecuciones en BD |
| Dashboard views | `views.py` | CRUD + dashboard + métricas |

---

## 3. Flujo de Trabajo Completo

```
1. PLANIFICAR
   │
   ├─ ¿Qué problema resuelve?
   ├─ ¿Qué parámetros necesita?
   ├─ ¿Qué datos retorna?
   └─ ¿Quién puede usarla? (nivel de acceso)
   │
   ▼
2. ESCRIBIR CÓDIGO
   │
   ├─ Seguir la arquitectura del Manual 1
   ├─ Usar el template mínimo
   ├─ Probar lógica localmente
   └─ Verificar con el checklist
   │
   ▼
3. CREAR EN DASHBOARD
   │
   ├─ Ir a /api/v1/intelligence/skills/create/
   ├─ Llenar: nombre, descripción, categoría, nivel
   ├─ Pegar código Python en el editor
   └─ Click "Crear Skill"
   │
   ▼
4. VERIFICAR
   │
   ├─ ¿Aparece en el dashboard?
   ├─ Probar ejecución desde el detalle
   ├─ Verificar logs de ejecución
   └─ Probar desde el chat IA
   │
   ▼
5. MONITOREAR
   │
   ├─ Revisar métricas en /metrics/
   ├─ Revisar logs en /logs/
   ├─ Verificar latencia y errores
   └─ Ajustar si es necesario
```

---

## 4. Paso 1: Planificar la Skill

Antes de escribir código, define:

### Ficha de planificación:

```yaml
Nombre: "mi_nueva_skill"
Descripción: "Calcula el precio promedio por m2 para una zona específica"
Categoría: "analysis" | "query" | "utility" | "data" | "integration"
Nivel requerido: 1 (Básico) | 2 (Intermedio) | 3 (Avanzado) | 4 (Admin) | 5 (Super Admin)

Parámetros de entrada:
  - nombre: "zona"
    tipo: "str"
    descripción: "Nombre del distrito o zona"
    requerido: true
  - nombre: "tipo_propiedad"
    tipo: "str"
    descripción: "Tipo de propiedad (Departamento, Casa, Terreno)"
    requerido: true
    opciones: ["Departamento", "Casa", "Terreno"]
  - nombre: "incluir_grafico"
    tipo: "bool"
    descripción: "Si debe incluir gráfico en el resultado"
    requerido: false
    default: false

Datos de retorno:
  - precio_promedio: float
  - cantidad_registros: int
  - zonas_encontradas: list
  - recomendacion: str
```

### Categorías disponibles:

| Categoría | Descripción | Ejemplos |
|---|---|---|
| `query` | Consultas y búsquedas | `busqueda_exacta`, `matching_oferta_demanda` |
| `analysis` | Análisis y cálculos | `acm_analisis`, `reporte_precios_zona` |
| `utility` | Utilidades generales | `suma`, `resta`, `estadisticas_basicas` |
| `data` | Procesamiento de datos | Importación, transformación |
| `integration` | Integraciones externas | APIs, webhooks |

### Niveles de acceso:

| Nivel | Nombre | Quién lo tiene |
|---|---|---|
| 1 | Básico | Todos los usuarios autenticados |
| 2 | Intermedio | Usuarios con rol intermedio |
| 3 | Avanzado | Usuarios avanzados |
| 4 | Admin | Administradores del sistema |
| 5 | Super Admin | Super administradores |

---

## 5. Paso 2: Escribir el Código Python

Sigue las instrucciones detalladas del [`MANUAL-01_ARQUITECTURA_CODIGO_SKILL.md`](MANUAL-01_ARQUITECTURA_CODIGO_SKILL.md).

### Resumen rápido:

```python
"""
[Descripción de la skill]
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class MiSkill(Skill):
    name = "mi_skill"
    description = "Descripción para el LLM"
    parameters = {
        'param1': SkillParameter(
            name='param1', type='str',
            description='...', required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            # Lógica aquí
            return SkillResult.ok(data={'resultado': ...})
        except Exception as e:
            return SkillResult.from_error(str(e))
```

### Prueba local del código (opcional pero recomendado):

Puedes probar tu skill localmente antes de subirla al dashboard:

```python
# test_mi_skill.py
import sys
sys.path.insert(0, 'webapp')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.skills.mi_skill import MiSkill

skill = MiSkill()
resultado = skill.execute(param1="valor")
print(f"Éxito: {resultado.success}")
print(f"Datos: {resultado.data}")
```

O ejecutar desde el shell de Django:

```bash
cd webapp
python manage.py shell
```

```python
from intelligence.skills.mi_skill import MiSkill
skill = MiSkill()
result = skill.execute(param1="test")
print(result)
```

---

## 6. Paso 3: Crear la Skill en el Dashboard

### Acceder al formulario de creación:

1. Abre el navegador en: [`http://localhost:8000/api/v1/intelligence/skills/create/`](http://localhost:8000/api/v1/intelligence/skills/create/)
2. Debes estar autenticado con nivel 4 (Admin) o superior

### Llenar el formulario:

```
┌─────────────────────────────────────────────────┐
│  Información Básica                              │
│                                                  │
│  Nombre de la Skill *                            │
│  ┌─────────────────────────────────────────────┐ │
│  │ mi_skill_personalizada                      │ │
│  └─────────────────────────────────────────────┘ │
│  Solo minúsculas, números y underscores.         │
│  Ej: analisis_avanzado                           │
│                                                  │
│  Descripción                                     │
│  ┌─────────────────────────────────────────────┐ │
│  │ Descripción clara de lo que hace la skill   │ │
│  └─────────────────────────────────────────────┘ │
│                                                  │
│  Categoría           Nivel Requerido             │
│  ┌──────────────┐   ┌──────────────────┐        │
│  │ ▼ Analysis   │   │ ▼ Nivel 3 (Avanz)│        │
│  └──────────────┘   └──────────────────┘        │
├─────────────────────────────────────────────────┤
│  Código de la Skill                              │
│  ┌─────────────────────────────────────────────┐ │
│  │ # Escribe aquí el código de tu skill...     │ │
│  │                                             │ │
│  │ from ...services.skill_base import ...      │ │
│  │                                             │ │
│  │ class MiSkill(Skill):                       │ │
│  │     ...                                     │ │
│  └─────────────────────────────────────────────┘ │
│  La clase debe heredar de Skill e implementar    │
│  execute(self, **kwargs) -> SkillResult          │
├─────────────────────────────────────────────────┤
│                    [Cancelar]  [Crear Skill]     │
└─────────────────────────────────────────────────┘
```

### Validaciones del formulario:

- **Nombre:** Solo `[a-z_][a-z0-9_]*` (minúsculas, números, underscores)
- **Código:** No puede estar vacío
- **Descripción:** Opcional pero recomendada
- El sistema validará que el código Python sea sintácticamente correcto

### ¿Qué pasa cuando haces clic en "Crear Skill"?

1. El servidor recibe el formulario (`POST`)
2. Valida que el nombre no exista ya
3. Valida que el código Python sea sintácticamente válido
4. **Crea un archivo** en `webapp/intelligence/skills/{nombre}.py`
5. **Recarga el registry** para que la skill esté disponible
6. Redirige al dashboard con mensaje de éxito

### Verificar que la skill se creó:

Ve al dashboard: [`http://localhost:8000/api/v1/intelligence/skills/dashboard/`](http://localhost:8000/api/v1/intelligence/skills/dashboard/)

Deberías ver tu nueva skill en la tabla con:
- Nombre, descripción, categoría
- Estado: Activo (por defecto)
- Contador de ejecuciones: 0
- Botones para: Detalle, Editar, Probar

---

## 7. Paso 4: Probar la Skill

### Desde el detalle de la skill:

1. Ve al dashboard: [`/api/v1/intelligence/skills/dashboard/`](http://localhost:8000/api/v1/intelligence/skills/dashboard/)
2. Haz clic en el nombre de tu skill
3. En la página de detalle, verás:
   - Información de la skill (nombre, descripción, parámetros)
   - Mini KPIs (ejecuciones, tasa de éxito, latencia)
   - Historial de ejecuciones
   - **Botón "Ejecutar"** para probar la skill

### Desde la API REST:

```bash
curl -X POST http://localhost:8000/api/v1/intelligence/skills/api/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <tu-token>" \
  -d '{
    "skill_name": "mi_skill",
    "parameters": {"param1": "valor"}
  }'
```

Respuesta esperada:
```json
{
    "success": true,
    "data": {"resultado": "..."},
    "latency_ms": 45,
    "cached": false
}
```

### Desde el shell de Django:

```bash
cd webapp
python manage.py shell
```

```python
from intelligence.skills import create_skill_system
orchestrator = create_skill_system()

# Ejecutar skill
resultado = orchestrator.execute_skill(
    "mi_skill",
    parameters={"param1": "valor"},
    user_id="<user-uuid>"
)
print(f"Éxito: {resultado.success}")
print(f"Datos: {resultado.data}")
```

### Verificar en logs:

1. Ve a: [`/api/v1/intelligence/skills/logs/`](http://localhost:8000/api/v1/intelligence/skills/logs/)
2. Filtra por tu skill
3. Deberías ver la ejecución registrada con:
   - Estado: `success` o `error`
   - Latencia en ms
   - Fecha y hora
   - Usuario que ejecutó

---

## 8. Paso 5: Monitorear la Skill

### Dashboard de métricas:

Accede a: [`/api/v1/intelligence/skills/metrics/`](http://localhost:8000/api/v1/intelligence/skills/metrics/)

Verás:
- **KPIs globales:** Total ejecuciones, skills activas, tasa de éxito, latencia promedio
- **Gráficos:**
  - Ejecuciones por día (últimos 30 días)
  - Tasa de éxito por skill
  - Latencia promedio por skill
  - Distribución de ejecuciones por skill

### Detalle de skill:

Accede a: `/api/v1/intelligence/skills/skills/<nombre_skill>/`

Verás:
- Información completa de la skill
- KPIs específicos de esa skill
- Historial de últimas ejecuciones
- Botón para limpiar cache
- Botón para desactivar/activar

### Logs de ejecución:

Accede a: [`/api/v1/intelligence/skills/logs/`](http://localhost:8000/api/v1/intelligence/skills/logs/)

Filtros disponibles:
- **Skill:** Seleccionar una skill específica
- **Estado:** `success`, `error`, `all`
- **Búsqueda:** Por texto libre

### API de estadísticas:

```bash
GET /api/v1/intelligence/skills/stats/api/
```

Retorna JSON con:
```json
{
    "total_executions": 150,
    "success_rate": 0.95,
    "avg_latency_ms": 120.5,
    "executions_by_day": [...],
    "executions_by_skill": {...},
    "success_by_skill": {...},
    "latency_by_skill": {...}
}
```

---

## 9. Método Alternativo: Crear Archivo Directamente

Si prefieres crear el archivo manualmente (por ejemplo, si no tienes acceso al dashboard o quieres versionarlo en Git):

### Paso 1: Crear el archivo

Crea un archivo en: `webapp/intelligence/skills/mi_skill.py`

```python
"""
Mi nueva skill personalizada.
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class MiSkill(Skill):
    name = "mi_skill"
    description = "Descripción de mi skill"
    parameters = {
        'param1': SkillParameter(
            name='param1', type='str',
            description='...', required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            return SkillResult.ok(data={'resultado': 'ok'})
        except Exception as e:
            return SkillResult.from_error(str(e))
```

### Paso 2: Registrar la skill

El sistema **descubre automáticamente** las skills al iniciar. Si el servidor ya está corriendo, puedes recargar manualmente:

```python
from intelligence.skills.registry import SkillRegistry
registry = SkillRegistry()
registry.discover_skills("intelligence.skills")
```

O simplemente reinicia el servidor de Django.

### Paso 3: Verificar que se registró

```python
from intelligence.skills import create_skill_system
orchestrator = create_skill_system()
skills = orchestrator.list_available_skills()
print([s['name'] for s in skills])
# Debería incluir 'mi_skill'
```

### Paso 4: Crear registro en BD (opcional)

Si creaste el archivo manualmente, el dashboard no tendrá la metadata (categoría, nivel, descripción). Para agregarla, puedes:

1. Usar el dashboard para editar la skill: `/api/v1/intelligence/skills/skills/mi_skill/edit/`
2. O insertar manualmente en la tabla de configuración (si existe)

---

## 10. Integración con el Chat Inteligente

Las skills pueden ser invocadas automáticamente por el chat IA (DeepSeek) cuando detecta que la intención del usuario coincide con la descripción de la skill.

### Cómo funciona:

1. El usuario escribe un mensaje en el chat
2. El `IntentClassifier` analiza la intención
3. Si detecta que debe ejecutar una skill, busca en el `SkillRegistry` por descripción
4. Ejecuta la skill con los parámetros extraídos del mensaje
5. El resultado se formatea como respuesta del chat

### Requisitos para que una skill sea invocable desde el chat:

1. **`description` debe ser semántica y descriptiva** — El LLM la usa para saber qué hace
2. **Los parámetros deben tener `description` clara** — El LLM extrae valores del mensaje
3. **El nombre debe ser intuitivo** — Preferir nombres en español

### Ejemplo de descripción efectiva:

```python
# ❌ MALA descripción (no ayuda al LLM)
description = "Procesa datos de propiedades"

# ✅ BUENA descripción (el LLM entiende cuándo usarla)
description = "Genera un análisis ACM completo y recomendaciones financieras para una propiedad"
```

### Flujo chat → skill:

```
Usuario: "¿Qué me recomiendas para un departamento de 120m2 en Cayma que cuesta 250,000 soles?"
                    │
                    ▼
         IntentClassifier.classify()
                    │
                    ▼
         Busca skill por descripción
         "acm_analisis" ← "análisis ACM... recomendaciones financieras"
                    │
                    ▼
         Extrae parámetros del mensaje:
         - precio: 250000
         - area_m2: 120
         - ubicacion: "Cayma"
                    │
                    ▼
         SkillOrchestrator.execute_skill("acm_analisis", parameters={...})
                    │
                    ▼
         ChatProcessor._render_skill_response(result)
                    │
                    ▼
         "El inmueble tiene un precio por m2 de 2,083.33..."
```

---

## 11. Integración con la API REST

### Endpoints disponibles:

| Método | URL | Descripción | Nivel |
|---|---|---|---|
| `GET` | `/api/v1/intelligence/skills/dashboard/` | Dashboard HTML | 1 |
| `GET` | `/api/v1/intelligence/skills/skills/<nombre>/` | Detalle HTML | 2 |
| `GET` | `/api/v1/intelligence/skills/create/` | Formulario crear HTML | 4 |
| `POST` | `/api/v1/intelligence/skills/create/` | Crear skill | 4 |
| `GET` | `/api/v1/intelligence/skills/skills/<nombre>/edit/` | Formulario editar HTML | 4 |
| `POST` | `/api/v1/intelligence/skills/skills/<nombre>/edit/` | Editar skill | 4 |
| `GET` | `/api/v1/intelligence/skills/metrics/` | Métricas HTML | 3 |
| `GET` | `/api/v1/intelligence/skills/logs/` | Logs HTML | 3 |
| `GET` | `/api/v1/intelligence/skills/logs/api/` | Logs JSON | 3 |
| `POST` | `/api/v1/intelligence/skills/api/` | Ejecutar skill (JSON) | 1 |
| `POST` | `/api/v1/intelligence/skills/cache/<nombre>/clear/` | Limpiar cache | 4 |
| `POST` | `/api/v1/intelligence/skills/skills/<nombre>/toggle/` | Activar/desactivar | 5 |
| `GET` | `/api/v1/intelligence/skills/stats/api/` | Stats JSON | 1 |

### Ejecutar skill via API:

```bash
curl -X POST http://localhost:8000/api/v1/intelligence/skills/api/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "skill_name": "acm_analisis",
    "parameters": {
      "precio": 250000,
      "area_m2": 120,
      "ubicacion": "Cayma"
    }
  }'
```

Respuesta:
```json
{
    "success": true,
    "data": {
        "analisis": {
            "zona": "Cayma",
            "precio_total": 250000,
            "area_m2": 120,
            "precio_m2": 2083.33,
            "cuota_mensual_aproximada": 2012.34,
            "costo_total_financiamiento": 482961.6,
            "ingreso_sugerido": 7043.19,
            "gastos_mantenimiento_mensuales": 0,
            "tasa_interes_anual": 7.5,
            "plazo_anos": 20,
            "indicador_costo_area": 2.0833
        },
        "recomendacion": "El inmueble tiene un precio por m2 de 2083.33..."
    },
    "latency_ms": 45,
    "cached": false
}
```

---

## 12. Manejo de Cache

El sistema de cache (`SkillCache`) almacena resultados para evitar recomputar skills que reciben los mismos parámetros.

### Comportamiento:

- **Cache en Redis:** Si Redis está configurado, los resultados se cachean allí
- **Cache local:** Fallback en memoria si Redis no está disponible
- **TTL:** Los resultados expiran después de un tiempo configurable
- **Invalidación:** Se puede limpiar el cache de una skill específica o de todas

### Limpiar cache:

Desde el dashboard:
1. Ve al detalle de la skill
2. Haz clic en "Limpiar Cache"

Desde API:
```bash
POST /api/v1/intelligence/skills/cache/mi_skill/clear/
```

### ¿Cuándo se cachea?

- Skills con los mismos parámetros exactos
- Resultados exitosos (no se cachean errores)
- Por defecto, todas las skills son cacheables

---

## 13. Seguridad y Permisos

### Niveles de acceso por acción:

| Acción | Nivel mínimo |
|---|---|
| Ver dashboard de skills | 1 (Básico) |
| Ejecutar una skill | 1 (Básico) |
| Ver detalle de skill | 2 (Intermedio) |
| Ver métricas | 3 (Avanzado) |
| Ver logs | 3 (Avanzado) |
| Crear nueva skill | 4 (Admin) |
| Editar skill existente | 4 (Admin) |
| Limpiar cache de skill | 4 (Admin) |
| Activar/desactivar skill | 5 (Super Admin) |

### ¿Cómo se controla?

El decorador `@level_required(min_level)` en las vistas de Django verifica que el usuario autenticado tenga el nivel suficiente:

```python
@level_required(4)
def skill_create_view(request):
    # Solo admins pueden crear skills
    ...
```

### Recomendaciones:

- Skills de **nivel 1**: Operaciones seguras, solo lectura, sin efectos secundarios
- Skills de **nivel 2-3**: Operaciones que modifican datos o hacen cálculos complejos
- Skills de **nivel 4-5**: Operaciones administrativas, integraciones externas

---

## 14. Solución de Problemas

### La skill no aparece en el dashboard

**Posibles causas:**
1. Error de sintaxis en el código Python
2. Error en tiempo de importación (módulo no encontrado)
3. La clase no hereda correctamente de `Skill`
4. Falta `name`, `description` o `parameters`

**Solución:**
```bash
cd webapp
python manage.py shell
```

```python
from intelligence.skills.registry import SkillRegistry
registry = SkillRegistry()
try:
    count = registry.discover_skills("intelligence.skills")
    print(f"Skills descubiertas: {count}")
except Exception as e:
    print(f"Error: {e}")
```

### Error al crear la skill en el dashboard

**Posibles causas:**
1. El nombre ya existe
2. El código Python tiene errores de sintaxis
3. El nombre no cumple el patrón `[a-z_][a-z0-9_]*`

**Solución:** Verifica el mensaje de error en la alerta roja del formulario.

### La skill se ejecuta pero retorna error

**Posibles causas:**
1. Parámetros incorrectos o faltantes
2. Error en la lógica de negocio
3. División por cero u operación matemática inválida
4. Tipo de dato incorrecto

**Solución:** Revisa los logs en `/api/v1/intelligence/skills/logs/` y filtra por tu skill para ver el mensaje de error exacto.

### La skill no es invocada por el chat IA

**Posibles causas:**
1. La `description` no es lo suficientemente descriptiva
2. El `IntentClassifier` no detecta la intención correcta
3. Los parámetros no pueden extraerse del mensaje del usuario

**Solución:** Mejora la `description` para que sea más semántica. Incluye palabras clave que el LLM pueda asociar.

### Error de importación: `ModuleNotFoundError`

```python
# ❌ MALA importación (ruta incorrecta)
from services.skill_base import Skill

# ✅ BUENA importación (ruta relativa correcta)
from ...services.skill_base import Skill
```

**Explicación:** Las skills están en `intelligence/skills/`, y `skill_base.py` está en `intelligence/services/`. La ruta relativa `...services.skill_base` sube dos niveles: `skills/` → `intelligence/` → `services/skill_base`.

### La skill funciona en shell pero no en el dashboard

**Posible causa:** El archivo se creó manualmente pero no se registró en el `DynamicSkillRegistry`.

**Solución:** Reinicia el servidor de Django o ejecuta:
```python
from intelligence.skills.registry import SkillRegistry
registry = SkillRegistry()
registry.discover_skills("intelligence.skills")
```

---

## Apéndice A: Referencia Rápida

### URLs del dashboard:

| URL | Descripción |
|---|---|
| `/api/v1/intelligence/skills/dashboard/` | Dashboard principal |
| `/api/v1/intelligence/skills/create/` | Crear nueva skill |
| `/api/v1/intelligence/skills/skills/<nombre>/` | Detalle de skill |
| `/api/v1/intelligence/skills/skills/<nombre>/edit/` | Editar skill |
| `/api/v1/intelligence/skills/metrics/` | Métricas globales |
| `/api/v1/intelligence/skills/logs/` | Logs de ejecución |
| `/api/v1/intelligence/skills/api/` | API de ejecución (POST) |
| `/api/v1/intelligence/skills/stats/api/` | Stats en JSON |

### Comandos útiles:

```bash
# Probar skill desde shell
cd webapp
python manage.py shell
from intelligence.skills.mi_skill import MiSkill
skill = MiSkill()
result = skill.execute(param1="test")
print(result)

# Listar skills registradas
from intelligence.skills import create_skill_system
o = create_skill_system()
print(o.list_available_skills())

# Descubrir skills manualmente
from intelligence.skills.registry import SkillRegistry
r = SkillRegistry()
r.discover_skills("intelligence.skills")
```

### Template mínimo para copiar:

```python
"""
[Nombre de la skill] — [Descripción breve]
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class MiSkill(Skill):
    """[Descripción detallada]"""

    name = "mi_skill"
    description = "[Descripción semántica para el LLM]"
    parameters = {
        'param1': SkillParameter(
            name='param1', type='str',
            description='[Descripción]', required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            # Lógica aquí
            return SkillResult.ok(data={'resultado': 'ok'})
        except Exception as e:
            return SkillResult.from_error(str(e))
```

---

> **Documentos relacionados:**
> - [`MANUAL-01_ARQUITECTURA_CODIGO_SKILL.md`](MANUAL-01_ARQUITECTURA_CODIGO_SKILL.md) — Spec detallado de la arquitectura de código Python
> - [`SPEC-011_SKILLS_DASHBOARD.md`](SPEC-011_SKILLS_DASHBOARD.md) — Especificación completa del dashboard de skills
> - [`plans/sistema_skills_arquitectura.md`](sistema_skills_arquitectura.md) — Arquitectura general del sistema de skills
