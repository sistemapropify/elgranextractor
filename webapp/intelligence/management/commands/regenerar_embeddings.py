"""
Comando para regenerar embeddings para todos los documentos de una colección
o para todos los documentos sin embedding.
Usa el RAGService existente para mantener consistencia.
"""

from django.core.management.base import BaseCommand
from intelligence.models import IntelligenceDocument, IntelligenceCollection
from intelligence.services.rag import RAGService
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Regenera embeddings para documentos de inteligencia usando RAGService'

    def add_arguments(self, parser):
        parser.add_argument(
            '--collection',
            type=str,
            help='Nombre de la colección (ej: propiedades_propify)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerar embeddings para todos los documentos (incluye los que ya tienen embedding)'
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            default=False,
            help='Solo regenerar embeddings para documentos sin embedding'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Forzar regeneración de embeddings aunque ya existan (sinónimo de --all)'
        )

    def handle(self, *args, **options):
        collection_name = options.get('collection')
        regenerate_all = options.get('all') or options.get('force', False)
        missing_only = options.get('missing_only', False)
        
        self.stdout.write(self.style.SUCCESS('=== REGENERANDO EMBEDDINGS ==='))
        
        # Inicializar el modelo de embeddings usando RAGService
        try:
            self.stdout.write('Inicializando modelo de embeddings via RAGService...')
            embedder = RAGService.initialize_embedder()
            self.stdout.write(self.style.SUCCESS(f'Modelo cargado: {RAGService.EMBEDDING_MODEL}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error cargando modelo: {e}'))
            return
        
        # Obtener documentos a procesar
        queryset = IntelligenceDocument.objects.all()
        
        if collection_name:
            try:
                collection = IntelligenceCollection.objects.get(name=collection_name)
                queryset = queryset.filter(collection=collection)
                self.stdout.write(f'Filtrando por colección: {collection_name}')
                self.stdout.write(f'Documentos en colección: {queryset.count()}')
            except IntelligenceCollection.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Colección no encontrada: {collection_name}'))
                return
        
        if missing_only and not regenerate_all:
            queryset = queryset.filter(embedding__isnull=True)
            self.stdout.write(f'Documentos sin embedding: {queryset.count()}')
        elif regenerate_all:
            self.stdout.write(self.style.WARNING('Forzando regeneración de TODOS los embeddings (incluyendo los existentes)'))
        
        total = queryset.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No hay documentos para procesar'))
            return
        
        self.stdout.write(f'Procesando {total} documentos...')
        
        success_count = 0
        error_count = 0
        
        for i, doc in enumerate(queryset, 1):
            try:
                # Preparar texto para embedding
                text_to_embed = self._prepare_text_for_embedding(doc)
                
                if not text_to_embed:
                    self.stdout.write(self.style.WARNING(f'Documento {doc.id} sin contenido para embedding'))
                    error_count += 1
                    continue
                
                # Generar embedding usando RAGService (modo passage para documentos)
                embedding_bytes = RAGService.generate_embedding(text_to_embed, mode='passage')
                
                if embedding_bytes is None:
                    self.stdout.write(self.style.WARNING(f'No se pudo generar embedding para documento {doc.id}'))
                    error_count += 1
                    continue
                
                # Actualizar documento
                doc.embedding = embedding_bytes
                doc.save(update_fields=['embedding'])
                
                success_count += 1
                
                if i % 10 == 0:
                    self.stdout.write(f'Procesados {i}/{total} documentos...')
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error procesando documento {doc.id}: {e}'))
                error_count += 1
                logger.error(f'Error regenerando embedding para documento {doc.id}: {e}')
        
        # Resumen
        self.stdout.write(self.style.SUCCESS('\n=== RESUMEN ==='))
        self.stdout.write(f'Total documentos procesados: {total}')
        self.stdout.write(f'Embeddings regenerados exitosamente: {success_count}')
        self.stdout.write(f'Errores: {error_count}')
        
        if success_count > 0:
            self.stdout.write(self.style.SUCCESS('¡Embeddings regenerados exitosamente!'))
        else:
            self.stdout.write(self.style.WARNING('No se regeneraron embeddings'))

    def _prepare_text_for_embedding(self, doc):
        """Prepara el texto para generar embedding"""
        text_parts = []
        
        # Intentar extraer información del contenido
        content = doc.content
        
        # Si el contenido es JSON, extraer campos relevantes
        try:
            data = json.loads(content)
            
            # Campos importantes para propiedades
            important_fields = [
                'title', 'description', 'real_address', 'exact_address',
                'district', 'province', 'urbanization', 'property_type',
                'property_subtype', 'price', 'bedrooms', 'bathrooms',
                'built_area', 'land_area'
            ]
            
            for field in important_fields:
                if field in data and data[field]:
                    value = data[field]
                    if isinstance(value, (str, int, float)):
                        text_parts.append(f"{field}: {value}")
            
            # Si no encontramos campos estructurados, usar todo el JSON
            if not text_parts:
                text_parts.append(str(data))
                
        except json.JSONDecodeError:
            # El contenido no es JSON, usar texto plano
            text_parts.append(content)
        
        # Agregar información de field_values si existe
        if doc.field_values:
            try:
                field_data = json.loads(doc.field_values)
                for key, value in field_data.items():
                    if value and isinstance(value, (str, int, float)):
                        text_parts.append(f"{key}: {value}")
            except:
                pass
        
        # Unir todas las partes
        return " ".join(str(part) for part in text_parts if part)