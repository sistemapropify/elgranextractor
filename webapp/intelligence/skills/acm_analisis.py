"""
Skill avanzado para análisis financiero de una propiedad.
"""

from typing import Dict, Any

from ..services.skill_base import Skill, SkillParameter, SkillResult


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
            precio = params['precio']
            area = params['area_m2']
            gastos = params.get('gastos_mantenimiento_mensuales', 0.0)
            tasa_anual = params.get('tasa_interes_anual', 7.5) / 100.0
            plazo_anos = params.get('plazo_anos', 20)
            meses = max(1, plazo_anos * 12)

            if precio <= 0 or area <= 0:
                return SkillResult.from_error("Precio y área deben ser mayores a cero")

            precio_m2 = round(precio / area, 2)
            cuota_mensual = round(
                precio * (tasa_anual / 12) / (1 - (1 + tasa_anual / 12) ** -meses),
                2
            ) if tasa_anual > 0 else round(precio / meses, 2)
            costo_total = round(cuota_mensual * meses + gastos * 12 * plazo_anos, 2)
            ingreso_recomendado = round(cuota_mensual * 3.5, 2)
            indice_costo_por_area = round(precio_m2 / 1000, 4)

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
                operation='acm_analisis',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))