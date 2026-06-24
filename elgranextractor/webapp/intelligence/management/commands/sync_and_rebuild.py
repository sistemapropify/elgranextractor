"""
Management command: sync_and_rebuild

Sincroniza una colección RAG y reconstruye el índice FAISS.
Uso:
    python manage.py sync_and_rebuild --collection propiedadespropify
    python manage.py sync_and_rebuild --all
    python manage.py sync_and_rebuild --collection propiedadespropify --force
"""

import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from intelligence.services.rag import RAGService
from intelligence.services.faiss_index import FAISSIndexManager
from intelligence.models import IntelligenceCollection, IntelligenceDocument


class Command(BaseCommand):
    help = 'Sincroniza colección RAG y reconstruye índice FAISS'

    def add_arguments(self, parser):
        parser.add_argument('--collection', type=str, help='Nombre de la colección')
        parser.add_argument('--all', action='store_true', help='Sincronizar todas las colecciones activas')
        parser.add_argument('--force', action='store_true', help='Forzar regeneración de todos los embeddings')

    def handle(self, *args, **options):
        start_time = time.time()
        collection_name = options.get('collection')
        sync_all = options.get('all', False)
        force = options.get('force', False)

        if not collection_name and not sync_all:
            self.stdout.write(self.style.ERROR('Debes especificar --collection o --all'))
            return

        if sync_all:
            collections = IntelligenceCollection.objects.filter(is_active=True)
            self.stdout.write(f'[{timezone.now():%H:%M:%S}] Sincronizando {collections.count()} colecciones...')
        else:
            try:
                collection = IntelligenceCollection.objects.get(name=collection_name, is_active=True)
                collections = [collection]
                self.stdout.write(f'[{timezone.now():%H:%M:%S}] Colección: {collection.name}')
            except IntelligenceCollection.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Colección "{collection_name}" no encontrada'))
                return

        total_created = 0
        total_updated = 0
        total_errors = 0

        for collection in collections:
            self.stdout.write('')
            self.stdout.write(f'{"="*50}')
            self.stdout.write(f'  Sincronizando: {collection.name}')
            self.stdout.write(f'{"="*50}')

            # Paso 1: Sync
            self.stdout.write(f'[{timezone.now():%H:%M:%S}] [INFO] Iniciando sincronización...')
            try:
                success, message, stats = RAGService.sync_collection(
                    collection_id=collection.id,
                    force_full_sync=force
                )

                if success:
                    self.stdout.write(self.style.SUCCESS(
                        f'[{timezone.now():%H:%M:%S}] [OK] Sync completada'
                    ))
                    self.stdout.write(f'  Procesados: {stats["total_processed"]}')
                    self.stdout.write(f'  Creados:    {stats["created"]}')
                    self.stdout.write(f'  Actualizados: {stats["updated"]}')
                    self.stdout.write(f'  Saltados:   {stats["skipped"]}')
                    self.stdout.write(f'  Errores:    {stats["errors"]}')
                    total_created += stats.get('created', 0)
                    total_updated += stats.get('updated', 0)
                    total_errors += stats.get('errors', 0)
                else:
                    self.stdout.write(self.style.ERROR(
                        f'[{timezone.now():%H:%M:%S}] [ERROR] {message}'
                    ))
                    continue

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'[{timezone.now():%H:%M:%S}] [ERROR] Sync falló: {e}'
                ))
                continue

            # Paso 2: FAISS Rebuild
            self.stdout.write(f'[{timezone.now():%H:%M:%S}] [INFO] Reconstruyendo índice FAISS...')
            try:
                indexed = FAISSIndexManager.rebuild_for_collection(
                    collection.name,
                    RAGService.EMBEDDING_DIMENSIONS
                )
                if indexed > 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'[{timezone.now():%H:%M:%S}] [OK] FAISS: {indexed} vectores indexados'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'[{timezone.now():%H:%M:%S}] [WARN] No se indexaron vectores'
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'[{timezone.now():%H:%M:%S}] [ERROR] FAISS rebuild falló: {e}'
                ))

            # Actualizar timestamp
            collection.last_sync_at = timezone.now()
            total_docs = IntelligenceDocument.objects.filter(collection=collection).count()
            collection.last_sync_count = total_docs
            collection.save(update_fields=['last_sync_at', 'last_sync_count'])

            self.stdout.write(self.style.SUCCESS(
                f'[{timezone.now():%H:%M:%S}] [OK] Pipeline completado para {collection.name}'
            ))

        # Resumen
        elapsed = time.time() - start_time
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('  PIPELINE COMPLETADO'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'  Tiempo total: {elapsed:.1f}s')
        self.stdout.write(f'  Creados: {total_created}')
        self.stdout.write(f'  Actualizados: {total_updated}')
        self.stdout.write(f'  Errores: {total_errors}')
        self.stdout.write('')
