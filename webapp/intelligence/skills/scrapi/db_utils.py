"""
db_utils — Funciones compartidas para guardar propiedades scrapeadas en DB.

Todas las scraper-skills usan guardar_propiedades() para hacer upsert
en la tabla propiedades_competencia (modelo PropiedadesCompetencia).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def guardar_propiedades(
    propiedades: List[Dict[str, Any]],
    fuente: str,
) -> Dict[str, int]:
    """
    Guarda propiedades scrapeadas en la tabla propiedades_competencia.

    Usa update_or_create para upsert por (fuente, id_origen):
    - Si la propiedad ya existe (mismo fuente + id_origen), la actualiza.
    - Si no existe, la crea.

    Args:
        propiedades: Lista de dicts con formato estandarizado.
                     Cada dict debe tener al menos 'id_origen'.
        fuente: Nombre del portal (remax, adondevivir, properati, urbania).

    Returns:
        Dict con { 'nuevas': N, 'actualizadas': M, 'total': len(propiedades) }
    """
    from ingestas.models import PropiedadesCompetencia

    nuevas = 0
    actualizadas = 0
    errores = 0

    for prop in propiedades:
        id_origen = prop.get('id_origen')
        if not id_origen:
            errores += 1
            logger.warning(
                f"[{fuente}] Propiedad sin id_origen, saltando: {prop.get('titulo', '?')}"
            )
            continue

        try:
            # Separar metadatos del scraper que no van al modelo
            datos_modelo = {k: v for k, v in prop.items()
                          if k != 'datos_crudos_extra'}

            obj, created = PropiedadesCompetencia.objects.update_or_create(
                fuente=fuente,
                id_origen=str(id_origen),
                defaults=datos_modelo,
            )
            if created:
                nuevas += 1
            else:
                actualizadas += 1
        except Exception as e:
            errores += 1
            logger.error(
                f"[{fuente}] Error guardando propiedad {id_origen}: {e}"
            )

    total = len(propiedades)
    logger.info(
        f"[{fuente}] Guardado completado: {nuevas} nuevas, "
        f"{actualizadas} actualizadas, {errores} errores / {total} total"
    )

    return {
        'nuevas': nuevas,
        'actualizadas': actualizadas,
        'errores': errores,
        'total': total,
    }


def limpiar_fuente(fuente: str) -> int:
    """
    Elimina todas las propiedades de una fuente específica.
    Útil antes de re-scrapear completamente un portal.

    Args:
        fuente: Nombre del portal a limpiar.

    Returns:
        Número de registros eliminados.
    """
    from ingestas.models import PropiedadesCompetencia

    count, _ = PropiedadesCompetencia.objects.filter(fuente=fuente).delete()
    logger.info(f"[{fuente}] Eliminados {count} registros")
    return count
