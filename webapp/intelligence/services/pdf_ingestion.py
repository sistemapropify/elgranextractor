"""
PDF Ingestion Service para RAG.
Extrae texto de PDFs, lo chunkifica y lo indexa en colecciones vectoriales.

Chunking strategy:
- Documentos estructurados (leyes, normas): chunk por ARTÍCULO, CAPÍTULO, TÍTULO
- Documentos no estructurados: chunk por palabras (400 palabras, 50 overlap)

Dependencias:
  - pymupdf (fitz): extracción de texto de PDFs digitales
  - pytesseract + Tesseract OCR: OCR para PDFs escaneados
  - pdf2image: convierte páginas PDF a imágenes para OCR

Instalación:
  pip install pytesseract pdf2image
  # Tesseract OCR: winget install UB-Mannheim.TesseractOCR
  # Idioma español: descargar spa.traineddata a tessdata/
"""

import os
import hashlib
import re
import logging
import traceback
from typing import List, Optional, Tuple, Dict, Any
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Configuración de OCR ──
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# Directorio tessdata: primero busca en la raíz del proyecto (d:\PROMETEO\tessdata),
# luego en la carpeta del sistema donde instaló Tesseract
TESSDATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tessdata")
TESSDATA_DIR = os.path.abspath(TESSDATA_DIR)
if not os.path.isdir(TESSDATA_DIR):
    TESSDATA_DIR = r"C:\Program Files\Tesseract-OCR\tessdata"

# Umbral: si el texto extraído por pymupdf tiene menos de este % del peso del PDF,
# se considera que el PDF es escaneado y se activa OCR.
# Ej: PDF de 100KB con solo 2KB de texto extraído → 2% → se activa OCR
OCR_TEXT_RATIO_THRESHOLD = 0.15  # 15%: si el texto extraído es < 15% del peso del PDF
OCR_MAX_CHARS_WITHOUT_OCR = 2000  # Si hay menos de 2000 chars, activar OCR (texto muy corto)


# Patrones de estructura para documentos legales peruanos
PATRONES_ESTRUCTURA = [
    ('titulo', re.compile(r'^TÍTULO\s+[IVXLCDM]+\b', re.MULTILINE)),
    ('capitulo', re.compile(r'^CAPÍTULO\s+[IVXLCDM]+\b', re.MULTILINE)),
    ('seccion', re.compile(r'^SECCIÓN\s+\w+', re.MULTILINE)),
    ('articulo', re.compile(r'^Art[ií]culo\s+\d+[°º]?\.?\s*[-—]?\s*', re.MULTILINE)),
    ('anexo', re.compile(r'^ANEXO\s+\w+', re.MULTILINE)),
    ('disposicion', re.compile(r'^(DISPOSICIÓN|DISPOSICIONES)\s+(COMPLEMENTARIA|FINAL|TRANSITORIA|DEROGATORIA)', re.MULTILINE)),
]


class PDFIngestionService:
    """Servicio de ingesta de PDFs para RAG."""

    CHUNK_SIZE = 400       # palabras por chunk (solo para no estructurados)
    CHUNK_OVERLAP = 50     # palabras de overlap entre chunks consecutivos

    # ============================================================
    # EXTRACCIÓN DE TEXTO
    # ============================================================

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

            full_text = "\n".join(text_parts) if text_parts else ""
            pdf_size = os.path.getsize(pdf_path)

            logger.info(
                f"PDF extraído: {os.path.basename(pdf_path)}, "
                f"{len(text_parts)} páginas con texto, "
                f"{len(full_text)} caracteres, "
                f"tamaño={pdf_size} bytes"
            )

            # ── Detectar si el PDF es escaneado y necesita OCR ──
            needs_ocr = False
            if not full_text.strip():
                needs_ocr = True
                logger.info("PDF sin texto extraíble. Activando OCR...")
            elif len(full_text) < OCR_MAX_CHARS_WITHOUT_OCR:
                # Muy poco texto extraído → probablemente escaneado
                needs_ocr = True
                logger.info(
                    f"PDF con poco texto: {len(full_text)} chars "
                    f"(umbral={OCR_MAX_CHARS_WITHOUT_OCR}). Activando OCR..."
                )
            elif pdf_size > 50000:
                # PDF grande: verificar relación texto/peso
                ratio = len(full_text) / max(pdf_size, 1)
                if ratio < OCR_TEXT_RATIO_THRESHOLD:
                    needs_ocr = True
                    logger.info(
                        f"PDF probablemente escaneado: {len(full_text)} chars "
                        f"en {pdf_size} bytes (ratio={ratio:.2%} < {OCR_TEXT_RATIO_THRESHOLD:.0%}). "
                        f"Activando OCR..."
                    )

            if needs_ocr:
                ocr_text = cls._ocr_pdf(pdf_path)
                if ocr_text and len(ocr_text) > len(full_text):
                    logger.info(
                        f"OCR exitoso: {len(ocr_text)} caracteres extraídos "
                        f"({len(text_parts) if text_parts else 0} páginas pymupdf → OCR)"
                    )
                    return ocr_text
                else:
                    logger.warning(
                        f"OCR no mejoró la extracción. "
                        f"Usando texto de pymupdf ({len(full_text)} chars)."
                    )

            if not full_text.strip():
                return None

            return full_text

        except ImportError as e:
            if 'fitz' in str(e):
                logger.error(
                    "pymupdf no está instalado. "
                    "Instala con: pip install pymupdf"
                )
            else:
                logger.error(f"Error de importación: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extrayendo PDF {pdf_path}: {e}")
            return None

    # ============================================================
    # OCR (para PDFs escaneados)
    # ============================================================

    @classmethod
    def _ocr_pdf(cls, pdf_path: str) -> Optional[str]:
        """
        Extrae texto de un PDF escaneado usando OCR (Tesseract).
        Convierte cada página a imagen con pymupdf (fitz) — no necesita poppler.

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Texto completo extraído, o None si falla
        """
        try:
            import fitz  # pymupdf (ya instalado)
            import pytesseract
            from PIL import Image
            import io

            # Configurar ruta de Tesseract
            if os.path.exists(TESSERACT_CMD):
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

            # Configurar ruta de tessdata (idiomas)
            if os.path.isdir(TESSDATA_DIR):
                os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

            logger.info(
                f"Iniciando OCR para: {os.path.basename(pdf_path)} "
                f"(tesseract={TESSERACT_CMD}, tessdata={TESSDATA_DIR})"
            )

            # Abrir PDF con pymupdf
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            ocr_text_parts = []

            for idx in range(total_pages):
                page = doc[idx]
                logger.info(f"OCR página {idx + 1}/{total_pages}...")

                # Renderizar página como PNG a 300 DPI
                zoom = 300.0 / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # Convertir a PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # OCR en español + inglés
                page_text = pytesseract.image_to_string(
                    img,
                    lang='spa+eng',
                    config='--psm 6'
                )

                if page_text.strip():
                    ocr_text_parts.append(page_text.strip())

            doc.close()

            if not ocr_text_parts:
                logger.warning(f"OCR no extrajo texto de ninguna página")
                return None

            full_text = "\n\n".join(ocr_text_parts)
            logger.info(
                f"OCR completado: {len(ocr_text_parts)}/{total_pages} páginas "
                f"con texto, {len(full_text)} caracteres"
            )
            return full_text

        except ImportError as e:
            logger.warning(
                f"No se pudo usar OCR: {e}. "
                f"Verifica que pymupdf y pytesseract estén instalados."
            )
            return None
        except Exception as e:
            logger.error(f"Error en OCR para {pdf_path}: {e}\n{traceback.format_exc()}")
            return None

    # ============================================================
    # DETECCIÓN DE ESTRUCTURA
    # ============================================================

    @classmethod
    def detect_structure(cls, text: str) -> List[Dict[str, Any]]:
        """
        Analiza el texto y detecta la estructura jerárquica del documento.

        Detecta: TÍTULO, CAPÍTULO, SECCIÓN, Artículo, ANEXO, Disposiciones.

        Returns:
            Lista de secciones detectadas con:
            - type: 'titulo' | 'capitulo' | 'seccion' | 'articulo' | 'anexo' | 'disposicion'
            - title: str (nombre completo de la sección)
            - start_char: int (posición de inicio en el texto)
            - end_char: int (posición de fin)
            - level: int (nivel jerárquico)
        """
        if not text:
            return []

        # Encontrar todas las ocurrencias de patrones estructurales
        matches = []
        for tipo, patron in PATRONES_ESTRUCTURA:
            for m in patron.finditer(text):
                # Extraer el título completo (primera línea)
                start = m.start()
                end_of_line = text.find('\n', start)
                if end_of_line == -1:
                    end_of_line = min(start + 200, len(text))
                title_line = text[start:end_of_line].strip()

                # Asignar nivel jerárquico
                niveles = {'titulo': 0, 'capitulo': 1, 'seccion': 2,
                          'articulo': 3, 'disposicion': 2, 'anexo': 0}

                matches.append({
                    'type': tipo,
                    'title': title_line,
                    'start_char': start,
                    'level': niveles.get(tipo, 3),
                })

        if not matches:
            return []

        # Ordenar por posición en el texto
        matches.sort(key=lambda x: x['start_char'])

        # Asignar end_char (hasta el inicio del siguiente match o fin del texto)
        for i, match in enumerate(matches):
            if i + 1 < len(matches):
                match['end_char'] = matches[i + 1]['start_char']
            else:
                match['end_char'] = len(text)

        return matches

    # ============================================================
    # CHUNKING
    # ============================================================

    @classmethod
    def chunk_text(cls, text: str) -> List[Dict[str, Any]]:
        """
        Divide texto en chunks respetando la estructura del documento.

        Estrategia:
        1. Detectar estructura del documento (títulos, capítulos, artículos)
        2. Si es documento estructurado → chunkear POR SECCIÓN
           (cada artículo es un chunk independiente)
        3. Si es texto plano → chunkear por palabras con overlap

        Returns:
            Lista de chunks, cada uno con:
            - content: str (texto del chunk)
            - chunk_index: int
            - word_count: int
            - char_count: int
            - estructura: dict | None (tipo, titulo, nivel si aplica)
        """
        if not text or not text.strip():
            return []

        # Detectar estructura
        estructura = cls.detect_structure(text)
        es_estructurado = len(estructura) > 3  # Al menos 3 secciones = documento estructurado

        if es_estructurado:
            return cls._chunk_estructurado(text, estructura)
        else:
            return cls._chunk_plano(text)

    @classmethod
    def _chunk_estructurado(
        cls, text: str, estructura: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Chunking basado en estructura: cada ARTÍCULO o sección es un chunk.
        Agrupa secciones menores (artículos) bajo su CONTENEDOR (capítulo/título).
        """
        chunks = []
        # Agrupar por contenedores (TÍTULO, CAPÍTULO)
        contenedores = [s for s in estructura if s['type'] in ('titulo', 'capitulo', 'anexo')]
        secciones = [s for s in estructura if s['type'] in ('articulo', 'disposicion', 'seccion')]

        if not secciones:
            # Si solo hay contenedores, usarlos como chunks
            secciones = contenedores if contenedores else estructura

        for i, sec in enumerate(secciones):
            # Extraer texto de esta sección
            start = sec['start_char']
            end = sec.get('end_char', len(text))
            content = text[start:end].strip()

            if not content:
                continue

            # Encontrar el título del contenedor padre
            contenedor_actual = None
            for c in contenedores:
                if c['start_char'] <= start:
                    contenedor_actual = c['title']
                else:
                    break

            palabras = content.split()
            chunks.append({
                'content': content,
                'chunk_index': i,
                'word_count': len(palabras),
                'char_count': len(content),
                'estructura': {
                    'type': sec['type'],
                    'titulo': sec['title'],
                    'nivel': sec['level'],
                    'contenedor': contenedor_actual or '',
                }
            })

        logger.info(
            f"Chunking estructural: {len(chunks)} chunks "
            f"(basado en {len(secciones)} secciones detectadas)"
        )
        return chunks

    @classmethod
    def _chunk_plano(cls, text: str) -> List[Dict[str, Any]]:
        """
        Chunking por palabras con overlap (para texto no estructurado).
        Detecta si tiene "Artículo" para respetar límites de artículos.
        Incluye salvaguardas contra bucles infinitos y MemoryError.
        """
        is_legal_doc = "Artículo" in text

        words = text.split()
        total_words = len(words)
        chunks = []
        MAX_CHUNKS = 10000  # Límite de seguridad

        start = 0
        chunk_index = 0
        iterations = 0

        while start < total_words and iterations < MAX_CHUNKS:
            iterations += 1
            end = min(start + cls.CHUNK_SIZE, total_words)

            # Si ya estamos al final del texto, salir después de procesar
            reached_end = (end >= total_words)

            # Para docs con Artículo, ajustar al límite del Artículo ANTERIOR
            # (buscar hacia atrás para no cortar un artículo)
            if is_legal_doc and end < total_words:
                for i in range(end - 1, max(start, 0), -1):
                    if i < total_words and words[i].startswith('Artículo'):
                        end = i
                        break

            # Asegurar que end > start para evitar chunks vacíos o bucle infinito
            if end <= start:
                if reached_end:
                    break
                end = min(start + 1, total_words)
                if end <= start:
                    break

            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)

            if chunk_text.strip():
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_index,
                    'word_count': len(chunk_words),
                    'char_count': len(chunk_text),
                    'estructura': None,
                })

            chunk_index += 1

            # Salir si ya procesamos el último fragmento
            if reached_end:
                break

            # Avanzar ventana
            if is_legal_doc:
                start = end  # Sin overlap para no mezclar artículos
            else:
                new_start = end - cls.CHUNK_OVERLAP
                # Asegurar que start siempre avance (evitar bucle infinito)
                start = max(new_start, start + 1)

        logger.info(
            f"Chunking plano: {len(chunks)} chunks "
            f"(legal_doc={is_legal_doc}, "
            f"chunk_size={cls.CHUNK_SIZE}, overlap={cls.CHUNK_OVERLAP if not is_legal_doc else 0}, "
            f"iterations={iterations})"
        )
        return chunks

    # ============================================================
    # INGESTA
    # ============================================================

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
        2. Detectar estructura del documento
        3. Chunkificar respetando estructura (artículos, capítulos)
        4. Generar embedding para cada chunk (modo passage)
        5. Crear/actualizar documentos en IntelligenceDocument
        6. Reconstruir índice FAISS si está disponible

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
            'total_chunks': 0,
            'secciones_detectadas': 0,
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

            # Detectar estructura
            estructura = cls.detect_structure(text)
            stats['secciones_detectadas'] = len(estructura)

            # Chunkificar
            try:
                chunks = cls.chunk_text(text)
            except MemoryError:
                logger.error(f"MemoryError al chunkificar texto de {os.path.basename(pdf_path)}. "
                             f"Texto demasiado grande o bucle infinito.")
                return False, "Error de memoria al procesar el texto del PDF. El archivo es demasiado grande o tiene un formato no soportado.", stats
            if not chunks:
                return False, "No se generaron chunks del texto extraído", stats

            stats['total_chunks'] = len(chunks)

            pdf_name = os.path.basename(pdf_path)
            # Hash del archivo completo para identificar duplicados
            with open(pdf_path, 'rb') as f:
                pdf_hash = hashlib.md5(f.read()).hexdigest()

            logger.info(
                f"Ingiriendo PDF: {pdf_name} (hash={pdf_hash[:8]}...) "
                f"-> colección '{collection_name}', "
                f"{len(chunks)} chunks, "
                f"{len(estructura)} secciones detectadas"
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
                        'char_count': chunk['char_count'],
                        'fecha_ingesta': timezone.now().isoformat(),
                    }

                    # Agregar metadatos de estructura si existen
                    est = chunk.get('estructura')
                    if est:
                        field_values['estructura_tipo'] = est['type']
                        field_values['estructura_titulo'] = est['titulo']
                        field_values['estructura_nivel'] = est['nivel']
                        field_values['estructura_contenedor'] = est['contenedor']
                    else:
                        field_values['estructura_tipo'] = 'texto_continuo'

                    if metadata:
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
                    logger.error(
                        f"Error procesando chunk {chunk['chunk_index']}: {e}\n"
                        f"{traceback.format_exc()}"
                    )
                    stats['errors'] += 1

            # Verificar si todos los chunks fallaron
            if stats['chunks_created'] == 0 and stats['chunks_updated'] == 0 and stats['errors'] > 0:
                return False, (
                    f"Error en ingesta: No se pudo generar embeddings para ningún chunk "
                    f"({stats['errors']} errores). Verifica que el modelo de embeddings "
                    f"(intfloat/multilingual-e5-small) esté correctamente instalado."
                ), stats

            # Actualizar estadísticas de la colección
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
                f"{stats['chunks_updated']} actualizados, "
                f"{stats['secciones_detectadas']} secciones detectadas"
            ), stats

        except IntelligenceCollection.DoesNotExist:
            return False, f"Colección '{collection_name}' no encontrada o inactiva", stats
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Error en ingesta de PDF: {e}\n{tb}")
            return False, f"Error en ingesta: {str(e) or 'Error desconocido (ver logs del servidor)'}", stats
