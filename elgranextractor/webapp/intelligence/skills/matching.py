"""
Skill avanzado para cruzar requerimientos de clientes con propiedades disponibles.
Migrada de Skill (LEGACY) a BaseSkill (NUEVO).
"""

from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult


class MatchingOfertaDemandaSkill(BaseSkill):
    """Skill para hacer matching entre requerimientos y propiedades."""

    name = "matching_oferta_demanda"
    description = "Cruza requerimientos de cliente con propiedades disponibles y retorna las mejores coincidencias"
    category = "crm"
    access_level = 1
    is_active = True

    parameters_schema = {
        'requerimientos': {
            'type': 'array',
            'description': 'Lista de requerimientos de clientes',
            'required': True,
        },
        'propiedades': {
            'type': 'array',
            'description': 'Lista de propiedades disponibles para matching',
            'required': True,
        },
        'top_n': {
            'type': 'integer',
            'description': 'Número máximo de coincidencias a retornar',
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Valida que los parámetros requeridos estén presentes."""
        if not params:
            return False
        required = ('requerimientos', 'propiedades')
        return all(params.get(k) is not None for k in required)

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Faltan parámetros requeridos: requerimientos, propiedades",
                    skill_name=self.name
                )

            requerimientos = params['requerimientos']
            propiedades = params['propiedades']
            top_n = int(params.get('top_n', 5))

            if not isinstance(requerimientos, list) or not isinstance(propiedades, list):
                return SkillResult.error(
                    message="Requerimientos y propiedades deben ser listas",
                    skill_name=self.name
                )

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

            mensaje = (
                f"Matching completado: {len(matches)} coincidencias encontradas, "
                f"mostrando las {len(mejores)} mejores."
            )

            return SkillResult.ok(
                data={
                    'top_matches': mejores,
                    'total_matches': len(matches),
                },
                message=mensaje,
                metadata={
                    'operation': 'matching_oferta_demanda',
                    'inputs': {
                        'total_requerimientos': len(requerimientos),
                        'total_propiedades': len(propiedades),
                        'top_n': top_n,
                    },
                },
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
