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
            'type': 'float',
            'description': 'Precio de la propiedad',
            'required': True,
        },
        'area_m2': {
            'type': 'float',
            'description': 'Área de la propiedad en metros cuadrados',
            'required': True,
        },
        'ubicacion': {
            'type': 'string',
            'description': 'Ubicación o zona de la propiedad',
            'required': True,
        },
        'gastos_mantenimiento_mensuales': {
            'type': 'float',
            'description': 'Gastos mensuales de mantenimiento estimados',
            'required': False,
        },
        'tasa_interes_anual': {
            'type': 'float',
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

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
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
            indice_costo_por_area = round(precio_m2 / 1000, 4)

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
                'indicador_costo_area': indice_costo_por_area,
            }

            recomendacion = (
                "El inmueble tiene un precio por m2 de "
                f"{precio_m2} y una cuota mensual estimada de {cuota_mensual}. "
                "Recomendamos un ingreso mínimo cercano a "
                f"{ingreso_recomendado} para una compra saludable."
            )

            return SkillResult.ok(
                data={
                    'analisis': analisis,
                    'recomendacion': recomendacion,
                },
                message=recomendacion,
                metadata={
                    'operation': 'acm_analisis',
                    'inputs': {
                        'precio': precio,
                        'area_m2': area,
                        'ubicacion': ubicacion,
                    },
                },
                skill_name=self.name
            )
        except Exception as e:
            return SkillResult.error(
                message=str(e),
                skill_name=self.name
            )
