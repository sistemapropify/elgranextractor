"""
Database routers for multiple database support.
"""

class PropifaiRouter:
    """
    A router to control all database operations on models in the propifai application.
    """
    
    # List of app labels that should use the 'propifai' database
    propifai_apps = {'propifai'}  # We'll create this app later
    
    def db_for_read(self, model, **hints):
        """
        Attempts to read propifai models go to propifai database.
        """
        if model._meta.app_label in self.propifai_apps:
            return 'propifai'
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write propifai models go to propifai database.
        """
        if model._meta.app_label in self.propifai_apps:
            return 'propifai'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both models are in the same database.
        """
        db1 = self.db_for_read(obj1.__class__) if obj1 else None
        db2 = self.db_for_read(obj2.__class__) if obj2 else None
        if db1 and db2:
            return db1 == db2
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the propifai app only appears in the 'propifai' database.
        """
        if app_label in self.propifai_apps:
            return db == 'propifai'
        # Other apps can go to default database
        if db == 'propifai':
            return False
        return None


class DefaultRouter:
    """
    Default router for all other apps.
    """
    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == 'default'