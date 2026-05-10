"""
Skill avanzado para realizar búsquedas exactas de propiedades por filtros.
"""

from typing import Dict, Any, List

from ..services.skill_base import Skill, SkillParameter, SkillResult


class BusquedaExactaSkill(Skill):
    """Skill para filtrar propiedades usando criterios exactos."""

    name = "busqueda_exacta"
    description = "Realiza una búsqueda exacta de propiedades según filtros estructurados"
    parameters = {
        'propiedades': SkillParameter(
            name='propiedades',
            type='list',
            description='Lista de propiedades a filtrar',
            required=True
        ),
        'filtros': SkillParameter(
            name='filtros',
            type='dict',
            description='Diccionario de filtros exactos a aplicar',
            required=True
        ),
        'ordenar_por': SkillParameter(
            name='ordenar_por',
            type='str',
            description='Campo por el cual ordenar resultados',
            required=False,
            default='precio'
        ),
        'direccion': SkillParameter(
            name='direccion',
            type='str',
            description='Dirección del orden: ascendente o descendente',
            required=False,
            default='ascendente'
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            propiedades = params['propiedades']
            filtros = params['filtros']
            ordenar_por = params['ordenar_por']
            direccion = params['direccion']

            if not isinstance(propiedades, list):
                return SkillResult.from_error("El parámetro 'propiedades' debe ser una lista")
            if not isinstance(filtros, dict):
                return SkillResult.from_error("El parámetro 'filtros' debe ser un diccionario")

            def cumple(prop: Dict[str, Any]) -> bool:
                for campo, valor in filtros.items():
                    if campo not in prop:
                        return False
                    if isinstance(valor, list):
                        if prop[campo] not in valor:
                            return False
                    elif isinstance(valor, dict):
                        min_val = valor.get('min')
                        max_val = valor.get('max')
                        if min_val is not None and prop[campo] < min_val:
                            return False
                        if max_val is not None and prop[campo] > max_val:
                            return False
                    else:
                        if str(prop[campo]).lower() != str(valor).lower():
                            return False
                return True

            filtradas = [prop for prop in propiedades if isinstance(prop, dict) and cumple(prop)]

            try:
                filtradas.sort(
                    key=lambda item: item.get(ordenar_por, 0) if isinstance(item, dict) else 0,
                    reverse=(direccion == 'descendente')
                )
            except TypeError:
                pass

            return SkillResult.ok(
                data={
                    'resultados': filtradas,
                    'total': len(filtradas),
                    'filtros_aplicados': filtros,
                    'ordenar_por': ordenar_por,
                    'direccion': direccion,
                },
                operation='busqueda_exacta',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))