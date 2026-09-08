"""Adondevivir: extractor específico con recorrido y persistencia compartidos."""
from intelligence.skills.base import BaseSkill
from scrapi.paged_engine import run_paged
from scrapi.source_config import requested_url
from .db_utils import guardar_propiedades
from .paged_skill import execute_paged_skill


def _ejecutar_scraping(max_paginas=0, start_page=1, source_url=None, url=None,
                       progress_callback=None, batch_callback=None, resume_state=None):
    return run_paged('adondevivir', max_paginas=max_paginas, start_page=start_page,
        source_url=requested_url('adondevivir', {'source_url': source_url or url}),
        progress_callback=progress_callback, batch_callback=batch_callback, resume_state=resume_state)


class ScraperAdondevivirSkill(BaseSkill):
    name = 'scraper_adondevivir'
    description = 'Extrae Adondevivir desde la búsqueda configurada, con cobertura y recuperación verificables.'
    category = 'custom'
    access_level = 1
    is_active = True
    parameters_schema = {
        'source_url': {'type': 'string', 'description': 'URL de búsqueda del portal.', 'required': False},
        'max_paginas': {'type': 'integer', 'description': 'Tope de seguridad; alcanzarlo produce cobertura incompleta.', 'required': False},
    }

    def validate_params(self, params):
        try:
            requested_url('adondevivir', params)
            return int(params.get('max_paginas') or 0) >= 0
        except (ValueError, TypeError):
            return False

    def execute(self, params, context=None):
        return execute_paged_skill(self, 'adondevivir', _ejecutar_scraping,
                                  guardar_propiedades, params, context)
