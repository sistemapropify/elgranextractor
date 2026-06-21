"""
Skills de matemáticas.

Incluye operaciones básicas y avanzadas.
"""
import math
from typing import List, Union, Dict, Any, Optional

from ..base import BaseSkill, SkillResult


class SumaSkill(BaseSkill):
    """Skill para sumar dos números."""

    name = "suma"
    description = "Suma dos números y retorna el resultado"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'a': {
            'type': 'float',
            'description': 'Primer número a sumar',
            'required': True,
        },
        'b': {
            'type': 'float',
            'description': 'Segundo número a sumar',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'a' in params and 'b' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetros 'a' y 'b' son requeridos")
            result = float(params['a']) + float(params['b'])
            return SkillResult.ok(
                data={'resultado': result},
                message="Suma realizada correctamente",
                metadata={'operation': 'suma', 'inputs': {'a': params['a'], 'b': params['b']}},
                skill_name=self.name,
            )
        except Exception as e:
            return SkillResult.error(str(e))


class RestaSkill(BaseSkill):
    """Skill para restar dos números."""

    name = "resta"
    description = "Resta el segundo número del primero"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'a': {
            'type': 'float',
            'description': 'Número del que restar',
            'required': True,
        },
        'b': {
            'type': 'float',
            'description': 'Número a restar',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'a' in params and 'b' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetros 'a' y 'b' son requeridos")
            result = float(params['a']) - float(params['b'])
            return SkillResult.ok(
                data={'resultado': result},
                message="Resta realizada correctamente",
                metadata={'operation': 'resta', 'inputs': {'a': params['a'], 'b': params['b']}},
                skill_name=self.name,
            )
        except Exception as e:
            return SkillResult.error(str(e))


class MultiplicacionSkill(BaseSkill):
    """Skill para multiplicar dos números."""

    name = "multiplicacion"
    description = "Multiplica dos números"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'a': {
            'type': 'float',
            'description': 'Primer factor',
            'required': True,
        },
        'b': {
            'type': 'float',
            'description': 'Segundo factor',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'a' in params and 'b' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetros 'a' y 'b' son requeridos")
            result = float(params['a']) * float(params['b'])
            return SkillResult.ok(
                data={'resultado': result},
                message="Multiplicación realizada correctamente",
                metadata={'operation': 'multiplicacion', 'inputs': {'a': params['a'], 'b': params['b']}},
                skill_name=self.name,
            )
        except Exception as e:
            return SkillResult.error(str(e))


class DivisionSkill(BaseSkill):
    """Skill para dividir dos números."""

    name = "division"
    description = "Divide el primer número por el segundo"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'a': {
            'type': 'float',
            'description': 'Dividendo',
            'required': True,
        },
        'b': {
            'type': 'float',
            'description': 'Divisor (no puede ser cero)',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'a' in params and 'b' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetros 'a' y 'b' son requeridos")
            if float(params['b']) == 0:
                return SkillResult.error("No se puede dividir por cero")
            result = float(params['a']) / float(params['b'])
            return SkillResult.ok(
                data={'resultado': result},
                message="División realizada correctamente",
                metadata={'operation': 'division', 'inputs': {'a': params['a'], 'b': params['b']}},
                skill_name=self.name,
            )
        except Exception as e:
            return SkillResult.error(str(e))


class PotenciaSkill(BaseSkill):
    """Skill para calcular potencia."""

    name = "potencia"
    description = "Calcula base elevado a exponente"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'base': {
            'type': 'float',
            'description': 'Base de la potencia',
            'required': True,
        },
        'exponente': {
            'type': 'float',
            'description': 'Exponente',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'base' in params and 'exponente' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetros 'base' y 'exponente' son requeridos")
            result = float(params['base']) ** float(params['exponente'])
            return SkillResult.ok(
                data={'resultado': result},
                message="Potencia calculada correctamente",
                metadata={'operation': 'potencia', 'inputs': {'base': params['base'], 'exponente': params['exponente']}},
                skill_name=self.name,
            )
        except Exception as e:
            return SkillResult.error(str(e))


class RaizCuadradaSkill(BaseSkill):
    """Skill para calcular raíz cuadrada."""

    name = "raiz_cuadrada"
    description = "Calcula la raíz cuadrada de un número"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'numero': {
            'type': 'float',
            'description': 'Número del que calcular la raíz (debe ser no negativo)',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'numero' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetro 'numero' es requerido")
            numero = float(params['numero'])
            if numero < 0:
                return SkillResult.error("No se puede calcular raíz cuadrada de número negativo")
            result = math.sqrt(numero)
            return SkillResult.ok(
                data={'resultado': result},
                message="Raíz cuadrada calculada correctamente",
                metadata={'operation': 'raiz_cuadrada', 'inputs': {'numero': params['numero']}},
                skill_name=self.name,
            )
        except Exception as e:
            return SkillResult.error(str(e))


class EstadisticasBasicasSkill(BaseSkill):
    """Skill para calcular estadísticas básicas de una lista de números."""

    name = "estadisticas_basicas"
    description = "Calcula estadísticas básicas (media, mediana, moda, desviación estándar) de una lista de números"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'numeros': {
            'type': 'list',
            'description': 'Lista de números para analizar',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'numeros' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetro 'numeros' es requerido")

            numeros = params['numeros']

            if not isinstance(numeros, list) or len(numeros) == 0:
                return SkillResult.error("Se requiere una lista no vacía de números")

            # Convertir a float y validar
            try:
                nums = [float(x) for x in numeros]
            except (ValueError, TypeError):
                return SkillResult.error("Todos los elementos deben ser números")

            # Calcular estadísticas
            n = len(nums)
            media = sum(nums) / n

            # Mediana
            nums_sorted = sorted(nums)
            if n % 2 == 0:
                mediana = (nums_sorted[n//2 - 1] + nums_sorted[n//2]) / 2
            else:
                mediana = nums_sorted[n//2]

            # Moda (valor más frecuente)
            from collections import Counter
            counter = Counter(nums)
            max_count = max(counter.values())
            modas = [num for num, count in counter.items() if count == max_count]
            moda = modas[0] if len(modas) == 1 else modas

            # Desviación estándar
            varianza = sum((x - media) ** 2 for x in nums) / n
            desviacion = math.sqrt(varianza)

            resultado = {
                'media': round(media, 4),
                'mediana': round(mediana, 4),
                'moda': moda,
                'desviacion_estandar': round(desviacion, 4),
                'minimo': min(nums),
                'maximo': max(nums),
                'cantidad': n
            }

            return SkillResult.ok(
                data=resultado,
                message="Estadísticas calculadas correctamente",
                metadata={
                    'operation': 'estadisticas_basicas',
                    'inputs': {'cantidad_numeros': n},
                },
                skill_name=self.name,
            )

        except Exception as e:
            return SkillResult.error(str(e))
