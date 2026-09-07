from django.apps import AppConfig


class N8NBridgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "n8n_bridge"

    def ready(self):
        import sys
        if 'run_lead_control' in sys.argv:
            return
        from intelligence.skills.registry import SkillRegistry
        from intelligence.skills.propiedades.informacion_inicial_propiedad import (
            InformacionInicialPropiedadSkill,
        )

        SkillRegistry().register(InformacionInicialPropiedadSkill)
