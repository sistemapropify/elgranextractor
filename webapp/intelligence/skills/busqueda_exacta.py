"""
Skill avanzado para realizar búsquedas exactas de propiedades por filtros.
Migrada de Skill (LEGACY) a BaseSkill (NUEVO).
"""

from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult


class BusquedaExactaSkill(BaseSkill):
    """Skill para filtrar propiedades usando criterios exactos."""

    name = "busqueda_exacta"
    description = "Realiza una búsqueda exacta de propiedades según filtros estructurados"
    category = "busqueda"
    access_level = 1
    is_active = True

    parameters_schema = {
        'propiedades': {
            'type': 'array',
            'description': 'Lista de propiedades a filtrar',
            'required': True,
        },
        'filtros': {
            'type': 'object',
            'description': 'Diccionario de filtros exactos a aplicar',
            'required': True,
        },
        'ordenar_por': {
            'type': 'string',
            'description': 'Campo por el cual ordenar resultados',
            'required': False,
        },
        'direccion': {
            'type': 'string',
            'description': 'Dirección del orden: ascendente o descendente',
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Valida que los parámetros requeridos estén presentes."""
        if not params:
            return False
        required = ('propiedades', 'filtros')
        return all(params.get(k) is not None for k in required)

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Faltan parámetros requeridos: propiedades, filtros",
                    skill_name=self.name
                )

            propiedades = params['propiedades']
            filtros = params['filtros']
            ordenar_por = str(params.get('ordenar_por', 'precio'))
            direccion = str(params.get('direccion', 'ascendente'))

            if not isinstance(propiedades, list):
                return SkillResult.error(
                    message="El parámetro 'propiedades' debe ser una lista",
                    skill_name=self.name
                )
            if not isinstance(filtros, dict):
                return SkillResult.error(
                    message="El parámetro 'filtros' debe ser un diccionario",
                    skill_name=self.name
                )

            def cumple(prop: Dict[str, Any]) -> bool:
                # ADDENDUM 2: soporta formato anidado (field_values) y plano
                # busqueda_propiedades retorna propiedades como:
                #   {'document_id': ..., 'field_values': {'district_name': 'Cayma', ...}}
                # busqueda_exacta esperaba formato plano:
                #   {'district_name': 'Cayma', ...}
                datos = prop.get('field_values', prop) if isinstance(prop.get('field_values'), dict) else prop

                for campo, valor in filtros.items():
                    if campo not in datos:
                        return False
                    if isinstance(valor, list):
                        if datos[campo] not in valor:
                            return False
                    elif isinstance(valor, dict):
                        min_val = valor.get('min')
                        max_val = valor.get('max')
                        if min_val is not None and datos[campo] < min_val:
                            return False
                        if max_val is not None and datos[campo] > max_val:
                            return False
                    else:
                        if str(datos[campo]).lower() != str(valor).lower():
                            return False
                return True

            def _get_sort_key(item: Dict[str, Any], campo: str):
                datos = item.get('field_values', item) if isinstance(item.get('field_values'), dict) else item
                return datos.get(campo, 0)

            filtradas = [prop for prop in propiedades if isinstance(prop, dict) and cumple(prop)]

            try:
                filtradas.sort(
                    key=lambda item: _get_sort_key(item, ordenar_por) if isinstance(item, dict) else 0,
                    reverse=(direccion == 'descendente')
                )
            except TypeError:
                pass

            mensaje = (
                f"Búsqueda exacta completada: {len(filtradas)} propiedades encontradas "
                f"de {len(propiedades)} total."
            )

            return SkillResult.ok(
                data={
                    'resultados': filtradas,
                    'total': len(filtradas),
                    'filtros_aplicados': filtros,
                    'ordenar_por': ordenar_por,
                    'direccion': direccion,
                },
                message=mensaje,
                metadata={
                    'operation': 'busqueda_exacta',
                    'inputs': {
                        'total_propiedades': len(propiedades),
                        'total_filtros': len(filtros),
                    },
                },
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
