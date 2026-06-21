"""
Skills de análisis de datos.

Incluye procesamiento de datos, filtros y transformaciones.
"""
import re
from typing import List, Dict, Any, Union, Optional
from collections import Counter

from ..base import BaseSkill, SkillResult


class ContarPalabrasSkill(BaseSkill):
    """Skill para contar palabras en un texto."""

    name = "contar_palabras"
    description = "Cuenta la frecuencia de palabras en un texto"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'texto': {
            'type': 'string',
            'description': 'Texto del que contar palabras',
            'required': True,
        },
        'ignorar_case': {
            'type': 'boolean',
            'description': 'Si ignorar mayúsculas/minúsculas',
            'required': False,
            'default': True,
        },
        'top_n': {
            'type': 'integer',
            'description': 'Número de palabras más frecuentes a retornar (0 = todas)',
            'required': False,
            'default': 10,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'texto' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("El parámetro 'texto' es requerido")

            texto = params['texto']
            ignorar_case = params.get('ignorar_case', True)
            top_n = params.get('top_n', 10)

            # Procesar texto
            if ignorar_case:
                texto = texto.lower()

            # Extraer palabras (solo letras y números)
            palabras = re.findall(r'\b\w+\b', texto)

            if not palabras:
                return SkillResult.error("No se encontraron palabras en el texto")

            # Contar frecuencia
            contador = Counter(palabras)

            # Obtener top N
            if top_n > 0:
                mas_frecuentes = contador.most_common(top_n)
            else:
                mas_frecuentes = contador.most_common()

            resultado = {
                'total_palabras': len(palabras),
                'palabras_unicas': len(contador),
                'frecuencias': dict(mas_frecuentes),
                'top_palabra': mas_frecuentes[0][0] if mas_frecuentes else None,
                'frecuencia_maxima': mas_frecuentes[0][1] if mas_frecuentes else 0
            }

            return SkillResult.ok(
                data=resultado,
                message="Conteo de palabras realizado correctamente",
                metadata={
                    'operation': 'contar_palabras',
                    'inputs': {
                        'longitud_texto': len(texto),
                        'ignorar_case': ignorar_case,
                        'top_n': top_n,
                    },
                },
                skill_name=self.name,
            )

        except Exception as e:
            return SkillResult.error(str(e))


class FiltrarListaSkill(BaseSkill):
    """Skill para filtrar elementos de una lista."""

    name = "filtrar_lista"
    description = "Filtra elementos de una lista según criterios"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'lista': {
            'type': 'list',
            'description': 'Lista a filtrar',
            'required': True,
        },
        'criterio': {
            'type': 'string',
            'description': 'Criterio de filtro: "mayor_que", "menor_que", "igual_a", "contiene", "empieza_con", "termina_con"',
            'required': True,
            'options': ['mayor_que', 'menor_que', 'igual_a', 'contiene', 'empieza_con', 'termina_con'],
        },
        'valor': {
            'type': 'string',
            'description': 'Valor para comparar (se convierte al tipo apropiado)',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'lista' in params and 'criterio' in params and 'valor' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("Parámetros 'lista', 'criterio' y 'valor' son requeridos")

            lista = params['lista']
            criterio = params['criterio']
            valor_str = params['valor']

            if not isinstance(lista, list):
                return SkillResult.error("El parámetro 'lista' debe ser una lista")

            if not lista:
                return SkillResult.ok(
                    data={'filtrados': [], 'total_original': 0, 'total_filtrados': 0},
                    message="Lista vacía, sin elementos para filtrar",
                    metadata={'operation': 'filtrar_lista'},
                    skill_name=self.name,
                )

            # Intentar convertir valor al tipo apropiado
            valor = self._convertir_valor(valor_str, lista[0] if lista else None)

            # Aplicar filtro
            filtrados = []
            for item in lista:
                if self._cumple_criterio(item, criterio, valor):
                    filtrados.append(item)

            resultado = {
                'filtrados': filtrados,
                'total_original': len(lista),
                'total_filtrados': len(filtrados),
                'porcentaje_filtrados': round(len(filtrados) / len(lista) * 100, 2) if lista else 0
            }

            return SkillResult.ok(
                data=resultado,
                message=f"Filtro '{criterio}' aplicado correctamente",
                metadata={
                    'operation': 'filtrar_lista',
                    'inputs': {
                        'criterio': criterio,
                        'valor': valor_str,
                        'tipo_valor': type(valor).__name__,
                    },
                },
                skill_name=self.name,
            )

        except Exception as e:
            return SkillResult.error(str(e))

    def _convertir_valor(self, valor_str: str, ejemplo_item: Any) -> Any:
        """Convierte el valor string al tipo apropiado basado en el ejemplo."""
        if ejemplo_item is None:
            return valor_str

        # Intentar convertir al mismo tipo que el ejemplo
        try:
            if isinstance(ejemplo_item, int):
                return int(float(valor_str))
            elif isinstance(ejemplo_item, float):
                return float(valor_str)
            elif isinstance(ejemplo_item, bool):
                return valor_str.lower() in ('true', '1', 'si', 'yes')
            else:
                return valor_str
        except (ValueError, TypeError):
            return valor_str

    def _cumple_criterio(self, item: Any, criterio: str, valor: Any) -> bool:
        """Verifica si un item cumple el criterio de filtro."""
        try:
            if criterio == 'mayor_que':
                return item > valor
            elif criterio == 'menor_que':
                return item < valor
            elif criterio == 'igual_a':
                return item == valor
            elif criterio == 'contiene':
                return str(valor) in str(item)
            elif criterio == 'empieza_con':
                return str(item).startswith(str(valor))
            elif criterio == 'termina_con':
                return str(item).endswith(str(valor))
            else:
                return False
        except (TypeError, AttributeError):
            return False


class OrdenarListaSkill(BaseSkill):
    """Skill para ordenar una lista."""

    name = "ordenar_lista"
    description = "Ordena una lista en orden ascendente o descendente"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'lista': {
            'type': 'list',
            'description': 'Lista a ordenar',
            'required': True,
        },
        'orden': {
            'type': 'string',
            'description': 'Orden: "ascendente" o "descendente"',
            'required': False,
            'default': 'ascendente',
            'options': ['ascendente', 'descendente'],
        },
        'tipo_dato': {
            'type': 'string',
            'description': 'Tipo de dato para comparación: "auto", "str", "int", "float"',
            'required': False,
            'default': 'auto',
            'options': ['auto', 'str', 'int', 'float'],
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'lista' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("El parámetro 'lista' es requerido")

            lista = params['lista']
            orden = params.get('orden', 'ascendente')
            tipo_dato = params.get('tipo_dato', 'auto')

            if not isinstance(lista, list):
                return SkillResult.error("El parámetro 'lista' debe ser una lista")

            if not lista:
                return SkillResult.ok(
                    data={'ordenada': [], 'total_elementos': 0},
                    message="Lista vacía, sin elementos para ordenar",
                    metadata={'operation': 'ordenar_lista'},
                    skill_name=self.name,
                )

            # Convertir tipos si es necesario
            lista_convertida = self._convertir_tipos(lista, tipo_dato)

            # Ordenar
            reverse = orden == 'descendente'
            try:
                lista_ordenada = sorted(lista_convertida, reverse=reverse)
            except TypeError:
                # Si no se puede ordenar, convertir todo a string
                lista_ordenada = sorted([str(x) for x in lista_convertida], reverse=reverse)

            resultado = {
                'ordenada': lista_ordenada,
                'total_elementos': len(lista),
                'orden': orden,
                'tipo_dato': tipo_dato
            }

            return SkillResult.ok(
                data=resultado,
                message=f"Lista ordenada en orden {orden}",
                metadata={'operation': 'ordenar_lista', 'inputs': params},
                skill_name=self.name,
            )

        except Exception as e:
            return SkillResult.error(str(e))

    def _convertir_tipos(self, lista: List[Any], tipo_dato: str) -> List[Any]:
        """Convierte los elementos de la lista al tipo especificado."""
        if tipo_dato == 'auto':
            return lista

        convert_func = {
            'str': str,
            'int': lambda x: int(float(x)) if str(x).replace('.', '').replace('-', '').isdigit() else x,
            'float': lambda x: float(x) if str(x).replace('.', '').replace('-', '').replace('e', '').replace('E', '').isdigit() else x
        }.get(tipo_dato, lambda x: x)

        return [convert_func(item) for item in lista]


class ResumirTextoSkill(BaseSkill):
    """Skill para crear un resumen simple de un texto."""

    name = "resumir_texto"
    description = "Crea un resumen simple de un texto basado en las oraciones más importantes"
    category = "ejemplos"
    access_level = 1
    is_active = True

    parameters_schema = {
        'texto': {
            'type': 'string',
            'description': 'Texto a resumir',
            'required': True,
        },
        'max_oraciones': {
            'type': 'integer',
            'description': 'Máximo número de oraciones en el resumen',
            'required': False,
            'default': 3,
        },
        'longitud_minima': {
            'type': 'integer',
            'description': 'Longitud mínima de oraciones a incluir',
            'required': False,
            'default': 20,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return 'texto' in params

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error("El parámetro 'texto' es requerido")

            texto = params['texto']
            max_oraciones = params.get('max_oraciones', 3)
            longitud_minima = params.get('longitud_minima', 20)

            if not texto.strip():
                return SkillResult.error("El texto no puede estar vacío")

            # Dividir en oraciones
            oraciones = re.split(r'[.!?]+', texto)
            oraciones = [s.strip() for s in oraciones if s.strip()]

            if not oraciones:
                return SkillResult.error("No se pudieron identificar oraciones en el texto")

            # Filtrar oraciones por longitud
            oraciones_filtradas = [s for s in oraciones if len(s) >= longitud_minima]

            if not oraciones_filtradas:
                # Si no hay oraciones lo suficientemente largas, tomar las más largas disponibles
                oraciones_filtradas = sorted(oraciones, key=len, reverse=True)[:max_oraciones]

            # Tomar las primeras N oraciones
            oraciones_resumen = oraciones_filtradas[:max_oraciones]

            resumen = '. '.join(oraciones_resumen)
            if resumen and not resumen.endswith('.'):
                resumen += '.'

            resultado = {
                'resumen': resumen,
                'oraciones_originales': len(oraciones),
                'oraciones_en_resumen': len(oraciones_resumen),
                'longitud_resumen': len(resumen),
                'longitud_original': len(texto)
            }

            return SkillResult.ok(
                data=resultado,
                message="Resumen generado correctamente",
                metadata={
                    'operation': 'resumir_texto',
                    'inputs': {
                        'max_oraciones': max_oraciones,
                        'longitud_minima': longitud_minima,
                    },
                },
                skill_name=self.name,
            )

        except Exception as e:
            return SkillResult.error(str(e))
