"""
Comando de sincronización para colecciones vectoriales dinámicas (SPEC-003).

Permite sincronizar colecciones RAG que usan campos dinámicos basados en tablas reales de Azure SQL.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection
import argparse


class Command(BaseCommand):
    help = 'Sincroniza colecciones vectoriales dinámicas usando nombres de campos REALES de tablas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--collection',
            type=str,
            help='Nombre de la colección específica a sincronizar (si no se especifica, sincroniza todas las activas)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar sincronización completa (regenerar todos los embeddings)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar realmente'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Listar todas las colecciones dinámicas disponibles'
        )
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Descubrir tablas disponibles en Azure SQL antes de sincronizar'
        )
        parser.add_argument(
            '--schema',
            type=str,
            default='dbo',
            help='Esquema de base de datos para descubrimiento (default: dbo)'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== SISTEMA DE SINCRONIZACIÓN DE COLECCIONES DINÁMICAS (SPEC-003) ==='))
        self.stdout.write('')
        
        # Opción de descubrimiento de tablas
        if options['discover']:
            self.stdout.write('1. Descubriendo tablas disponibles en Azure SQL...')
            try:
                tables = RAGService.get_available_tables(schema=options['schema'])
                self.stdout.write(self.style.SUCCESS(f'   Encontradas {len(tables)} tablas en esquema "{options["schema"]}":'))
                for i, table in enumerate(tables[:20], 1):  # Mostrar solo las primeras 20
                    self.stdout.write(f'      {i:2d}. {table}')
                if len(tables) > 20:
                    self.stdout.write(f'      ... y {len(tables) - 20} más')
                self.stdout.write('')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error descubriendo tablas: {e}'))
                return
        
        # Opción de listar colecciones
        if options['list']:
            self.stdout.write('2. Listando colecciones dinámicas configuradas...')
            collections = IntelligenceCollection.objects.filter(is_active=True).order_by('name')
            
            if not collections.exists():
                self.stdout.write(self.style.WARNING('   No hay colecciones activas configuradas'))
            else:
                self.stdout.write(f'   Encontradas {collections.count()} colección(es) activa(s):')
                for i, collection in enumerate(collections, 1):
                    table_info = f" (Tabla: {collection.table_name})" if collection.table_name else ""
                    sync_info = f" - Última sync: {collection.last_sync_at}" if collection.last_sync_at else " - Nunca sincronizada"
                    self.stdout.write(f'      {i:2d}. {collection.name}{table_info}')
                    self.stdout.write(f'          Descripción: {collection.description[:80]}...' if len(collection.description) > 80 else f'          Descripción: {collection.description}')
                    self.stdout.write(f'          Campos embedding: {len(collection.embedding_fields)}')
                    self.stdout.write(f'          Campos display: {len(collection.display_fields)}')
                    self.stdout.write(f'          Campos filtro: {len(collection.filter_fields)}')
                    self.stdout.write(f'          Nivel mínimo: {collection.min_level}{sync_info}')
                    self.stdout.write(f'          Dominio: {collection.domain}')
                    self.stdout.write(f'          Público: {collection.is_public}')
                    self.stdout.write('')
            return
        
        # Determinar qué colecciones sincronizar
        collection_name = options['collection']
        force_full_sync = options['force']
        dry_run = options['dry_run']
        
        if collection_name:
            self.stdout.write(f'2. Sincronizando colección específica: "{collection_name}"...')
            collections = IntelligenceCollection.objects.filter(name=collection_name, is_active=True)
        else:
            self.stdout.write('2. Sincronizando todas las colecciones activas...')
            collections = IntelligenceCollection.objects.filter(is_active=True)
        
        if not collections.exists():
            self.stdout.write(self.style.WARNING('   No hay colecciones activas para sincronizar'))
            return
        
        total_collections = collections.count()
        self.stdout.write(f'   Encontradas {total_collections} colección(es) activa(s)')
        self.stdout.write('')
        
        # Sincronizar cada colección
        stats_summary = {
            'total_collections': total_collections,
            'successful': 0,
            'failed': 0,
            'total_documents_processed': 0,
            'total_documents_created': 0,
            'total_documents_updated': 0
        }
        
        for i, collection in enumerate(collections, 1):
            self.stdout.write(f'   [{i}/{total_collections}] Colección: {collection.name}')
            self.stdout.write(f'      Tabla origen: {collection.table_name or "No configurada (colección estática)"}')
            self.stdout.write(f'      Descripción: {collection.description[:100]}...' if len(collection.description) > 100 else f'      Descripción: {collection.description}')
            self.stdout.write(f'      Última sincronización: {collection.last_sync_at or "Nunca"}')
            self.stdout.write(f'      Documentos en última sync: {collection.last_sync_count or 0}')
            
            # Verificar si es una colección dinámica (tiene table_name)
            if not collection.table_name:
                self.stdout.write(self.style.WARNING('      ⚠️  Esta colección no tiene table_name configurado (no es dinámica)'))
                self.stdout.write('      Saltando...')
                self.stdout.write('')
                continue
            
            if dry_run:
                self.stdout.write('      [DRY RUN] Se sincronizaría esta colección dinámica')
                if force_full_sync:
                    self.stdout.write('      [DRY RUN] Modo FORCE: se regenerarían todos los embeddings')
                self.stdout.write('')
                continue
            
            try:
                # Ejecutar sincronización dinámica
                success, message, stats = RAGService.sync_collection_dynamic(
                    collection_name=collection.name,
                    force_full_sync=force_full_sync
                )
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'      ✓ Sincronización dinámica exitosa'))
                    self.stdout.write(f'         Procesados: {stats["total_processed"]}')
                    self.stdout.write(f'         Creados: {stats["created"]}')
                    self.stdout.write(f'         Actualizados: {stats["updated"]}')
                    self.stdout.write(f'         Saltados: {stats["skipped"]}')
                    self.stdout.write(f'         Errores: {stats["errors"]}')
                    
                    # Actualizar estadísticas del resumen
                    stats_summary['successful'] += 1
                    stats_summary['total_documents_processed'] += stats['total_processed']
                    stats_summary['total_documents_created'] += stats['created']
                    stats_summary['total_documents_updated'] += stats['updated']
                    
                    # Mostrar tiempo transcurrido
                    if collection.last_sync_at:
                        time_diff = timezone.now() - collection.last_sync_at
                        self.stdout.write(f'         Tiempo desde última sync: {time_diff}')
                else:
                    self.stdout.write(self.style.ERROR(f'      ✗ Error: {message}'))
                    stats_summary['failed'] += 1
                    if stats['errors'] > 0:
                        self.stdout.write(f'         Errores: {stats["errors"]}')
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'      ✗ Error inesperado: {e}'))
                stats_summary['failed'] += 1
            
            self.stdout.write('')
        
        # Resumen final
        self.stdout.write(self.style.SUCCESS('=== RESUMEN DE SINCRONIZACIÓN DINÁMICA ==='))
        self.stdout.write(f'   Colecciones procesadas: {stats_summary["total_collections"]}')
        self.stdout.write(f'   Colecciones exitosas: {stats_summary["successful"]}')
        self.stdout.write(f'   Colecciones fallidas: {stats_summary["failed"]}')
        self.stdout.write(f'   Documentos totales procesados: {stats_summary["total_documents_processed"]}')
        self.stdout.write(f'   Documentos creados: {stats_summary["total_documents_created"]}')
        self.stdout.write(f'   Documentos actualizados: {stats_summary["total_documents_updated"]}')
        self.stdout.write(f'   Modo: {"DRY RUN" if dry_run else "EJECUCIÓN REAL"}')
        self.stdout.write(f'   Fuerza completa: {"SÍ" if force_full_sync else "NO"}')
        self.stdout.write('')
        
        if not dry_run:
            # Mostrar estadísticas generales del sistema RAG
            from intelligence.models import IntelligenceDocument
            total_docs = IntelligenceDocument.objects.count()
            docs_with_embedding = IntelligenceDocument.objects.filter(embedding__isnull=False).count()
            
            self.stdout.write('   Estadísticas generales del sistema RAG:')
            self.stdout.write(f'      Total de documentos en sistema: {total_docs}')
            self.stdout.write(f'      Documentos con embedding: {docs_with_embedding}')
            if total_docs > 0:
                coverage = docs_with_embedding / total_docs * 100
                self.stdout.write(f'      Cobertura de embeddings: {coverage:.1f}%')
            
            # Verificar que el modelo de embeddings esté cargado
            try:
                embedder = RAGService.get_embedder()
                self.stdout.write(f'      Modelo de embeddings: {RAGService.EMBEDDING_MODEL} (cargado)')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'      Modelo de embeddings: NO CARGADO ({e})'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sincronización de colecciones dinámicas completada.'))
        
        # Instrucciones para uso
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('Para ejecutar realmente, elimina el flag --dry-run'))
        
        if stats_summary['failed'] > 0:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'{stats_summary["failed"]} colección(es) fallaron. Revisa los logs para más detalles.'
            ))
        
        # Mostrar comandos útiles
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE('Comandos útiles:'))
        self.stdout.write('   python manage.py sync_vector_collections --list')
        self.stdout.write('   python manage.py sync_vector_collections --discover --schema dbo')
        self.stdout.write('   python manage.py sync_vector_collections --collection "nombre_coleccion"')
        self.stdout.write('   python manage.py sync_vector_collections --force')