from django.apps import AppConfig


class IngestasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingestas'

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from .models import PropiedadesCompetencia, RevisionPropiedadScraping
        from .ml_candidates import safe_capture

        def property_saved(sender, instance, raw=False, **kwargs):
            if not raw:
                safe_capture(instance.pk, 'property_save')

        def review_changed(sender, instance, raw=False, **kwargs):
            if not raw:
                safe_capture(instance.propiedad_id, 'manual_review')

        post_save.connect(property_saved, sender=PropiedadesCompetencia, weak=False, dispatch_uid='ml_property_capture_v1')
        post_save.connect(review_changed, sender=RevisionPropiedadScraping, weak=False, dispatch_uid='ml_review_capture_v1')
        post_delete.connect(review_changed, sender=RevisionPropiedadScraping, weak=False, dispatch_uid='ml_review_delete_v1')
