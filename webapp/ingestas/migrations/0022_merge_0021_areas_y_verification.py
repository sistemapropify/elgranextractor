from django.db import migrations


class Migration(migrations.Migration):
    """Fusiona las dos ramas 0021 (áreas y verificación) para el grafo de migraciones."""

    dependencies = [
        ('ingestas', '0021_propiedadescompetencia_areas'),
        ('ingestas', '0021_scrapingverification'),
    ]

    operations = []
