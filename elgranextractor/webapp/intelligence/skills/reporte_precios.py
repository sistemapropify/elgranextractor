"""
Skill avanzado para generar reportes de precios por zona y tipo de propiedad.
Migrada de Skill (LEGACY) a BaseSkill (NUEVO).
"""

from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult


class ReportePreciosZonaSkill(BaseSkill):
    """Skill para crear reportes de precios promedio y tendencias por zona."""

    name = "reporte_precios_zona"
    description = "Genera un reporte de precios promedio y tendencias para una zona y tipo de propiedad"
    category = "reporte"
    access_level = 1
    is_active = True

    parameters_schema = {
        'zona': {
            'type': 'string',
            'description': 'Zona o distrito objetivo',
            'required': True,
        },
        'tipo_propiedad': {
            'type': 'string',
            'description': 'Tipo de propiedad a analizar',
            'required': True,
        },
        'registros': {
            'type': 'array',
            'description': 'Lista de registros de ventas con precios y atributos de propiedad',
            'required': True,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Valida que los parámetros requeridos estén presentes."""
        if not params:
            return False
        required = ('zona', 'tipo_propiedad', 'registros')
        return all(params.get(k) is not None for k in required)

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Faltan parámetros requeridos: zona, tipo_propiedad, registros",
                    skill_name=self.name
                )

            zona = str(params['zona']).lower()
            tipo_propiedad = str(params['tipo_propiedad']).lower()
            registros = params['registros']

            if not isinstance(registros, list) or not registros:
                return SkillResult.error(
                    message="La lista de registros no puede estar vacía",
                    skill_name=self.name
                )

            filtrados = [r for r in registros if isinstance(r, dict) and
                         zona in str(r.get('zona', '')).lower() and
                         tipo_propiedad in str(r.get('tipo_propiedad', '')).lower()]

            if not filtrados:
                return SkillResult.error(
                    message="No se encontraron registros para la zona y tipo de propiedad solicitados",
                    skill_name=self.name
                )

            precios = [float(r.get('precio', 0)) for r in filtrados if r.get('precio') is not None]
            precios = [p for p in precios if p > 0]

            precio_m2_values = []
            for registro in filtrados:
                precio = registro.get('precio')
                area = (
                    registro.get('built_area')
                    or registro.get('area_m2')
                    or registro.get('area_construida')
                    or registro.get('land_area')
                )
                try:
                    precio_val = float(precio)
                    area_val = float(area)
                    if precio_val > 0 and area_val > 0:
                        precio_m2_values.append(round(precio_val / area_val, 2))
                except (TypeError, ValueError):
                    continue

            if not precios:
                return SkillResult.error(
                    message="Los registros no contienen precios válidos",
                    skill_name=self.name
                )

            precios.sort()
            total = len(precios)
            minimo = min(precios)
            maximo = max(precios)
            promedio = round(sum(precios) / total, 2)
            mediana = round(precios[total // 2] if total % 2 == 1 else (precios[total // 2 - 1] + precios[total // 2]) / 2, 2)

            tendencias = {
                'promedio': promedio,
                'minimo': minimo,
                'maximo': maximo,
                'mediana': mediana,
                'cantidad_registros': total,
                'zona': zona,
                'tipo_propiedad': tipo_propiedad,
            }

            reporte = (
                f"Reporte de precio para {tipo_propiedad} en {zona}: promedio {promedio}, "
                f"mínimo {minimo}, máximo {maximo}, mediana {mediana}."
            )

            if precio_m2_values:
                precios_m2_values = sorted(precio_m2_values)
                total_m2 = len(precios_m2_values)
                promedio_m2 = round(sum(precios_m2_values) / total_m2, 2)
                minimo_m2 = precios_m2_values[0]
                maximo_m2 = precios_m2_values[-1]
                mediana_m2 = round(
                    precios_m2_values[total_m2 // 2]
                    if total_m2 % 2 == 1
                    else (precios_m2_values[total_m2 // 2 - 1] + precios_m2_values[total_m2 // 2]) / 2,
                    2,
                )
                tendencias.update({
                    'precio_m2_promedio': promedio_m2,
                    'precio_m2_minimo': minimo_m2,
                    'precio_m2_maximo': maximo_m2,
                    'precio_m2_mediana': mediana_m2,
                    'cantidad_registros_con_area': total_m2,
                })
                reporte = (
                    f"Reporte de precio para {tipo_propiedad} en {zona}: promedio {promedio}, "
                    f"mínimo {minimo}, máximo {maximo}, mediana {mediana}. "
                    f"Precio promedio por m2 calculado en {promedio_m2}."
                )

            return SkillResult.ok(
                data={
                    'tendencias': tendencias,
                    'reporte': reporte,
                    'registros_analizados': filtrados,
                },
                message=reporte,
                metadata={
                    'operation': 'reporte_precios_zona',
                    'inputs': {'zona': zona, 'tipo_propiedad': tipo_propiedad},
                },
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
