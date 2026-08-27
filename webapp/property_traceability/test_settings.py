SECRET_KEY = "traceability-tests"
INSTALLED_APPS = ["django.contrib.contenttypes", "propifai", "property_traceability"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "America/Lima"
