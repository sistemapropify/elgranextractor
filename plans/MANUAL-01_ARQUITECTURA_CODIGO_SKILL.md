# MANUAL 1: Arquitectura de Código para una Skill Python

> **Propósito:** Este manual explica EXACTAMENTE cómo debe estructurarse el código Python que se pega en el formulario de creación de skills (textarea "Código de la Skill" en `/api/v1/intelligence/skills/create/`).
>
> **Público:** Desarrolladores que necesitan crear nuevas skills escribiendo código Python directamente en el dashboard.

---

## Índice

1. [Estructura General del Código](#1-estructura-general-del-código)
2. [Importaciones](#2-importaciones)
3. [La Clase Skill](#3-la-clase-skill)
4. [Atributos Obligatorios de Clase](#4-atributos-obligatorios-de-clase)
5. [Parámetros con `SkillParameter`](#5-parámetros-con-skillparameter)
6. [El Método `execute()`](#6-el-método-execute)
7. [Validación de Parámetros con `validate_params()`](#7-validación-de-parámetros-con-validate_params)
8. [Retorno de Resultados con `SkillResult`](#8-retorno-de-resultados-con-skillresult)
9. [Manejo de Errores](#9-manejo-de-errores)
10. [Ejemplo Mínimo (Template)](#10-ejemplo-mínimo-template)
11. [Ejemplo Simple: SumaSkill](#11-ejemplo-simple-sumaskill)
12. [Ejemplo Intermedio: DivisionSkill](#12-ejemplo-intermedio-divisionskill)
13. [Ejemplo Avanzado: ACMAnalisisSkill](#13-ejemplo-avanzado-acmanalisisskill)
14. [Ejemplo con Listas: EstadisticasBasicasSkill](#14-ejemplo-con-listas-estadisticasbasicas)
15. [Checklist de Validación](#15-checklist-de-validación)
16. [Errores Comunes y Soluciones](#16-errores-comunes-y-soluciones)

---

## 1. Estructura General del Código

Toda skill es un **archivo Python** que contiene **una clase** que hereda de `Skill`. La estructura mínima es:

```python
"""
[Docstring opcional describiendo la skill]
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult

class MiNuevaSkill(Skill):
    name = "mi_nueva_skill"
    description = "Descripción clara de lo que hace"
    parameters = {
        # Definir parámetros aquí
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            # LÓGICA DE LA SKILL AQUÍ
            return SkillResult.ok(
                data={'resultado': ...},
                operation='mi_nueva_skill',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))
```

> ⚠️ **REGLAS DE ORO:**
> 1. La clase **DEBE** heredar de `Skill`
> 2. La clase **DEBE** definir `name`, `description` y `parameters`
> 3. La clase **DEBE** implementar `execute(self, **kwargs) -> SkillResult`
> 4. El método `execute()` **DEBE** usar `self.validate_params(**kwargs)` para validar
> 5. El método `execute()` **DEBE** retornar `SkillResult.ok()` o `SkillResult.from_error()`
> 6. Todo el código de `execute()` **DEBE** ir dentro de un `try/except`

---

## 2. Importaciones

Las importaciones necesarias son siempre las mismas:

```python
from typing import Dict, Any          # Tipado (opcional pero recomendado)
from ...services.skill_base import Skill, SkillParameter, SkillResult
```

**Explicación:**
- `Skill` → Clase base abstracta de la que heredar
- `SkillParameter` → Dataclass para definir cada parámetro de entrada
- `SkillResult` → Dataclass para el resultado estandarizado

**Importaciones adicionales comunes:**
```python
from typing import Dict, Any, List, Optional, Union
import math
import json
from collections import Counter
```

> ⚠️ **Ruta de importación:** Las skills viven en `intelligence/skills/`, y `skill_base.py` está en `intelligence/services/`. Por eso la ruta relativa es `...services.skill_base` (subir dos niveles: skills → intelligence → services).

---

## 3. La Clase Skill

La clase `Skill` es una **clase abstracta** (`ABC`). Cuando heredas de ella, el sistema **valida automáticamente** que hayas definido:

| Atributo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `name` | `str` | ✅ Sí | Identificador único de la skill |
| `description` | `str` | ✅ Sí | Descripción semántica para el LLM |
| `parameters` | `Dict[str, SkillParameter]` | ✅ Sí | Diccionario de parámetros de entrada |

Si falta alguno, el sistema lanza `ValueError` al intentar cargar la skill.

### Convención de nombres para la clase:

```
[Funcionalidad]Skill
```

Ejemplos: `SumaSkill`, `DivisionSkill`, `ACMAnalisisSkill`, `ReportePreciosZonaSkill`, `MatchingOfertaDemandaSkill`

---

## 4. Atributos Obligatorios de Clase

### `name` — Identificador único

```python
name = "mi_skill"
```

**Reglas:**
- Solo **minúsculas**, **números** y **guiones bajos** (`_`)
- Debe empezar con letra o underscore
- Debe ser **único** en todo el sistema
- Se usa como identificador en URLs y API
- Ejemplos válidos: `"suma"`, `"acm_analisis"`, `"reporte_precios_zona"`, `"matching_oferta_demanda"`

### `description` — Descripción semántica

```python
description = "Calcula la raíz cuadrada de un número"
```

**Reglas:**
- Texto descriptivo en español
- Debe explicar QUÉ hace la skill, no cómo
- Se usa para que el LLM (DeepSeek) pueda encontrar y ejecutar la skill automáticamente
- Sé específico: incluye el tipo de operación y los datos que maneja

### `parameters` — Diccionario de parámetros

```python
parameters = {
    'nombre_parametro': SkillParameter(
        name='nombre_parametro',
        type='float',
        description='Descripción del parámetro',
        required=True
    ),
}
```

**Reglas:**
- Las **llaves** del diccionario deben coincidir con el `name` del `SkillParameter`
- Cada valor es una instancia de `SkillParameter`
- Puede estar vacío (`{}`) si la skill no requiere parámetros

---

## 5. Parámetros con `SkillParameter`

`SkillParameter` es un **dataclass** con estos campos:

| Campo | Tipo | Obligatorio | Default | Descripción |
|---|---|---|---|---|
| `name` | `str` | ✅ Sí | — | Nombre del parámetro |
| `type` | `str` | ✅ Sí | — | Tipo de dato: `'str'`, `'int'`, `'float'`, `'bool'`, `'list'`, `'dict'` |
| `description` | `str` | ✅ Sí | — | Descripción para el LLM y la UI |
| `required` | `bool` | ❌ No | `True` | Si es obligatorio o no |
| `default` | `Any` | ❌ No | `None` | Valor por defecto (solo si `required=False`) |
| `options` | `Optional[List[str]]` | ❌ No | `None` | Lista de valores permitidos (para opciones fijas) |

### Tipos de datos soportados:

| type | Python | Conversión automática |
|---|---|---|
| `'str'` | `str` | `str(value)` |
| `'int'` | `int` | `int(value)` |
| `'float'` | `float` | `float(value)` |
| `'bool'` | `bool` | `str(value).lower() in ('true', '1', 'yes', 'si')` |
| `'list'` | `list` | `list(value)` o `[value]` |
| `'dict'` | `dict` | `dict(value)` o `{'value': value}` |

### Ejemplos de parámetros:

```python
# Parámetro string requerido
'ubicacion': SkillParameter(
    name='ubicacion',
    type='str',
    description='Zona o distrito a analizar',
    required=True
),

# Parámetro numérico requerido
'precio': SkillParameter(
    name='precio',
    type='float',
    description='Precio de la propiedad en soles',
    required=True
),

# Parámetro entero opcional con valor por defecto
'plazo_anos': SkillParameter(
    name='plazo_anos',
    type='int',
    description='Plazo del financiamiento en años',
    required=False,
    default=20
),

# Parámetro con opciones fijas
'tipo_inmueble': SkillParameter(
    name='tipo_inmueble',
    type='str',
    description='Tipo de propiedad',
    required=True,
    options=['Departamento', 'Casa', 'Terreno', 'Local Comercial', 'Oficina']
),

# Parámetro de lista
'registros': SkillParameter(
    name='registros',
    type='list',
    description='Lista de registros a analizar',
    required=True
),

# Parámetro booleano opcional
'generar_grafico': SkillParameter(
    name='generar_grafico',
    type='bool',
    description='Si debe generar un gráfico',
    required=False,
    default=False
),
```

---

## 6. El Método `execute()`

Es el **corazón de la skill**. Aquí va toda la lógica de negocio.

### Firma:

```python
def execute(self, **kwargs) -> SkillResult:
```

### Estructura obligatoria:

```python
def execute(self, **kwargs) -> SkillResult:
    try:
        # 1. Validar y convertir parámetros
        params = self.validate_params(**kwargs)

        # 2. Extraer valores (con .get() para opcionales)
        valor_requerido = params['nombre_parametro']
        valor_opcional = params.get('nombre_opcional', valor_default)

        # 3. Validaciones de negocio
        if valor_requerido <= 0:
            return SkillResult.from_error("El valor debe ser mayor a cero")

        # 4. Lógica principal
        resultado = ...  # tu cálculo aquí

        # 5. Retornar resultado exitoso
        return SkillResult.ok(
            data={'clave': resultado},
            operation='nombre_skill',
            inputs=params
        )

    except Exception as e:
        # 6. Capturar cualquier error
        return SkillResult.from_error(str(e))
```

### Reglas del método `execute()`:

1. **Siempre** dentro de `try/except`
2. **Siempre** llamar a `self.validate_params(**kwargs)` primero
3. **Siempre** retornar `SkillResult.ok()` o `SkillResult.from_error()`
4. **Nunca** lanzar excepciones — siempre capturarlas y retornar error
5. **Nunca** retornar un dict, string u otro tipo directamente

---

## 7. Validación de Parámetros con `validate_params()`

El método `validate_params(**kwargs)` de la clase base `Skill`:

1. **Verifica** que todos los parámetros requeridos estén presentes
2. **Convierte** cada valor al tipo especificado (`_convert_type()`)
3. **Retorna** un diccionario con los valores ya convertidos
4. **Lanza** `ValueError` si falta algún parámetro requerido

```python
params = self.validate_params(**kwargs)
# params es un dict: {'a': 5.0, 'b': 3.0}
```

**¿Qué pasa si un parámetro opcional no se envía?**
- Si tiene `default`, se usa ese valor
- Si no tiene `default` y no se envía, simplemente no aparece en `params`

Por eso los parámetros opcionales se acceden con `.get()`:

```python
gastos = params.get('gastos_mantenimiento_mensuales', 0.0)
tasa = params.get('tasa_interes_anual', 7.5)
```

---

## 8. Retorno de Resultados con `SkillResult`

### `SkillResult.ok(data, **metadata)` — Resultado exitoso

```python
return SkillResult.ok(
    data={
        'resultado': 42,
        'mensaje': 'Operación completada',
    },
    operation='mi_skill',
    inputs={'a': 5, 'b': 3}
)
```

| Parámetro | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `data` | `Dict[str, Any]` | ✅ Sí | Datos del resultado |
| `**metadata` | `Any` | ❌ No | Metadatos adicionales (operation, inputs, etc.) |

**Convenciones para `data`:**
- Usa claves descriptivas en español
- Incluye solo datos relevantes
- Si el resultado es complejo, estructura con sub-diccionarios

### `SkillResult.from_error(error, **metadata)` — Resultado con error

```python
return SkillResult.from_error("No se puede dividir por cero")
```

| Parámetro | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `error` | `str` | ✅ Sí | Mensaje de error descriptivo |
| `**metadata` | `Any` | ❌ No | Metadatos adicionales |

**Buenas prácticas para mensajes de error:**
- Sé descriptivo: explica qué pasó y por qué
- En español
- Incluye valores relevantes si ayuda al debugging

---

## 9. Manejo de Errores

### Patrón obligatorio:

```python
def execute(self, **kwargs) -> SkillResult:
    try:
        params = self.validate_params(**kwargs)
        # ... lógica ...
        return SkillResult.ok(data={...})
    except ValueError as e:
        # Error de validación de parámetros
        return SkillResult.from_error(f"Error de validación: {str(e)}")
    except Exception as e:
        # Cualquier otro error
        return SkillResult.from_error(f"Error inesperado: {str(e)}")
```

### Validaciones de negocio (antes de procesar):

```python
# Validar rangos
if params['numero'] < 0:
    return SkillResult.from_error("El número no puede ser negativo")

# Validar división por cero
if params['b'] == 0:
    return SkillResult.from_error("No se puede dividir por cero")

# Validar listas vacías
if not params['numeros']:
    return SkillResult.from_error("La lista no puede estar vacía")

# Validar tipos específicos
if not isinstance(params['registros'], list):
    return SkillResult.from_error("Se requiere una lista de registros")
```

---

## 10. Ejemplo Mínimo (Template)

Este es el template mínimo que puedes copiar y pegar directamente en el textarea del dashboard:

```python
"""
[Descripción breve de la skill]
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class MiNuevaSkill(Skill):
    """[Descripción detallada de la clase]"""

    name = "mi_nueva_skill"
    description = "[Descripción semántica para el LLM]"
    parameters = {
        'param1': SkillParameter(
            name='param1',
            type='str',
            description='[Descripción del parámetro]',
            required=True
        ),
        'param2': SkillParameter(
            name='param2',
            type='float',
            description='[Descripción del parámetro]',
            required=False,
            default=0.0
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)

            # --- LÓGICA DE LA SKILL ---
            param1 = params['param1']
            param2 = params.get('param2', 0.0)

            resultado = f"Procesado: {param1} con valor {param2}"

            return SkillResult.ok(
                data={
                    'resultado': resultado,
                    'param1': param1,
                    'param2': param2,
                },
                operation='mi_nueva_skill',
                inputs=params
            )

        except Exception as e:
            return SkillResult.from_error(str(e))
```

---

## 11. Ejemplo Simple: SumaSkill

Skill más básica posible: suma dos números.

```python
"""
Skill para sumar dos números.
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class SumaSkill(Skill):
    """Skill para sumar dos números."""

    name = "suma"
    description = "Suma dos números y retorna el resultado"
    parameters = {
        'a': SkillParameter(
            name='a',
            type='float',
            description='Primer número a sumar',
            required=True
        ),
        'b': SkillParameter(
            name='b',
            type='float',
            description='Segundo número a sumar',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            result = params['a'] + params['b']
            return SkillResult.ok(
                data={'resultado': result},
                operation='suma',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))
```

**Puntos clave:**
- 2 parámetros requeridos tipo `float`
- Lógica de una línea: `params['a'] + params['b']`
- Retorna `{'resultado': result}` en `data`
- Metadata: `operation='suma'`, `inputs=params`

---

## 12. Ejemplo Intermedio: DivisionSkill

Muestra validación de negocio (división por cero).

```python
"""
Skill para dividir dos números.
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class DivisionSkill(Skill):
    """Skill para dividir dos números."""

    name = "division"
    description = "Divide el primer número por el segundo"
    parameters = {
        'a': SkillParameter(
            name='a',
            type='float',
            description='Dividendo',
            required=True
        ),
        'b': SkillParameter(
            name='b',
            type='float',
            description='Divisor (no puede ser cero)',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)

            # Validación de negocio ANTES de operar
            if params['b'] == 0:
                return SkillResult.from_error("No se puede dividir por cero")

            result = params['a'] / params['b']
            return SkillResult.ok(
                data={'resultado': result},
                operation='division',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))
```

**Puntos clave:**
- Validación de negocio: `if params['b'] == 0`
- Retorno temprano con `SkillResult.from_error()`
- La descripción del parámetro `b` advierte al usuario: "no puede ser cero"

---

## 13. Ejemplo Avanzado: ACMAnalisisSkill

Skill real del sistema que hace análisis financiero de propiedades. Muestra:
- Parámetros requeridos y opcionales con defaults
- Cálculos financieros complejos
- Estructura de datos anidada en el resultado
- Generación de texto de recomendación

```python
"""
Skill avanzado para análisis financiero de una propiedad.
"""
from typing import Dict, Any
from ...services.skill_base import Skill, SkillParameter, SkillResult


class ACMAnalisisSkill(Skill):
    """Skill para generar un análisis financiero ACM de una propiedad."""

    name = "acm_analisis"
    description = "Genera un análisis ACM completo y recomendaciones financieras para una propiedad"
    parameters = {
        'precio': SkillParameter(
            name='precio',
            type='float',
            description='Precio de la propiedad',
            required=True
        ),
        'area_m2': SkillParameter(
            name='area_m2',
            type='float',
            description='Área de la propiedad en metros cuadrados',
            required=True
        ),
        'ubicacion': SkillParameter(
            name='ubicacion',
            type='str',
            description='Ubicación o zona de la propiedad',
            required=True
        ),
        'gastos_mantenimiento_mensuales': SkillParameter(
            name='gastos_mantenimiento_mensuales',
            type='float',
            description='Gastos mensuales de mantenimiento estimados',
            required=False,
            default=0.0
        ),
        'tasa_interes_anual': SkillParameter(
            name='tasa_interes_anual',
            type='float',
            description='Tasa de interés anual esperada para financiamiento (%)',
            required=False,
            default=7.5
        ),
        'plazo_anos': SkillParameter(
            name='plazo_anos',
            type='int',
            description='Plazo del financiamiento en años',
            required=False,
            default=20
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)

            # Extraer valores (requeridos con [], opcionales con .get())
            precio = params['precio']
            area = params['area_m2']
            gastos = params.get('gastos_mantenimiento_mensuales', 0.0)
            tasa_anual = params.get('tasa_interes_anual', 7.5) / 100.0
            plazo_anos = params.get('plazo_anos', 20)
            meses = max(1, plazo_anos * 12)

            # Validaciones de negocio
            if precio <= 0 or area <= 0:
                return SkillResult.from_error(
                    "Precio y área deben ser mayores a cero"
                )

            # Cálculos financieros
            precio_m2 = round(precio / area, 2)
            cuota_mensual = round(
                precio * (tasa_anual / 12) /
                (1 - (1 + tasa_anual / 12) ** -meses),
                2
            ) if tasa_anual > 0 else round(precio / meses, 2)

            costo_total = round(
                cuota_mensual * meses + gastos * 12 * plazo_anos, 2
            )
            ingreso_recomendado = round(cuota_mensual * 3.5, 2)

            # Estructurar resultado
            analisis = {
                'zona': params['ubicacion'],
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
                data={
                    'analisis': analisis,
                    'recomendacion': recomendacion,
                },
                operation='acm_analisis',
                inputs=params
            )

        except Exception as e:
            return SkillResult.from_error(str(e))
```

**Puntos clave:**
- 3 parámetros requeridos + 3 opcionales con `default`
- Parámetros opcionales se acceden con `params.get('nombre', default)`
- Validación de negocio: `if precio <= 0 or area <= 0`
- Resultado estructurado con sub-diccionarios (`'analisis'` y `'recomendacion'`)
- Generación de texto legible para humanos

---

## 14. Ejemplo con Listas: EstadisticasBasicasSkill

Muestra cómo trabajar con parámetros tipo `list`.

```python
"""
Skill para calcular estadísticas básicas de una lista de números.
"""
import math
from typing import Dict, Any, List
from collections import Counter
from ...services.skill_base import Skill, SkillParameter, SkillResult


class EstadisticasBasicasSkill(Skill):
    """Skill para calcular estadísticas básicas."""

    name = "estadisticas_basicas"
    description = "Calcula estadísticas básicas (media, mediana, moda, desviación estándar) de una lista de números"
    parameters = {
        'numeros': SkillParameter(
            name='numeros',
            type='list',
            description='Lista de números para analizar',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            numeros = params['numeros']

            # Validar que sea lista no vacía
            if not isinstance(numeros, list) or len(numeros) == 0:
                return SkillResult.from_error(
                    "Se requiere una lista no vacía de números"
                )

            # Convertir a float
            try:
                nums = [float(x) for x in numeros]
            except (ValueError, TypeError):
                return SkillResult.from_error(
                    "Todos los elementos deben ser números"
                )

            # Cálculos
            n = len(nums)
            media = sum(nums) / n

            nums_sorted = sorted(nums)
            if n % 2 == 0:
                mediana = (nums_sorted[n//2 - 1] + nums_sorted[n//2]) / 2
            else:
                mediana = nums_sorted[n//2]

            counter = Counter(nums)
            max_count = max(counter.values())
            modas = [num for num, count in counter.items()
                     if count == max_count]
            moda = modas[0] if len(modas) == 1 else modas

            varianza = sum((x - media) ** 2 for x in nums) / n
            desviacion = math.sqrt(varianza)

            return SkillResult.ok(
                data={
                    'media': round(media, 4),
                    'mediana': round(mediana, 4),
                    'moda': moda,
                    'desviacion_estandar': round(desviacion, 4),
                    'minimo': min(nums),
                    'maximo': max(nums),
                    'cantidad': n,
                },
                operation='estadisticas_basicas',
                inputs={'cantidad_numeros': n}
            )

        except Exception as e:
            return SkillResult.from_error(str(e))
```

**Puntos clave:**
- Parámetro tipo `list` para recibir múltiples valores
- Validación de tipo: `isinstance(numeros, list)`
- Validación de contenido: `len(numeros) == 0`
- Conversión segura de tipos dentro de try/except anidado
- Múltiples cálculos sobre los mismos datos

---

## 15. Checklist de Validación

Antes de guardar una skill, verifica que cumples con TODO:

### Estructura básica
- [ ] El archivo tiene docstring al inicio
- [ ] Las importaciones son correctas (`from ...services.skill_base import ...`)
- [ ] La clase hereda de `Skill`
- [ ] La clase tiene `name` (string)
- [ ] La clase tiene `description` (string)
- [ ] La clase tiene `parameters` (dict)
- [ ] La clase implementa `execute(self, **kwargs) -> SkillResult`

### Atributo `name`
- [ ] Solo minúsculas, números y underscores
- [ ] No tiene espacios ni caracteres especiales
- [ ] Es descriptivo y único

### Atributo `parameters`
- [ ] Cada `SkillParameter` tiene `name`, `type`, `description`
- [ ] Los tipos son válidos: `'str'`, `'int'`, `'float'`, `'bool'`, `'list'`, `'dict'`
- [ ] Los parámetros opcionales tienen `default`
- [ ] Los parámetros con opciones fijas tienen `options`

### Método `execute()`
- [ ] Todo el código está dentro de `try/except`
- [ ] Se llama a `self.validate_params(**kwargs)` al inicio
- [ ] Los parámetros requeridos se acceden con `params['nombre']`
- [ ] Los parámetros opcionales se acceden con `params.get('nombre', default)`
- [ ] Hay validaciones de negocio antes de procesar
- [ ] Se retorna `SkillResult.ok(data={...})` en éxito
- [ ] Se retorna `SkillResult.from_error(...)` en error
- [ ] El `except` final captura `Exception as e`

---

## 16. Errores Comunes y Soluciones

| Error | Causa | Solución |
|---|---|---|
| `ValueError: Skill X debe definir 'name'` | Falta el atributo `name` en la clase | Agregar `name = "mi_skill"` |
| `ValueError: Skill X debe definir 'description'` | Falta el atributo `description` | Agregar `description = "..."` |
| `ValueError: Parámetro requerido faltante: x` | No se envió un parámetro requerido | Verificar que el parámetro existe en `parameters` y se envía |
| `ValueError: could not convert string to float: 'abc'` | Tipo de dato incorrecto | El parámetro espera `float` pero se recibió texto |
| `DivisionByZero` | No se validó división por cero | Agregar `if b == 0: return SkillResult.from_error(...)` |
| `KeyError: 'x'` | Se accede a `params['x']` pero no existe | Usar `params.get('x', default)` para opcionales |
| `NameError: name 'Skill' is not defined` | Importación incorrecta | Verificar `from ...services.skill_base import Skill` |
| La skill no aparece en el dashboard | Error de sintaxis en el código | Revisar el código con atención a indentación y sintaxis |
| `TypeError: 'NoneType' object is not subscriptable` | `validate_params()` no fue llamado | Llamar `params = self.validate_params(**kwargs)` primero |

---

> **Siguiente paso:** Una vez que el código de la skill está listo, ve al [`MANUAL-02_IMPLEMENTACION_SKILL.md`](MANUAL-02_IMPLEMENTACION_SKILL.md) para aprender cómo implementarla de 0 en el sistema, desde la creación en el dashboard hasta la ejecución y monitoreo.
