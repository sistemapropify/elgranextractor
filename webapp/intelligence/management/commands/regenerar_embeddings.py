"""
Comando para regenerar embeddings para documentos de inteligencia.

Útil cuando:
- Se cambió el modelo de embeddings (ej: de 1024d a 384d)
- Documentos nuevos no tienen embedding
- Se necesita forzar regeneración completa

Usa RAGService para mantener consistencia con el modelo actual.
"""
import logging
import numpy as np

from django.core.management.base import BaseCommand
from intelligence.models import IntelligenceDocument, IntelligenceCollection
from intelligence.services.rag import RAGService

logger = logging.getLogger(__name__)

# Dimensión esperada del modelo actual (SPEC-014: multilingual-e5-small)
EMBEDDING_DIMENSION = 384


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
            help='Regenerar embeddings para TODOS los documentos (incluye los que ya tienen embedding)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Sinónimo de --all'
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            default=False,
            help='Solo regenerar embeddings para documentos sin embedding'
        )
        parser.add_argument(
            '--fix-dimensions',
            action='store_true',
            default=False,
            help=(
                'Detectar y regenerar solo documentos con dimensión de embedding '
                'incorrecta (ej: 1024d antiguos → 384d actuales). '
                'Útil después de migrar de modelo de embeddings.'
            )
        )

    def handle(self, *args, **options):
        collection_name = options.get('collection')
        regenerate_all = options.get('all') or options.get('force', False)
        missing_only = options.get('missing_only', False)
        fix_dimensions = options.get('fix_dimensions', False)

        self.stdout.write(self.style.SUCCESS('=== REGENERANDO EMBEDDINGS ==='))
        self.stdout.write(f'Modelo actual: {RAGService.EMBEDDING_MODEL} ({RAGService.EMBEDDING_DIMENSIONS}d)')

        # Inicializar el modelo de embeddings usando RAGService
        try:
            self.stdout.write('Inicializando modelo de embeddings...')
            embedder = RAGService.initialize_embedder()
            if embedder is None:
                self.stdout.write(self.style.ERROR('No se pudo inicializar el modelo de embeddings'))
                return
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
            except IntelligenceCollection.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Colección no encontrada: {collection_name}'))
                return

        if fix_dimensions:
            # Detectar documentos con dimensión incorrecta
            todos = list(queryset.filter(embedding__isnull=False))
            docs_con_dimension_incorrecta = []
            docs_sin_embedding = list(queryset.filter(embedding__isnull=True))

            for doc in todos:
                if doc.embedding:
                    vector = np.frombuffer(doc.embedding, dtype=np.float32)
                    if vector.shape[0] != EMBEDDING_DIMENSION:
                        docs_con_dimension_incorrecta.append(doc)

            total_incorrectos = len(docs_con_dimension_incorrecta)
            total_sin_embedding = len(docs_sin_embedding)
            self.stdout.write(
                f'Documentos con dimensión incorrecta: {total_incorrectos} '
                f'(se regenerarán)'
            )
            self.stdout.write(
                f'Documentos sin embedding: {total_sin_embedding} '
                f'(se crearán)'
            )
            self.stdout.write(
                f'Documentos con dimensión correcta: '
                f'{len(todos) - total_incorrectos} (se saltarán)'
            )

            # Combinar: incorrectos + sin embedding
            queryset_ids = [d.id for d in docs_con_dimension_incorrecta] + \
                           [d.id for d in docs_sin_embedding]
            queryset = IntelligenceDocument.objects.filter(id__in=queryset_ids)

            total = queryset.count()
            if total == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        'Todos los documentos ya tienen la dimensión correcta. '
                        'No es necesario regenerar.'
                    )
                )
                return
        elif missing_only and not regenerate_all:
            queryset = queryset.filter(embedding__isnull=True)
            self.stdout.write(f'Documentos sin embedding: {queryset.count()}')
        elif regenerate_all:
            self.stdout.write(
                self.style.WARNING(
                    'Regenerando TODOS los embeddings '
                    '(incluyendo los existentes con dimensión correcta)...'
                )
            )

        total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.WARNING('No hay documentos para procesar'))
            return

        self.stdout.write(f'Procesando {total} documentos...')

        success_count = 0
        error_count = 0

        for i, doc in enumerate(queryset, 1):
            try:
                # Preparar texto para embedding:
                # Usar doc.content directamente (texto plano concatenado)
                # que ya contiene los campos relevantes unidos.
                text_to_embed = doc.content or ''

                # Si no hay content, intentar con field_values
                if not text_to_embed.strip() and doc.field_values:
                    text_parts = []
                    for key, value in doc.field_values.items():
                        if value is not None and value != '':
                            text_parts.append(f"{key}: {value}")
                    text_to_embed = " | ".join(text_parts)

                if not text_to_embed.strip():
                    self.stdout.write(
                        self.style.WARNING(f'Documento {doc.id} sin contenido para embedding')
                    )
                    error_count += 1
                    continue

                # Generar embedding usando RAGService (modo passage para documentos)
                embedding_bytes = RAGService.generate_embedding(
                    text_to_embed, mode='passage'
                )

                if embedding_bytes is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f'No se pudo generar embedding para documento {doc.id}'
                        )
                    )
                    error_count += 1
                    continue

                # Actualizar documento
                doc.embedding = embedding_bytes
                doc.save(update_fields=['embedding'])

                success_count += 1

                if i % 10 == 0:
                    self.stdout.write(f'Procesados {i}/{total} documentos...')

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error procesando documento {doc.id}: {e}')
                )
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