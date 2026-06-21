"""
PDF Ingestion Service para RAG.
Extrae texto de PDFs, lo chunkifica y lo indexa en colecciones vectoriales.

Chunking strategy:
- 400 palabras por chunk
- 50 palabras de overlap
- Respetar límites de "Artículo" en documentos legales (SUNARP, etc.)

Dependencia: pymupdf (instalar con: pip install pymupdf)
"""

import os
import hashlib
import logging
from typing import List, Optional, Tuple, Dict, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


class PDFIngestionService:
    """Servicio de ingesta de PDFs para RAG."""

    CHUNK_SIZE = 400       # palabras por chunk
    CHUNK_OVERLAP = 50     # palabras de overlap entre chunks consecutivos

    @classmethod
    def extract_text(cls, pdf_path: str) -> Optional[str]:
        """
        Extrae texto de un PDF usando pymupdf (fitz).

        Args:
            pdf_path: Ruta absoluta o relativa al archivo PDF

        Returns:
            Texto completo extraído del PDF, o None si hay error
        """
        if not os.path.exists(pdf_path):
            logger.error(f"Archivo PDF no encontrado: {pdf_path}")
            return None

        try:
            import fitz  # pymupdf

            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

            doc.close()

            if not text_parts:
                logger.warning(f"No se extrajo texto del PDF: {pdf_path}")
                return None

            full_text = "\n".join(text_parts)
            logger.info(
                f"PDF extraído: {os.path.basename(pdf_path)}, "
                f"{len(text_parts)} páginas con texto, "
                f"{len(full_text)} caracteres"
            )
            return full_text

        except ImportError:
            logger.error(
                "pymupdf no está instalado. "
                "Instala con: pip install pymupdf"
            )
            return None
        except Exception as e:
            logger.error(f"Error extrayendo PDF {pdf_path}: {e}")
            return None

    @classmethod
    def chunk_text(cls, text: str) -> List[Dict[str, Any]]:
        """
        Divide texto en chunks con overlap.

        Para documentos legales (SUNARP, regulaciones municipales, etc.),
        respeta límites de "Artículo" para no mezclar artículos en un mismo chunk.

        Args:
            text: Texto completo a chunkificar

        Returns:
            Lista de chunks, cada uno con:
            - content: str (texto del chunk)
            - chunk_index: int
            - word_count: int
            - char_count: int
            - is_legal_document: bool
        """
        if not text or not text.strip():
            return []

        # Detectar si es documento legal (contiene "Artículo" con mayúscula)
        is_legal_doc = "Artículo" in text

        words = text.split()
        chunks = []

        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + cls.CHUNK_SIZE, len(words))
            chunk_words = words[start:end]

            # Para documentos legales, ajustar al límite del Artículo anterior
            if is_legal_doc and end < len(words):
                # Buscar "Artículo" hacia atrás desde end
                for i in range(end - 1, start, -1):
                    if i < len(words) and words[i].startswith('Artículo'):
                        end = i
                        chunk_words = words[start:end]
                        break

            chunk_text = ' '.join(chunk_words)

            if chunk_text.strip():
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_index,
                    'word_count': len(chunk_words),
                    'char_count': len(chunk_text),
                    'is_legal_document': is_legal_doc
                })

            chunk_index += 1

            # Avanzar ventana
            if is_legal_doc:
                # Para documentos legales, no usar overlap para evitar mezclar artículos
                start = end
            else:
                start = end - cls.CHUNK_OVERLAP

            # Evitar loop infinito
            if start >= len(words) or start >= end:
                break

        logger.info(
            f"Texto chunkificado: {len(chunks)} chunks "
            f"(legal_doc={is_legal_doc}, "
            f"chunk_size={cls.CHUNK_SIZE}, overlap={cls.CHUNK_OVERLAP if not is_legal_doc else 0})"
        )
        return chunks

    @classmethod
    def ingest_pdf(
        cls,
        pdf_path: str,
        collection_name: str,
        metadata: Dict[str, Any] = None
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Ingiere un PDF completo en una colección RAG.

        Pipeline:
        1. Extraer texto del PDF con pymupdf
        2. Chunkificar el texto (400 palabras, 50 overlap)
        3. Generar embedding para cada chunk (modo passage)
        4. Crear/actualizar documentos en IntelligenceDocument
        5. Reconstruir índice FAISS si está disponible

        Args:
            pdf_path: Ruta al archivo PDF
            collection_name: Nombre de la colección destino
            metadata: Metadatos adicionales (fuente, fecha, tipo, etc.)

        Returns:
            Tuple (success, message, stats)
        """
        from ..models import IntelligenceCollection, IntelligenceDocument
        from .rag import RAGService

        stats = {
            'chunks_created': 0,
            'chunks_updated': 0,
            'errors': 0,
            'total_chunks': 0
        }

        try:
            # Verificar que la colección existe y está activa
            collection = IntelligenceCollection.objects.get(
                name=collection_name,
                is_active=True
            )

            # Extraer texto del PDF
            text = cls.extract_text(pdf_path)
            if not text:
                return False, "No se pudo extraer texto del PDF", stats

            # Chunkificar
            chunks = cls.chunk_text(text)
            if not chunks:
                return False, "No se generaron chunks del texto extraído", stats

            stats['total_chunks'] = len(chunks)

            pdf_name = os.path.basename(pdf_path)
            # Hash del archivo completo para identificar duplicados
            with open(pdf_path, 'rb') as f:
                pdf_hash = hashlib.md5(f.read()).hexdigest()

            logger.info(
                f"Ingiriendo PDF: {pdf_name} (hash={pdf_hash[:8]}...) "
                f"-> colección '{collection_name}', {len(chunks)} chunks"
            )

            # Crear documentos para cada chunk
            for chunk in chunks:
                try:
                    source_id = f"pdf_{pdf_hash}_{chunk['chunk_index']}"

                    # Construir field_values con metadatos del chunk
                    field_values = {
                        'fuente': pdf_name,
                        'tipo_documento': 'PDF',
                        'pdf_hash': pdf_hash,
                        'chunk_index': chunk['chunk_index'],
                        'word_count': chunk['word_count'],
                        'es_documento_legal': chunk['is_legal_document'],
                        'fecha_ingesta': timezone.now().isoformat(),
                    }
                    if metadata:
                        # Agregar metadatos adicionales sin sobrescribir los base
                        for k, v in metadata.items():
                            if k not in field_values:
                                field_values[k] = v

                    # Generar embedding (modo passage para documentos)
                    embedding = RAGService.generate_embedding(
                        chunk['content'],
                        mode='passage'
                    )

                    # Crear o actualizar documento
                    doc, created = IntelligenceDocument.objects.update_or_create(
                        collection=collection,
                        source_id=source_id,
                        defaults={
                            'content': chunk['content'],
                            'content_hash': RAGService.calculate_content_hash(chunk['content']),
                            'embedding': embedding,
                            'field_values': field_values
                        }
                    )

                    if created:
                        stats['chunks_created'] += 1
                    else:
                        stats['chunks_updated'] += 1

                except Exception as e:
                    logger.error(f"Error procesando chunk {chunk['chunk_index']}: {e}")
                    stats['errors'] += 1

            # Actualizar estadísticas de la colección
            from django.utils import timezone
            collection.last_sync_at = timezone.now()
            collection.save()

            # Reconstruir índice FAISS si está disponible
            try:
                from .faiss_index import FAISSIndexManager
                indexed = FAISSIndexManager.rebuild_for_collection(
                    collection.name,
                    RAGService.EMBEDDING_DIMENSIONS
                )
                if indexed > 0:
                    logger.info(f"Índice FAISS reconstruido tras ingesta PDF: {indexed} vectores")
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Error reconstruyendo FAISS tras ingesta PDF: {e}")

            logger.info(
                f"PDF ingestado: {pdf_name} -> {collection_name}: "
                f"{stats['chunks_created']} creados, "
                f"{stats['chunks_updated']} actualizados, "
                f"{stats['errors']} errores"
            )

            return True, (
                f"PDF '{pdf_name}' ingestado: "
                f"{stats['chunks_created']} chunks creados, "
                f"{stats['chunks_updated']} actualizados"
            ), stats

        except IntelligenceCollection.DoesNotExist:
            return False, f"Colección '{collection_name}' no encontrada o inactiva", stats
        except Exception as e:
            logger.error(f"Error en ingesta de PDF: {e}")
            return False, f"Error en ingesta: {str(e)}", stats
