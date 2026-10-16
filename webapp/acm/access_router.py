"""Local preview routes only the new ACM access tables to local SQLite."""
class ACMLocalAccessRouter:
    models = {'acmrolepolicy', 'acmroleaudit', 'acmportalanalysis', 'acmphotoreview'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'acm' and model._meta.model_name in self.models:
            from django.conf import settings
            return settings.ACM_ACCESS_DATABASE

    db_for_write = db_for_read

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        from django.conf import settings
        target = settings.ACM_ACCESS_DATABASE
        if db == target:
            return app_label == 'acm' and model_name in self.models
        if app_label == 'acm' and model_name in self.models:
            return False
        return None
