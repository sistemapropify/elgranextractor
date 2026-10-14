"""COFOPRI archive skill; uses the existing BaseSkill contract, separate ledger."""
from intelligence.skills.base import BaseSkill, SkillResult
from catastro.jobs import start_job
from scrapi.geollaqta_scraper import validate


class ScraperGeollaqtaSkill(BaseSkill):
    name = 'scraper_geollaqta'
    description = 'Archiva lotes catastrales de Geollaqta COFOPRI: reportes, fichas disponibles y fachadas en R2.'
    category = 'custom'
    access_level = 4
    is_active = True
    cacheable = False
    parameters_schema = {
        'ubigeo': {'type': 'string', 'required': True, 'description': 'UBIGEO de Arequipa; Yanahuara: 040126.'},
        'max_lotes': {'type': 'integer', 'required': False, 'description': 'Sólo para pruebas: limitar a 1–500 predios. Omitir para descargar todo el distrito.'},
        'id_lote': {'type': 'string', 'required': False, 'description': 'Un lote catastral específico del distrito.'},
        'reintentar_pendientes': {'type': 'boolean', 'required': False, 'description': 'Volver a consultar fichas o imágenes pendientes.'},
    }

    def validate_params(self, params):
        try:
            validate(params.get('ubigeo'), params.get('max_lotes'), params.get('id_lote'))
            return isinstance(params.get('reintentar_pendientes', False), bool)
        except (ValueError, TypeError):
            return False

    def execute(self, params, context=None):
        if not self.validate_params(params):
            return SkillResult.error('Distrito, cantidad o código de lote no válidos.', skill_name=self.name)
        try:
            job_id = start_job(params['ubigeo'], params.get('max_lotes'), params.get('id_lote'),
                               params.get('reintentar_pendientes', False))
            return SkillResult.ok({'job_id': job_id, 'status': 'queued', 'dashboard': '/catastro/'},
                                  'Descarga catastral iniciada. Consulta el avance en Catastro.', skill_name=self.name)
        except (ValueError, RuntimeError) as exc:
            return SkillResult.error(str(exc), skill_name=self.name)
