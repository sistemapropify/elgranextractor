"""
Comando de management para pre-cargar el modelo de embeddings y verificar el singleton.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import logging
import time

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Pre-carga el modelo de embeddings y verifica el funcionamiento del singleton'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar reinicialización del modelo'
        )
        parser.add_argument(
            '--test-cache',
            action='store_true',
            help='Probar caché de embeddings con consultas de prueba'
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Limpiar caché de embeddings antes de la prueba'
        )
    
    def handle(self, *args, **options):
        from intelligence.services.rag import RAGService
        
        force = options['force']
        test_cache = options['test_cache']
        clear_cache = options['clear_cache']
        
        self.stdout.write(self.style.SUCCESS('=== PRE-CARGA DE MODELO DE EMBEDDINGS ==='))
        self.stdout.write(f'Fecha/hora: {timezone.now()}')
        self.stdout.write(f'Modelo: {RAGService.EMBEDDING_MODEL}')
        self.stdout.write(f'Dimensiones: {RAGService.EMBEDDING_DIMENSIONS}')
        self.stdout.write('')
        
        # 1. Verificar estado actual
        self.stdout.write('1. Verificando estado actual del singleton...')
        initial_status = RAGService.get_embedder_status()
        self.stdout.write(f'   - Modelo cargado: {initial_status["loaded"]}')
        self.stdout.write(f'   - Tamaño de caché: {initial_status["cache_size"]}')
        self.stdout.write(f'   - Hits de caché: {initial_status.get("cache_hits", 0)}')
        self.stdout.write(f'   - Misses de caché: {initial_status.get("cache_misses", 0)}')
        
        # 2. Limpiar caché si se solicita
        if clear_cache:
            self.stdout.write('2. Limpiando caché de embeddings...')
            cleared = RAGService.clear_embedding_cache()
            self.stdout.write(f'   - Elementos eliminados: {cleared}')
        
        # 3. Pre-cargar modelo
        self.stdout.write('3. Pre-cargando modelo de embeddings...')
        start_time = time.time()
        
        try:
            success = RAGService.preload_embedder()
            load_time = time.time() - start_time
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Modelo pre-cargado exitosamente en {load_time:.2f} segundos'))
            else:
                self.stdout.write(self.style.ERROR('   ✗ Error al pre-cargar modelo'))
                return
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error: {e}'))
            return
        
        # 4. Verificar estado después de la carga
        self.stdout.write('4. Verificando estado después de la carga...')
        final_status = RAGService.get_embedder_status()
        self.stdout.write(f'   - Modelo cargado: {final_status["loaded"]}')
        self.stdout.write(f'   - Tamaño de caché: {final_status["cache_size"]}')
        
        # 5. Probar caché si se solicita
        if test_cache:
            self.stdout.write('5. Probando caché de embeddings...')
            test_queries = [
                "Propiedades en Cayma",
                "Departamentos en Yanahuara",
                "Casas en Miraflores",
                "Terrenos en Cerro Colorado",
                "Locales comerciales en Cercado"
            ]
            
            # Primera ronda (misses de caché)
            self.stdout.write('   - Primera ronda (misses de caché):')
            first_round_times = []
            for i, query in enumerate(test_queries, 1):
                start_time = time.time()
                embedding = RAGService.generate_embedding(query, use_cache=True)
                elapsed = time.time() - start_time
                first_round_times.append(elapsed)
                self.stdout.write(f'     {i}. "{query[:30]}..." - {elapsed:.3f}s')
            
            # Segunda ronda (hits de caché)
            self.stdout.write('   - Segunda ronda (hits de caché):')
            second_round_times = []
            for i, query in enumerate(test_queries, 1):
                start_time = time.time()
                embedding = RAGService.generate_embedding(query, use_cache=True)
                elapsed = time.time() - start_time
                second_round_times.append(elapsed)
                self.stdout.write(f'     {i}. "{query[:30]}..." - {elapsed:.3f}s')
            
            # Estadísticas
            avg_first = sum(first_round_times) / len(first_round_times)
            avg_second = sum(second_round_times) / len(second_round_times)
            speedup = avg_first / avg_second if avg_second > 0 else 0
            
            self.stdout.write('   - Estadísticas de caché:')
            self.stdout.write(f'     • Tiempo promedio primera ronda: {avg_first:.3f}s')
            self.stdout.write(f'     • Tiempo promedio segunda ronda: {avg_second:.3f}s')
            self.stdout.write(f'     • Aceleración: {speedup:.1f}x')
            
            if speedup > 5:
                self.stdout.write(self.style.SUCCESS(f'     ✓ Caché funcionando correctamente ({speedup:.1f}x más rápido)'))
            else:
                self.stdout.write(self.style.WARNING(f'     ⚠ Caché con aceleración limitada ({speedup:.1f}x)'))
        
        # 6. Estado final
        self.stdout.write('6. Estado final del singleton:')
        final_status = RAGService.get_embedder_status()
        
        for key, value in final_status.items():
            if key == 'loaded':
                status_style = self.style.SUCCESS if value else self.style.ERROR
                self.stdout.write(f'   - {key}: {status_style(str(value))}')
            elif key in ['cache_hits', 'cache_misses']:
                self.stdout.write(f'   - {key}: {value}')
            elif key == 'cache_size':
                self.stdout.write(f'   - {key}: {value} elementos')
            else:
                self.stdout.write(f'   - {key}: {value}')
        
        # 7. Recomendaciones
        self.stdout.write('')
        self.stdout.write('7. Recomendaciones:')
        
        if not final_status['loaded']:
            self.stdout.write(self.style.ERROR('   • El modelo NO está cargado. Verificar dependencias.'))
        elif final_status['cache_size'] == 0:
            self.stdout.write(self.style.WARNING('   • La caché está vacía. Considerar pre-cargar consultas frecuentes.'))
        else:
            self.stdout.write(self.style.SUCCESS('   • Singleton funcionando correctamente.'))
        
        # 8. Para producción
        self.stdout.write('')
        self.stdout.write('8. Para producción:')
        self.stdout.write('   • Agregar este comando al startup.sh para pre-cargar al iniciar')
        self.stdout.write('   • Configurar variables de entorno:')
        self.stdout.write('     - RAG_EMBEDDING_CACHE_SIZE=100 (tamaño de caché)')
        self.stdout.write('     - RAG_SIMILARITY_THRESHOLD=0.7 (umbral de similitud)')
        self.stdout.write('     - RAG_MAX_RESULTS=10 (resultados máximos)')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== PRE-CARGA COMPLETADA ==='))