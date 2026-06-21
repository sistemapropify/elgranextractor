# MANUAL 1: Arquitectura de Código para una Skill Python

> **Propósito:** Este manual explica EXACTAMENTE cómo debe estructurarse el código Python de una skill en el sistema Propifai Intelligence.
>
> **Público:** Desarrolladores que necesitan crear nuevas skills.
>
> **Actualizado:** Mayo 2026 — Solo documenta el sistema NUEVO (`BaseSkill`). El sistema LEGACY (`Skill` de `services/skill_base.py`) fue eliminado.

---

## Índice

1. [Visión General del Sistema](#1-visión-general-del-sistema)
2. [Clase `BaseSkill` (skills.base)](#2-clase-baseskill-skillsbase)
3. [SkillResult](#3-skillresult)
4. [SkillRegistry (Singleton)](#4-skillregistry-singleton)
5. [SkillOrchestrator](#5-skillorchestrator)
6. [Importaciones](#6-importaciones)
7. [Estructura de la Clase](#7-estructura-de-la-clase)
8. [Parámetros con `parameters_schema`](#8-parámetros-con-parameters_schema)
9. [El Método `execute()`](#9-el-método-execute)
10. [Validación de Parámetros](#10-validación-de-parámetros)
11. [Retorno de Resultados con `SkillResult`](#11-retorno-de-resultados-con-skillresult)
12. [Manejo de Errores](#12-manejo-de-errores)
13. [Ejemplo Mínimo (Template)](#13-ejemplo-mínimo-template)
14. [Ejemplo Simple: SumaSkill](#14-ejemplo-simple-sumaskill)
15. [Ejemplo Avanzado: ACMAnalisisSkill (Migrado)](#15-ejemplo-avanzado-acmanalisisskill-migrado)
16. [Ejemplo Producción: BusquedaPropiedadesSkill](#16-ejemplo-producción-busquedapropiedadesskill)
17. [Ejemplo con Listas: EstadisticasBasicasSkill](#17-ejemplo-con-listas-estadisticasbasicas)
18. [Checklist de Validación](#18-checklist-de-validación)
19. [Errores Comunes y Soluciones](#19-errores-comunes-y-soluciones)

---

## 1. Visión General del Sistema

El sistema de skills de Propifai usa una **única clase base**: [`BaseSkill`](webapp/intelligence/skills/base.py:91).

| Componente | Archivo | Función |
|---|---|---|
| **`BaseSkill`** (ABC) | [`skills/base.py`](webapp/intelligence/skills/base.py:91) | Clase base abstracta para todas las skills |
| **`SkillResult`** | [`skills/base.py`](webapp/intelligence/skills/base.py:22) | Dataclass de resultado estandarizado |
| **`SkillRegistry`** | [`skills/registry.py`](webapp/intelligence/skills/registry.py:41) | Singleton que registra y descubre skills |
| **`SkillOrchestrator`** | [`skills/orchestrator.py`](webapp/intelligence/skills/orchestrator.py:62) | Coordina ejecución con cache, métricas y persistencia |
| **`SkillCache`** | [`skills/cache.py`](webapp/intelligence/skills/cache.py) | Cache en Redis + memoria local |
| **`SkillExecution`** | [`models.py`](webapp/intelligence/models.py) | Persistencia de ejecuciones en BD |

> ⚠️ **El sistema LEGACY (`Skill`, `SkillParameter` de `services/skill_base.py`) fue eliminado en Mayo 2026.** Todas las skills existentes fueron migradas a `BaseSkill`. No uses importaciones de `services.skill_base`.

---

## 2. Clase `BaseSkill` (skills.base)

**Archivo:** [`webapp/intelligence/skills/base.py`](webapp/intelligence/skills/base.py:91)

```python
class BaseSkill(ABC):
    # Atributos de clase (sobrescribir en subclases)
    name: str = ""
    description: str = ""
    category: str = "custom"
    access_level: int = 1
    is_active: bool = True
    parameters_schema: Dict[str, Dict[str, Any]] = {}

    @abstractmethod
    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        ...

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        ...

    def get_schema(self) -> Dict[str, Any]:
        """Retorna el schema completo de la skill para el agente."""
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'access_level': self.access_level,
            'is_active': self.is_active,
            'parameters_schema': self.parameters_schema,
        }

    def can_user_access(self, user_level: int) -> bool:
        """Verifica si un usuario con cierto nivel puede usar esta skill."""
        return self.is_active and user_level >= self.access_level
```

### Atributos de clase requeridos:

| Atributo | Tipo | Descripción |
|---|---|---|
| `name` | `str` | Identificador único en snake_case. Ej: `'busqueda_propiedades'` |
| `description` | `str` | Descripción semántica para que el LLM elija la skill |
| `category` | `str` | `'busqueda'`, `'crm'`, `'reporte'`, `'notificacion'`, `'template'`, `'custom'` |
| `access_level` | `int` | Nivel mínimo de acceso: 1 (Básico), 2, 3, 4 (Admin), 5 (SuperAdmin) |
| `is_active` | `bool` | Si la skill está disponible para el agente |
| `parameters_schema` | `dict` | Schema de parámetros que acepta la skill |

### Validación automática en `__init_subclass__`:

Al definir una subclase, `BaseSkill` valida automáticamente:
- `name` no puede estar vacío
- `description` no puede estar vacío
- `category` debe ser uno de los valores estándar (warning si no)
- `parameters_schema` debe ser un dict

---

## 3. SkillResult

**Archivo:** [`webapp/intelligence/skills/base.py`](webapp/intelligence/skills/base.py:22)

```python
@dataclass
class SkillResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    skill_name: str = ""

    @classmethod
    def ok(cls, data, message="", metadata=None, skill_name="") -> 'SkillResult': ...

    @classmethod
    def error(cls, message, metadata=None, skill_name="") -> 'SkillResult': ...
```

### Métodos factory:

```python
# Resultado exitoso
SkillResult.ok(
    data={'resultado': 'valor'},
    message="Descripción legible del resultado",
    metadata={'parametros_usados': list(params.keys())},
    skill_name=self.name
)

# Resultado con error
SkillResult.error(
    message="Descripción del error",
    metadata={'parametros_recibidos': params},
    skill_name=self.name
)
```

### Alias de compatibilidad (para código migrado desde LEGACY):

```python
result.error_message       # → self.message si no es success, None si es success
SkillResult.from_error("error", **metadata)  # → equivalente a SkillResult.error(message="error", metadata=metadata)
```

---

## 4. SkillRegistry (Singleton)

**Archivo:** [`webapp/intelligence/skills/registry.py`](webapp/intelligence/skills/registry.py:41)

```python
class SkillRegistry:
    _instance: Optional['SkillRegistry'] = None
    _skills: Dict[str, BaseSkill] = {}
    _skill_classes: Dict[str, Type[BaseSkill]] = {}

    def __new__(cls) -> 'SkillRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, skill_class: Type[BaseSkill]) -> None:
        """Registra una skill en el catálogo."""

    def find_best_skill(self, intent: str, user_level: int = 1) -> Optional[BaseSkill]:
        """Dada una intención, retorna la skill más adecuada."""

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Obtiene una skill por su nombre."""

    def list_available(self, user_level: int = 1) -> List[Dict[str, Any]]:
        """Lista todas las skills activas accesibles para ese nivel."""

    def deactivate(self, name: str) -> None: ...
    def activate(self, name: str) -> None: ...
```

### Registro de skills:

Las skills se registran automáticamente al arrancar la aplicación en [`webapp/intelligence/apps.py`](webapp/intelligence/apps.py). El registro manual:

```python
from intelligence.skills.registry import SkillRegistry
from intelligence.skills.mi_skill import MiSkill

registry = SkillRegistry()
registry.register(MiSkill)
```

### Búsqueda semántica:

`find_best_skill()` analiza la intención del usuario usando:
1. Coincidencia de tokens con palabras clave del dominio inmobiliario
2. Coincidencia de tokens con la descripción de cada skill
3. Bonus por nombre de skill y categoría

Si la confianza es menor al umbral (`MIN_CONFIDENCE_THRESHOLD = 0.25`), retorna `None` (RAG puro).

---

## 5. SkillOrchestrator

**Archivo:** [`webapp/intelligence/skills/orchestrator.py`](webapp/intelligence/skills/orchestrator.py:62)

```python
class SkillOrchestrator:
    def __init__(self, registry: SkillRegistry, cache: SkillCache): ...

    def execute_skill(
        self,
        skill_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext = None
    ) -> SkillResult:
        """Ejecuta una skill con validación completa, cache y persistencia."""
```

### Flujo de ejecución:

1. Validar existencia de la skill en el registry
2. Verificar permisos del usuario (`can_user_access`)
3. Generar cache key
4. Verificar cache (si hay hit, retorna resultado cacheado)
5. Ejecutar `skill.execute(parameters, context)`
6. Cachear resultado si fue exitoso
7. Registrar métricas y persistir en `SkillExecution`

### ExecutionContext:

```python
@dataclass
class ExecutionContext:
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    environment: str = "production"
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

## 6. Importaciones

```python
from typing import Dict, Any, Optional
from ..base import BaseSkill, SkillResult
```

> **Ruta de importación:** Las skills viven en `intelligence/skills/`. `base.py` está en el mismo paquete `intelligence/skills/`, por eso la ruta relativa es `..base` (subir un nivel desde una subcarpeta como `skills/propiedades/` → `skills/`).

Para skills en subdirectorios (ej: `skills/propiedades/skill.py`):

```python
from ..base import BaseSkill, SkillResult
```

Para skills en el directorio raíz de skills (ej: `skills/acm_analisis.py`):

```python
from .base import BaseSkill, SkillResult
```

---

## 7. Estructura de la Clase

```python
class MiSkill(BaseSkill):
    """Docstring de la skill."""

    name = "mi_skill"
    description = "Descripción semántica para el LLM"
    category = "custom"              # busqueda | crm | reporte | notificacion | template | custom
    access_level = 1                 # 1=Básico, 2=Intermedio, 3=Avanzado, 4=Admin, 5=SuperAdmin
    is_active = True

    parameters_schema = {
        'param1': {
            'type': 'string',
            'description': 'Descripción del parámetro',
            'required': True,
        },
        'param2': {
            'type': 'integer',
            'description': 'Parámetro opcional',
            'required': False,
            'default': 0,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        for name, schema in self.parameters_schema.items():
            if schema.get('required', False):
                if params.get(name) is None or params.get(name) == '':
                    return False
        return True

    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Parámetros inválidos",
                    skill_name=self.name
                )
            # Lógica aquí
            return SkillResult.ok(
                data={'resultado': ...},
                message="Ejecutado correctamente",
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
```

---

## 8. Parámetros con `parameters_schema`

Los parámetros se definen como un diccionario de diccionarios:

```python
parameters_schema = {
    'nombre_parametro': {
        'type': 'string',          # Tipo: 'string', 'integer', 'number', 'boolean', 'array', 'object'
        'description': '...',      # Descripción para el LLM
        'required': True,          # Si es obligatorio
        'default': None,           # Valor por defecto (solo si required=False)
        'enum': ['opcion1', 'opcion2'],  # Valores fijos permitidos (opcional)
        'example': 'ejemplo',      # Ejemplo para el LLM (opcional)
    },
    ...
}
```

### Tipos soportados:

| Tipo en schema | Python | Uso |
|---|---|---|
| `'string'` | `str` | Texto, nombres, descripciones |
| `'integer'` | `int` | Números enteros (cantidad, años) |
| `'number'` | `float` | Números decimales (precios, áreas) |
| `'boolean'` | `bool` | Valores verdadero/falso |
| `'array'` | `list` | Lista de valores |
| `'object'` | `dict` | Diccionario con estructura compleja |

### Diferencia clave con el LEGACY eliminado:

En el sistema NUEVO, `validate_params()` **NO** hace validación automática de tipos. Eres responsable de:
1. Verificar que los parámetros requeridos existen
2. Convertir tipos si es necesario
3. Validar valores permitidos

```python
def validate_params(self, params: Dict[str, Any]) -> bool:
    if not params:
        return False
    for name, schema in self.parameters_schema.items():
        if schema.get('required', False):
            if params.get(name) is None or params.get(name) == '':
                return False
        # Validar valores permitidos (enum)
        if 'enum' in schema and params.get(name) is not None:
            if params[name] not in schema['enum']:
                return False
    return True
```

---

## 9. El Método `execute()`

```python
def execute(self, params: Dict[str, Any],
            context: Optional[Dict[str, Any]] = None) -> SkillResult:
    try:
        if not self.validate_params(params):
            return SkillResult.error(
                message="Parámetros inválidos o insuficientes",
                skill_name=self.name
            )
        valor = params.get('param_requerido')
        opcional = params.get('param_opcional', default)
        return SkillResult.ok(
            data={'resultado': valor},
            message="Ejecutado correctamente",
            metadata={'parametros_usados': list(params.keys())},
            skill_name=self.name
        )
    except Exception as e:
        return SkillResult.error(
            message=str(e),
            skill_name=self.name
        )
```

> **El parámetro `context`** permite pasar información adicional como:
> - `user_id`: ID del usuario que ejecuta la skill
> - `session_id`: ID de sesión
> - `permissions`: Lista de permisos
> - `environment`: 'production' o 'development'
> - `metadata`: Dict con datos adicionales

---

## 10. Validación de Parámetros

El sistema NUEVO **no hace validación automática**. Debes implementarla tú mismo:

```python
def validate_params(self, params: Dict[str, Any]) -> bool:
    if not params:
        return False

    # 1. Verificar requeridos
    for name, schema in self.parameters_schema.items():
        if schema.get('required', False):
            if params.get(name) is None or params.get(name) == '':
                return False

    # 2. Verificar que haya al menos un filtro con valor
    has_any_value = any(
        v is not None and v != '' and v != []
        for v in params.values()
    )
    if not has_any_value:
        return False

    # 3. Validar valores enum si aplica
    for name, schema in self.parameters_schema.items():
        if 'enum' in schema and params.get(name) is not None:
            if params[name] not in schema['enum']:
                return False

    return True
```

---

## 11. Retorno de Resultados con `SkillResult`

```python
# Éxito
return SkillResult.ok(
    data={'resultado': 'valor'},
    message="Descripción legible del resultado",
    metadata={'parametros_usados': list(params.keys())},
    skill_name=self.name
)

# Error
return SkillResult.error(
    message="Descripción del error",
    metadata={'parametros_recibidos': params},
    skill_name=self.name
)
```

### Campos de SkillResult:

| Campo | Tipo | Descripción |
|---|---|---|
| `success` | `bool` | `True` si la ejecución fue exitosa |
| `data` | `dict` o `None` | Datos del resultado |
| `message` | `str` | Texto legible del resultado o error |
| `metadata` | `dict` | Metadatos adicionales |
| `skill_name` | `str` | Nombre de la skill que ejecutó |

---

## 12. Manejo de Errores

```python
def execute(self, params: Dict[str, Any],
            context: Optional[Dict[str, Any]] = None) -> SkillResult:
    try:
        if not self.validate_params(params):
            return SkillResult.error(
                message="Parámetros inválidos o insuficientes",
                metadata={'params_recibidos': params},
                skill_name=self.name
            )
        # ... lógica ...
        if precio <= 0:
            return SkillResult.error(
                message="El precio debe ser mayor a cero",
                skill_name=self.name
            )
        return SkillResult.ok(data={...}, skill_name=self.name)
    except Exception as e:
        return SkillResult.error(
            message=str(e),
            metadata={'error_type': type(e).__name__},
            skill_name=self.name
        )
```

---

## 13. Ejemplo Mínimo (Template)

```python
"""
[Nombre de la skill] — [Descripción breve]
"""
from typing import Dict, Any, Optional
from ..base import BaseSkill, SkillResult


class MiSkill(BaseSkill):
    """[Descripción detallada]"""

    name = "mi_skill"
    description = "[Descripción semántica para el LLM]"
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'param1': {
            'type': 'string',
            'description': '[Descripción del parámetro]',
            'required': True,
        },
        'param_opcional': {
            'type': 'integer',
            'description': '[Descripción]',
            'required': False,
            'default': 0,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        for name, schema in self.parameters_schema.items():
            if schema.get('required', False):
                if params.get(name) is None or params.get(name) == '':
                    return False
        return True

    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Parámetros inválidos",
                    skill_name=self.name
                )
            # Lógica aquí
            return SkillResult.ok(
                data={'resultado': 'ok'},
                message="Ejecutado correctamente",
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
```

---

## 14. Ejemplo Simple: SumaSkill

Basado en el ejemplo real [`webapp/intelligence/skills/examples/math_skills.py`](webapp/intelligence/skills/examples/math_skills.py):

```python
"""
Skill para sumar dos números.
"""
from typing import Dict, Any, Optional
from ..base import BaseSkill, SkillResult


class SumaSkill(BaseSkill):
    """Skill para sumar dos números."""

    name = "suma"
    description = "Suma dos números y devuelve el resultado"
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'a': {
            'type': 'number',
            'description': 'Primer número a sumar',
            'required': True,
        },
        'b': {
            'type': 'number',
            'description': 'Segundo número a sumar',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        return (
            params.get('a') is not None and
            params.get('b') is not None
        )

    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Se requieren dos números (a y b)",
                    skill_name=self.name
                )
            resultado = float(params['a']) + float(params['b'])
            return SkillResult.ok(
                data={'resultado': resultado, 'operacion': 'suma'},
                message=f"La suma de {params['a']} + {params['b']} = {resultado}",
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
```

---

## 15. Ejemplo Avanzado: ACMAnalisisSkill (Migrado)

Basado en el archivo real [`webapp/intelligence/skills/acm_analisis.py`](webapp/intelligence/skills/acm_analisis.py):

```python
"""
Skill avanzado para análisis financiero de una propiedad.
Migrada de Skill (LEGACY) a BaseSkill (NUEVO).
"""
from typing import Any, Dict, Optional
from .base import BaseSkill, SkillResult


class ACMAnalisisSkill(BaseSkill):
    """Skill para generar un análisis financiero ACM de una propiedad."""

    name = "acm_analisis"
    description = "Genera un análisis ACM completo y recomendaciones financieras para una propiedad"
    category = "reporte"
    access_level = 1
    is_active = True

    parameters_schema = {
        'precio': {
            'type': 'number',
            'description': 'Precio de la propiedad',
            'required': True,
        },
        'area_m2': {
            'type': 'number',
            'description': 'Área de la propiedad en metros cuadrados',
            'required': True,
        },
        'ubicacion': {
            'type': 'string',
            'description': 'Ubicación o zona de la propiedad',
            'required': True,
        },
        'gastos_mantenimiento_mensuales': {
            'type': 'number',
            'description': 'Gastos mensuales de mantenimiento estimados',
            'required': False,
        },
        'tasa_interes_anual': {
            'type': 'number',
            'description': 'Tasa de interés anual esperada para financiamiento (%)',
            'required': False,
        },
        'plazo_anos': {
            'type': 'integer',
            'description': 'Plazo del financiamiento en años',
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Valida que los parámetros requeridos estén presentes."""
        if not params:
            return False
        required = ('precio', 'area_m2', 'ubicacion')
        return all(params.get(k) is not None for k in required)

    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Faltan parámetros requeridos: precio, area_m2, ubicacion",
                    skill_name=self.name
                )

            precio = float(params['precio'])
            area = float(params['area_m2'])
            ubicacion = str(params['ubicacion'])
            gastos = float(params.get('gastos_mantenimiento_mensuales', 0.0))
            tasa_anual = float(params.get('tasa_interes_anual', 7.5)) / 100.0
            plazo_anos = int(params.get('plazo_anos', 20))
            meses = max(1, plazo_anos * 12)

            if precio <= 0 or area <= 0:
                return SkillResult.error(
                    message="Precio y área deben ser mayores a cero",
                    skill_name=self.name
                )

            precio_m2 = round(precio / area, 2)
            cuota_mensual = round(
                precio * (tasa_anual / 12) / (1 - (1 + tasa_anual / 12) ** -meses),
                2
            ) if tasa_anual > 0 else round(precio / meses, 2)
            costo_total = round(cuota_mensual * meses + gastos * 12 * plazo_anos, 2)
            ingreso_recomendado = round(cuota_mensual * 3.5, 2)

            analisis = {
                'zona': ubicacion,
                'precio_total': precio,
                'area_m2': area,
                'precio_m2': precio_m2,
                'cuota_mensual_aproximada': cuota_mensual,
                'costo_total_financiamiento': costo_total,
                'ingreso_sugerido': ingreso_recomendado,
                'gastos_mantenimiento_mensuales': gastos,
                'tasa_interes_anual': tasa_anual * 100,
                'plazo_anos': plazo_anos,
            }

            recomendacion = (
                "El inmueble tiene un precio por m2 de "
                f"{precio_m2} y una cuota mensual estimada de "
                f"{cuota_mensual}. Recomendamos un ingreso mínimo "
                f"cercano a {ingreso_recomendado} para una compra saludable."
            )

            return SkillResult.ok(
                data={'analisis': analisis, 'recomendacion': recomendacion},
                message="Análisis ACM generado correctamente",
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
```

**Puntos clave:**
- 3 parámetros requeridos + 3 opcionales
- Parámetros opcionales se acceden con `params.get('nombre', default)`
- Validación de negocio: `if precio <= 0 or area <= 0`
- Resultado estructurado con sub-diccionarios
- Generación de texto legible para humanos

---

## 16. Ejemplo Producción: BusquedaPropiedadesSkill

Basado en el archivo real [`webapp/intelligence/skills/propiedades/skill.py`](webapp/intelligence/skills/propiedades/skill.py):

```python
"""
BusquedaPropiedadesSkill — Skill de búsqueda híbrida (SQL + semántica) de propiedades.
"""
from typing import Any, Dict, Optional
from ..base import BaseSkill, SkillResult


class BusquedaPropiedadesSkill(BaseSkill):
    """Busca propiedades combinando filtros SQL con búsqueda semántica."""

    name = "busqueda_propiedades"
    description = (
        "Busca propiedades en la base de datos usando filtros exactos "
        "(distrito, tipo, precio, habitaciones, área) y búsqueda semántica "
        "(descripciones, ambientes, características)."
    )
    category = "busqueda"
    access_level = 1
    is_active = True

    parameters_schema = {
        'distrito': {
            'type': 'string',
            'description': 'Distrito donde buscar (ej: Cayma, Yanahuara, Cerro Colorado)',
            'required': False,
        },
        'tipo_propiedad': {
            'type': 'string',
            'description': 'Tipo de propiedad: Departamento, Casa, Terreno, Local Comercial, Oficina',
            'required': False,
        },
        'operacion': {
            'type': 'string',
            'description': 'Tipo de operación: venta, alquiler',
            'required': False,
        },
        'precio_min': {
            'type': 'number',
            'description': 'Precio mínimo en la moneda detectada',
            'required': False,
        },
        'precio_max': {
            'type': 'number',
            'description': 'Precio máximo en la moneda detectada',
            'required': False,
        },
        'habitaciones': {
            'type': 'integer',
            'description': 'Número mínimo de habitaciones',
            'required': False,
        },
        'area_min': {
            'type': 'number',
            'description': 'Área mínima en m²',
            'required': False,
        },
        'semantic_query': {
            'type': 'string',
            'description': 'Búsqueda por texto libre semántico (ej: ambientes amplios y luminosos)',
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        has_filter = any(
            params.get(k) is not None and params.get(k) != ''
            for k in ('distrito', 'tipo_propiedad', 'operacion',
                       'precio_min', 'precio_max', 'habitaciones',
                       'area_min', 'semantic_query')
        )
        return has_filter

    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Parámetros insuficientes para buscar propiedades",
                    skill_name=self.name
                )
            # Lógica de búsqueda aquí...
            return SkillResult.ok(
                data={'propiedades': [], 'total': 0},
                message="Búsqueda completada",
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
```

---

## 17. Ejemplo con Listas: EstadisticasBasicas

Basado en el ejemplo real [`webapp/intelligence/skills/examples/data_skills.py`](webapp/intelligence/skills/examples/data_skills.py):

```python
"""
Skill para calcular estadísticas básicas de una lista de números.
"""
from typing import List, Dict, Any, Optional
from collections import Counter
from ..base import BaseSkill, SkillResult


class EstadisticasBasicasSkill(BaseSkill):
    """Calcula estadísticas básicas (media, mediana, moda, etc.) de una lista de números."""

    name = "estadisticas_basicas"
    description = "Calcula estadísticas básicas de una lista de números: media, mediana, moda, mínimo, máximo"
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'numeros': {
            'type': 'array',
            'description': 'Lista de números para analizar',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        numeros = params.get('numeros')
        if numeros is None or not isinstance(numeros, list) or len(numeros) == 0:
            return False
        return True

    def execute(self, params: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Se requiere una lista no vacía de números",
                    skill_name=self.name
                )
            numeros = [float(x) for x in params['numeros']]
            n = len(numeros)
            suma = sum(numeros)
            media = suma / n
            ordenados = sorted(numeros)
            mediana = ordenados[n // 2] if n % 2 else (ordenados[n // 2 - 1] + ordenados[n // 2]) / 2
            moda = Counter(numeros).most_common(1)[0][0] if n > 0 else None

            return SkillResult.ok(
                data={
                    'media': round(media, 2),
                    'mediana': round(mediana, 2),
                    'moda': moda,
                    'minimo': min(numeros),
                    'maximo': max(numeros),
                    'total': n,
                },
                message=f"Estadísticas calculadas para {n} números",
                skill_name=self.name
            )
        except (ValueError, TypeError) as e:
            return SkillResult.error(
                message=f"Error al procesar números: {e}",
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
```

---

## 18. Checklist de Validación

Antes de dar por terminada una skill, verifica:

### ✅ Estructura básica
- [ ] La clase hereda de `BaseSkill`
- [ ] `name` está definido y es único (snake_case)
- [ ] `description` es semántica y descriptiva para el LLM
- [ ] `category` es uno de los valores estándar
- [ ] `access_level` está definido (1-5)
- [ ] `is_active` está definido
- [ ] `parameters_schema` es un dict no vacío

### ✅ Métodos implementados
- [ ] `validate_params(params) -> bool` está implementado
- [ ] `execute(params, context) -> SkillResult` está implementado

### ✅ Calidad de código
- [ ] Los nombres de parámetros son intuitivos y en español
- [ ] Las `description` incluyen ejemplos entre paréntesis para el LLM
- [ ] Se usa `params.get('nombre', default)` para opcionales
- [ ] Los errores se capturan y retornan como `SkillResult.error()`
- [ ] No hay SQL raw ni lógica de negocio hardcodeada
- [ ] La skill se registra en `apps.py` (o se descubre automáticamente)

---

## 19. Errores Comunes y Soluciones

### Error de importación: `ModuleNotFoundError`

```python
# ❌ MAL (ruta del sistema LEGACY eliminado)
from ...services.skill_base import Skill

# ✅ BIEN (ruta del sistema NUEVO)
from ..base import BaseSkill, SkillResult
```

### La skill no aparece en el dashboard

**Posibles causas:**
1. Error de sintaxis en el código Python
2. Error en tiempo de importación (módulo no encontrado)
3. La clase no hereda correctamente de `BaseSkill`
4. Falta `name`, `description` o `parameters_schema`

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

### La skill funciona en shell pero no en el dashboard

**Posible causa:** El archivo se creó manualmente pero no se registró en el `SkillRegistry`.

**Solución:** Reinicia el servidor de Django o ejecuta:
```python
from intelligence.skills.registry import SkillRegistry
registry = SkillRegistry()
registry.discover_skills("intelligence.skills")
```

---

*Este manual documenta exclusivamente el sistema NUEVO (`BaseSkill`). El sistema LEGACY (`Skill` de `services/skill_base.py`) fue eliminado en Mayo 2026.*
