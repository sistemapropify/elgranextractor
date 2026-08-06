from django.apps import AppConfig


class N8NBridgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "n8n_bridge"

    def ready(self):
        from intelligence.skills.registry import SkillRegistry
        from intelligence.skills.propiedades.informacion_inicial_propiedad import (
            InformacionInicialPropiedadSkill,
        )

        SkillRegistry().register(InformacionInicialPropiedadSkill)