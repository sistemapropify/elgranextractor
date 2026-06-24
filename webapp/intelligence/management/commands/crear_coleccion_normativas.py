"""
Management command para crear la colección "normativas_legales"
optimizada para documentos legales (leyes, ordenanzas, decretos).

Uso: python manage.py crear_coleccion_normativas
"""

import json
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Crea la colección normativas_legales para documentos PDF legales'

    def handle(self, *args, **options):
        from intelligence.models import IntelligenceCollection

        nombre = 'normativas_legales'

        # Verificar si ya existe
        if IntelligenceCollection.objects.filter(name=nombre).exists():
            self.stdout.write(self.style.WARNING(
                f"La colección '{nombre}' ya existe. No se creó de nuevo."
            ))
            return

        # Obtener DB alias
        db_alias = getattr(settings, 'NORMATIVAS_DB_ALIAS', None)

        coleccion = IntelligenceCollection.objects.create(
            name=nombre,
            source_sql='',
            embedding_fields=['title', 'content', 'fuente'],
            display_fields=[
                'title', 'fuente', 'tipo_documento',
                'estructura_tipo', 'estructura_titulo',
                'estructura_contenedor',
            ],
            filter_fields=[
                'tipo_documento', 'fuente', 'estructura_tipo',
            ],
            min_level=1,
            is_active=True,
            is_public=True,
            domain='general',
            description=(
                "Documentos legales y normativos: leyes, ordenanzas municipales, "
                "decretos, resoluciones. Los chunks respetan la estructura de "
                "artículos, capítulos y títulos del documento original."
            ),
            database_alias=db_alias or '',
        )

        self.stdout.write(self.style.SUCCESS(
            f"✅ Colección '{nombre}' creada (ID: {coleccion.id})\n"
            f"   Display fields: title, fuente, tipo_documento, estructura_tipo\n"
            f"   Filter fields: tipo_documento, fuente, estructura_tipo\n"
            f"   Access level: {coleccion.access_level}\n\n"
            f"Para subir un PDF usa:\n"
            f"   curl -X POST http://localhost:8000/intelligence/rag/collections/"
            f"{nombre}/ingest-pdf/ \\\n"
            f"     -F \"file=@documento.pdf\" \\\n"
            f"     -F \"metadata={{\\\"titulo\\\": \\\"Ley 123\\\", "
            f"\\\"tipo_norma\\\": \\\"Ley\\\"}}\""
        ))
