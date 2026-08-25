"""Skill para extraer inventario público de Facebook Marketplace."""

from __future__ import annotations

from typing import Any, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades


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
        url = str(params.get("search_url") or "")
        return not url or "facebook.com/marketplace/" in url

    def execute(self, params: Dict[str, Any], context: Dict[str, Any] = None) -> SkillResult:
        from scrapi.facebook_marketplace_scraper import (
            DEFAULT_MAX_ITEMS,
            DEFAULT_SEARCH_URL,
            run_scraper,
        )

        progress_callback = (context or {}).get("progress_callback")
        incremental = {"total": 0, "nuevas": 0, "actualizadas": 0, "errores": 0}

        def save_batch(rows):
            result = guardar_propiedades(rows, fuente="facebook_marketplace")
            for key in incremental:
                incremental[key] += int(result.get(key, 0) or 0)
            return incremental.copy()

        try:
            rows = run_scraper(
                search_url=params.get("search_url") or DEFAULT_SEARCH_URL,
                max_items=int(params.get("max_items") or DEFAULT_MAX_ITEMS),
                start_index=int(params.get("start_page") or 1),
                progress_callback=progress_callback,
                batch_callback=save_batch,
            )
        except Exception as exc:
            return SkillResult.error(
                message=f"Error en scraper Facebook Marketplace: {exc}",
                skill_name=self.name,
            )
        if not rows:
            return SkillResult.error(
                message="Facebook Marketplace no devolvió anuncios procesables.",
                skill_name=self.name,
            )
        return SkillResult.ok(
            data={"portal": "facebook_marketplace", **incremental},
            message=(
                f"Facebook Marketplace completado: {incremental['nuevas']} nuevas, "
                f"{incremental['actualizadas']} actualizadas, {incremental['errores']} errores."
            ),
            skill_name=self.name,
        )
