"""
Skills de matemáticas.

Incluye operaciones básicas y avanzadas.
"""
import math
from typing import List, Union

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


class RestaSkill(Skill):
    """Skill para restar dos números."""

    name = "resta"
    description = "Resta el segundo número del primero"
    parameters = {
        'a': SkillParameter(
            name='a',
            type='float',
            description='Número del que restar',
            required=True
        ),
        'b': SkillParameter(
            name='b',
            type='float',
            description='Número a restar',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            result = params['a'] - params['b']
            return SkillResult.ok(
                data={'resultado': result},
                operation='resta',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))


class MultiplicacionSkill(Skill):
    """Skill para multiplicar dos números."""

    name = "multiplicacion"
    description = "Multiplica dos números"
    parameters = {
        'a': SkillParameter(
            name='a',
            type='float',
            description='Primer factor',
            required=True
        ),
        'b': SkillParameter(
            name='b',
            type='float',
            description='Segundo factor',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            result = params['a'] * params['b']
            return SkillResult.ok(
                data={'resultado': result},
                operation='multiplicacion',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))


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


class PotenciaSkill(Skill):
    """Skill para calcular potencia."""

    name = "potencia"
    description = "Calcula base elevado a exponente"
    parameters = {
        'base': SkillParameter(
            name='base',
            type='float',
            description='Base de la potencia',
            required=True
        ),
        'exponente': SkillParameter(
            name='exponente',
            type='float',
            description='Exponente',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            result = params['base'] ** params['exponente']
            return SkillResult.ok(
                data={'resultado': result},
                operation='potencia',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))


class RaizCuadradaSkill(Skill):
    """Skill para calcular raíz cuadrada."""

    name = "raiz_cuadrada"
    description = "Calcula la raíz cuadrada de un número"
    parameters = {
        'numero': SkillParameter(
            name='numero',
            type='float',
            description='Número del que calcular la raíz (debe ser no negativo)',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)

            if params['numero'] < 0:
                return SkillResult.from_error("No se puede calcular raíz cuadrada de número negativo")

            result = math.sqrt(params['numero'])
            return SkillResult.ok(
                data={'resultado': result},
                operation='raiz_cuadrada',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))


class EstadisticasBasicasSkill(Skill):
    """Skill para calcular estadísticas básicas de una lista de números."""

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

            if not isinstance(numeros, list) or len(numeros) == 0:
                return SkillResult.from_error("Se requiere una lista no vacía de números")

            # Convertir a float y validar
            try:
                nums = [float(x) for x in numeros]
            except (ValueError, TypeError):
                return SkillResult.from_error("Todos los elementos deben ser números")

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
                operation='estadisticas_basicas',
                inputs={'cantidad_numeros': n}
            )

        except Exception as e:
            return SkillResult.from_error(str(e))