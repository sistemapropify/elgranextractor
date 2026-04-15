from django.core.management.base import BaseCommand
from django.utils import timezone
from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection


class Command(BaseCommand):
    help = 'Sincroniza colecciones RAG según configuración (inicializa o sincroniza)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--collection',
            type=int,
            help='ID de la colección específica a sincronizar (si no se especifica, sincroniza todas)'
        )
        parser.add_argument(
            '--initialize',
            action='store_true',
            help='Inicializa colecciones por defecto antes de sincronizar'
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
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== SISTEMA DE SINCRONIZACIÓN RAG ==='))
        self.stdout.write('')
        
        # Opción de inicialización
        if options['initialize']:
            self.stdout.write('1. Inicializando colecciones por defecto...')
            if options['dry_run']:
                self.stdout.write('   [DRY RUN] Se inicializarían colecciones por defecto')
            else:
                try:
                    results = RAGService.initialize_default_collections()
                    self.stdout.write(self.style.SUCCESS(
                        f'   Colecciones inicializadas: {results["total_created"]} creadas, '
                        f'{results["total_skipped"]} saltadas'
                    ))
                    
                    for collection_result in results['collections']:
                        if collection_result['status'] == 'created':
                            self.stdout.write(f'      ✓ {collection_result["name"]}: {collection_result["message"]}')
                        elif collection_result['status'] == 'skipped':
                            self.stdout.write(f'      - {collection_result["name"]}: {collection_result["message"]}')
                        else:
                            self.stdout.write(self.style.WARNING(
                                f'      ✗ {collection_result["name"]}: {collection_result["message"]}'
                            ))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   Error inicializando colecciones: {e}'))
                    return
        
        # Determinar qué colecciones sincronizar
        collection_id = options['collection']
        force_full_sync = options['force']
        dry_run = options['dry_run']
        
        if collection_id:
            self.stdout.write(f'2. Sincronizando colección específica (ID: {collection_id})...')
            collections = IntelligenceCollection.objects.filter(id=collection_id, is_active=True)
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
        for i, collection in enumerate(collections, 1):
            self.stdout.write(f'   [{i}/{total_collections}] Colección: {collection.name} (ID: {collection.id})')
            self.stdout.write(f'      Descripción: {collection.description}')
            self.stdout.write(f'      Última sincronización: {collection.last_sync_at or "Nunca"}')
            self.stdout.write(f'      Documentos en última sync: {collection.last_sync_count or 0}')
            
            if dry_run:
                self.stdout.write('      [DRY RUN] Se sincronizaría esta colección')
                if force_full_sync:
                    self.stdout.write('      [DRY RUN] Modo FORCE: se regenerarían todos los embeddings')
                continue
            
            try:
                # Ejecutar sincronización
                success, message, stats = RAGService.sync_collection(
                    collection_id=collection.id,
                    force_full_sync=force_full_sync
                )
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'      ✓ Sincronización exitosa'))
                    self.stdout.write(f'         Procesados: {stats["total_processed"]}')
                    self.stdout.write(f'         Creados: {stats["created"]}')
                    self.stdout.write(f'         Actualizados: {stats["updated"]}')
                    self.stdout.write(f'         Saltados: {stats["skipped"]}')
                    self.stdout.write(f'         Errores: {stats["errors"]}')
                    
                    # Mostrar tiempo transcurrido
                    if collection.last_sync_at:
                        time_diff = timezone.now() - collection.last_sync_at
                        self.stdout.write(f'         Tiempo desde última sync: {time_diff}')
                else:
                    self.stdout.write(self.style.ERROR(f'      ✗ Error: {message}'))
                    if stats['errors'] > 0:
                        self.stdout.write(f'         Errores: {stats["errors"]}')
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'      ✗ Error inesperado: {e}'))
            
            self.stdout.write('')
        
        # Resumen final
        self.stdout.write(self.style.SUCCESS('=== RESUMEN DE SINCRONIZACIÓN ==='))
        self.stdout.write(f'   Colecciones procesadas: {total_collections}')
        self.stdout.write(f'   Modo: {"DRY RUN" if dry_run else "EJECUCIÓN REAL"}')
        self.stdout.write(f'   Fuerza completa: {"SÍ" if force_full_sync else "NO"}')
        self.stdout.write('')
        
        if not dry_run:
            # Mostrar estadísticas generales
            total_docs = IntelligenceDocument.objects.count()
            docs_with_embedding = IntelligenceDocument.objects.filter(embedding__isnull=False).count()
            
            self.stdout.write('   Estadísticas generales del sistema RAG:')
            self.stdout.write(f'      Total de documentos: {total_docs}')
            self.stdout.write(f'      Documentos con embedding: {docs_with_embedding}')
            self.stdout.write(f'      Cobertura de embeddings: {docs_with_embedding/total_docs*100:.1f}%' if total_docs > 0 else '      Cobertura de embeddings: 0%')
            
            # Verificar que el modelo de embeddings esté cargado
            try:
                embedder = RAGService.get_embedder()
                self.stdout.write(f'      Modelo de embeddings: {RAGService.EMBEDDING_MODEL} (cargado)')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'      Modelo de embeddings: NO CARGADO ({e})'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sincronización RAG completada.'))
        
        # Instrucciones para uso
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('Para ejecutar realmente, elimina el flag --dry-run'))
        
        if not options['initialize'] and IntelligenceCollection.objects.count() == 0:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                'No hay colecciones configuradas. Ejecuta con --initialize para crear colecciones por defecto.'
            ))