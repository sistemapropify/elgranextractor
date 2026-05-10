"""
Skill avanzado para cruzar requerimientos de clientes con propiedades disponibles.
"""

from typing import Dict, Any, List

from ..services.skill_base import Skill, SkillParameter, SkillResult


class MatchingOfertaDemandaSkill(Skill):
    """Skill para hacer matching entre requerimientos y propiedades."""

    name = "matching_oferta_demanda"
    description = "Cruza requerimientos de cliente con propiedades disponibles y retorna las mejores coincidencias"
    parameters = {
        'requerimientos': SkillParameter(
            name='requerimientos',
            type='list',
            description='Lista de requerimientos de clientes',
            required=True
        ),
        'propiedades': SkillParameter(
            name='propiedades',
            type='list',
            description='Lista de propiedades disponibles para matching',
            required=True
        ),
        'top_n': SkillParameter(
            name='top_n',
            type='int',
            description='Número máximo de coincidencias a retornar',
            required=False,
            default=5
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            requerimientos = params['requerimientos']
            propiedades = params['propiedades']
            top_n = params['top_n']

            if not isinstance(requerimientos, list) or not isinstance(propiedades, list):
                return SkillResult.from_error("Requerimientos y propiedades deben ser listas")

            def score_property(prop: Dict[str, Any], req: Dict[str, Any]) -> float:
                score = 0.0
                if req.get('tipo_propiedad') and prop.get('tipo_propiedad') == req['tipo_propiedad']:
                    score += 2.0
                if req.get('ubicacion') and req['ubicacion'].lower() in str(prop.get('ubicacion', '')).lower():
                    score += 1.5
                precio = prop.get('precio')
                presupuesto = req.get('presupuesto_max')
                if precio is not None and presupuesto is not None:
                    if precio <= presupuesto:
                        score += 2.0
                    else:
                        score -= min(2.0, (precio - presupuesto) / max(1.0, presupuesto) * 2)
                if req.get('habitaciones') and prop.get('habitaciones') == req['habitaciones']:
                    score += 1.0
                if req.get('banos') and prop.get('banos') == req['banos']:
                    score += 0.8
                return score

            matches = []
            for req in requerimientos:
                for prop in propiedades:
                    score = score_property(prop, req)
                    if score > 0:
                        matches.append({
                            'requerimiento': req,
                            'propiedad': prop,
                            'score': round(score, 2)
                        })

            matches.sort(key=lambda item: item['score'], reverse=True)
            mejores = matches[:top_n]

            return SkillResult.ok(
                data={
                    'top_matches': mejores,
                    'total_matches': len(matches),
                },
                operation='matching_oferta_demanda',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))