"""
ScraperOrchestratorSkill — Skill orquestadora.

Ejecuta TODOS los scrapers de portales inmobiliarios en secuencia:
1. Remax
2. Adondevivir
3. Properati
4. Urbania

Si un scraper falla, los otros continúan. Al final retorna un resumen
con los resultados de cada portal.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from intelligence.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


# Mapa de nombres de skill a clases
SKILL_MAP = {
    'remax': 'scraper_remax',
    'adondevivir': 'scraper_adondevivir',
    'properati': 'scraper_properati',
    'urbania': 'scraper_urbania',
}

# Orden de ejecución por defecto
ORDEN_DEFECTO = ['remax', 'adondevivir', 'properati', 'urbania']


def _instanciar_skill(portal: str):
    """
    Importa dinámicamente y devuelve una instancia de la skill del portal.
    
    Args:
        portal: Nombre del portal (remax, adondevivir, properati, urbania)
    
    Returns:
        Instancia de la skill correspondiente.
    
    Raises:
        ValueError: Si el portal no está soportado.
    """
    skill_name = SKILL_MAP.get(portal)
    if not skill_name:
        raise ValueError(f"Portal no soportado: {portal}. Opciones: {list(SKILL_MAP.keys())}")

    module_path = f"intelligence.skills.scrapi.{skill_name}"
    try:
        import importlib
        module = importlib.import_module(module_path)
        # Buscar la clase que hereda de BaseSkill
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr.__name__.startswith('Scraper') and hasattr(attr, 'execute'):
                return attr()
        raise ValueError(f"No se encontró clase skill en {module_path}")
    except ImportError as e:
        raise ValueError(f"Error importando skill para '{portal}': {e}")


class ScraperOrchestratorSkill(BaseSkill):
    name = "scraper_orchestrator"
    description = (
        "Ejecuta TODOS los scrapers de portales inmobiliarios en secuencia: "
        "Remax → Adondevivir → Properati → Urbania. "
        "Si un scraper falla, los otros continúan."
    )
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'portales': {
            'type': 'array',
            'description': (
                'Lista de portales a scrapear. Default: todos. '
                'Opciones: remax, adondevivir, properati, urbania. '
                'Ej: ["remax", "urbania"]'
            ),
            'required': False,
        },
        'max_paginas': {
            'type': 'integer',
            'description': (
                'Máximo de páginas a scrapear por portal. '
                '0 = todas las páginas (default). '
                'Útil para pruebas rápidas: max_paginas=1'
            ),
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        # Validar portales si se especificaron
        portales = params.get('portales', ORDEN_DEFECTO)
        if not isinstance(portales, list):
            return False
        for p in portales:
            if p not in SKILL_MAP:
                return False
        return True

    def execute(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> SkillResult:
        portales = params.get('portales', ORDEN_DEFECTO)
        max_paginas = params.get('max_paginas', 0)

        logger.info(
            f"ScraperOrchestrator: iniciando {len(portales)} scrapers "
            f"(max_paginas={max_paginas})"
        )

        resultados: List[Dict[str, Any]] = []
        errores: List[Dict[str, Any]] = []
        tiempo_inicio = time.time()

        for i, portal in enumerate(portales, 1):
            print(f"\n{'=' * 60}")
            print(f"[{i}/{len(portales)}] Scraping: {portal.upper()}")
            print(f"{'=' * 60}")

            try:
                skill = _instanciar_skill(portal)
                resultado = skill.execute({'max_paginas': max_paginas})

                if resultado.success:
                    data = resultado.data or {}
                    resultados.append({
                        'portal': portal,
                        'status': 'ok',
                        'total': data.get('total', 0),
                        'nuevas': data.get('nuevas', 0),
                        'actualizadas': data.get('actualizadas', 0),
                        'errores_db': data.get('errores', 0),
                        'mensaje': resultado.message,
                    })
                    print(f"[OK] {portal}: {resultado.message}")
                else:
                    errores.append({
                        'portal': portal,
                        'status': 'error',
                        'mensaje': resultado.message,
                    })
                    print(f"[ERROR] {portal}: {resultado.message}")

            except Exception as e:
                errores.append({
                    'portal': portal,
                    'status': 'exception',
                    'mensaje': str(e),
                })
                logger.exception(f"[orquestador] Error en {portal}: {e}")
                print(f"[EXCEPTION] {portal}: {e}")

            print()  # línea en blanco entre scrapers

        tiempo_total = round(time.time() - tiempo_inicio, 2)

        # Resumen
        total_props = sum(r.get('total', 0) for r in resultados)
        total_nuevas = sum(r.get('nuevas', 0) for r in resultados)
        total_actualizadas = sum(r.get('actualizadas', 0) for r in resultados)

        resumen = (
            f"Orquestación completada en {tiempo_total}s. "
            f"{len(resultados)} portales OK, {len(errores)} con errores. "
            f"Total: {total_props} props ({total_nuevas} nuevas, "
            f"{total_actualizadas} actualizadas)"
        )

        logger.info(resumen)

        return SkillResult.ok(
            data={
                'resumen': resumen,
                'tiempo_segundos': tiempo_total,
                'portales_ok': len(resultados),
                'portales_error': len(errores),
                'resultados': resultados,
                'errores': errores,
                'total_propiedades': total_props,
                'total_nuevas': total_nuevas,
                'total_actualizadas': total_actualizadas,
            },
            message=resumen,
            skill_name=self.name,
        )
