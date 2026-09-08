"""Skill para extraer inventario público de Facebook Marketplace."""

from __future__ import annotations

from typing import Any, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades
from scrapi.contracts import outcome
from scrapi.source_config import requested_url


class ScraperFacebookMarketplaceSkill(BaseSkill):
    name = "scraper_facebook_marketplace"
    description = (
        "Extrae anuncios inmobiliarios visibles de Facebook Marketplace "
        "Arequipa mediante desplazamiento infinito y los guarda de forma idempotente."
    )
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        "source_url": {"type": "string", "description": "URL de búsqueda configurada.", "required": False},
        "max_items": {
            "type": "integer",
            "description": "Máximo de anuncios visibles a procesar.",
            "required": False,
        },
        "search_url": {
            "type": "string",
            "description": "URL de búsqueda de Marketplace permitida.",
            "required": False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        try:
            requested_url('facebook_marketplace', params)
            return int(params.get('max_items') or 1500) > 0
        except (ValueError, TypeError):
            return False

    def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> SkillResult:
        from scrapi.facebook_marketplace_scraper import (
            DEFAULT_MAX_ITEMS,
            DEFAULT_SEARCH_URL,
            run_scraper,
        )

        progress_callback = (context or {}).get("progress_callback")
        lifecycle_run_id = (context or {}).get("lifecycle_run_id")
        incremental = {"total": 0, "nuevas": 0, "actualizadas": 0, "errores": 0}

        def save_batch(rows):
            result = guardar_propiedades(
                rows,
                fuente="facebook_marketplace",
                lifecycle_run_id=lifecycle_run_id,
                execution_token=(context or {}).get('execution_token'),
            )
            for key in incremental:
                incremental[key] = (int(result.get(key, 0) or 0) if lifecycle_run_id
                                    else incremental[key] + int(result.get(key, 0) or 0))
            return incremental.copy()

        try:
            rows = run_scraper(
                search_url=requested_url('facebook_marketplace', params),
                max_items=int(params.get("max_items") or DEFAULT_MAX_ITEMS),
                start_index=int(params.get("start_page") or 1),
                resume_item_ids=params.get("resume_item_ids") or None,
                resume_state=params.get('resume_state'),
                progress_callback=progress_callback,
                batch_callback=save_batch,
            )
        except Exception as exc:
            import logging
            import traceback
            logging.getLogger(__name__).exception('marketplace.failed')
            if progress_callback:
                progress_callback({'event': 'scraping.failed', 'level': 'error', 'message': str(exc),
                                   'error_type': type(exc).__name__, 'traceback': traceback.format_exc()})
            return SkillResult.error(
                message=f"Error en scraper Facebook Marketplace: {exc}",
                skill_name=self.name,
            )
        discovery = outcome(rows)
        if lifecycle_run_id:
            from ingestas.scraping_store import run_counters
            incremental.update(run_counters(lifecycle_run_id))
        if not rows:
            if int(params.get("start_page") or 1) > 1 or incremental['total']:
                return SkillResult.ok(
                    data={
                        "portal": "facebook_marketplace",
                        **incremental,
                        'discovery': discovery,
                        "resume_complete": discovery['complete'],
                    },
                    message="Facebook Marketplace: no quedan fichas después del checkpoint.",
                    skill_name=self.name,
                )
            return SkillResult.error(
                message="Facebook Marketplace no devolvió anuncios procesables.",
                skill_name=self.name,
            )
        return SkillResult.ok(
            data={"portal": "facebook_marketplace", **incremental, 'discovery': discovery},
            message=(
                f"Facebook Marketplace ({discovery['stop_reason']}): {incremental['nuevas']} nuevas, "
                f"{incremental['actualizadas']} actualizadas, {incremental['errores']} errores."
            ),
            skill_name=self.name,
        )
