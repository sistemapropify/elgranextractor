# F1-003: PDF Ingestion Pipeline

> **Phase:** 1 — Function Calling
> **Priority:** 🔴 HIGH
> **Estimated Effort:** 3 days
> **Dependencies:** None
> **Status:** Pending

---

## Description

Implementar pipeline de ingesta de documentos PDF (SUNARP, documentos legales, escrituras) al sistema RAG. Actualmente solo existen 85 documentos en la colección `propiedades_propify`. La ingesta de PDFs legales aumentará significativamente la cobertura de datos.

## Goals

- [x] **3.1** Analizar plan de implementación existente en `implementacion_rag_mejoras.md`
- [ ] **3.2** Implementar `services/pdf_ingestion.py` con clase `PDFIngestionService`
- [ ] **3.3** Implementar extracción de texto con PyMuPDF (fitz)
- [ ] **3.4** Implementar chunking: 400 palabras, 50 overlap
- [ ] **3.5** Implementar detección de documentos legales (artículos) con chunking especial
- [ ] **3.6** Implementar endpoint `POST /rag/collections/{name}/ingest-pdf/`
- [ ] **3.7** Implementar post-ingesta: reconstruir índice FAISS automáticamente
- [ ] **3.8** Agregar logging de ingesta (páginas procesadas, chunks creados)
- [ ] **3.9** Probar con documentos SUNARP reales
- [ ] **3.10** Documentar formato de documentos soportados

_Prompt: Build a PDF ingestion pipeline that extracts text from legal documents (SUNARP, escrituras), chunks them appropriately (with special handling for legal articles), generates embeddings with E5-large, stores them in IntelligenceDocument, and rebuilds the FAISS index._

_Requirements: PyMuPDF, E5-large embeddings (mode='passage'), 400-word chunks, 50-word overlap, legal article detection_

_Leverage: existing RAGService.generate_embedding(), FAISSIndexManager.rebuild_for_collection(), IntelligenceDocument model_

_Files: webapp/intelligence/services/pdf_ingestion.py (new), webapp/intelligence/views.py (modify), requirements.txt (add pymupdf)_

## Architecture

```python
class PDFIngestionService:
    CHUNK_SIZE = 400  # palabras
    CHUNK_OVERLAP = 50  # palabras
    LEGAL_CHUNK_OVERLAP = 0  # No overlap para documentos legales
    
    @classmethod
    def ingest_pdf(cls, file_path: str, collection_name: str) -> IngestionResult:
        # 1. Extraer texto con fitz
        text = cls._extract_text(file_path)
        
        # 2. Detectar si es documento legal
        is_legal = cls._detect_legal_document(text)
        
        # 3. Chunkear según tipo
        chunks = cls._chunk_text(text, is_legal)
        
        # 4. Generar embeddings y guardar
        for chunk in chunks:
            embedding = RAGService.generate_embedding(chunk, mode='passage')
            IntelligenceDocument.objects.create(
                collection=collection,
                content=chunk,
                embedding=embedding,
                # ...
            )
        
        # 5. Reconstruir FAISS
        FAISSIndexManager.rebuild_for_collection(collection_name)
        
        return IngestionResult(pages=..., chunks=..., documents=len(chunks))
```

## Acceptance Criteria

- [ ] **3.a** Extracción correcta de texto de PDFs con PyMuPDF
- [ ] **3.b** Chunking de 400 palabras con 50 de overlap (texto general)
- [ ] **3.c** Chunking sin overlap para documentos legales (artículos)
- [ ] **3.d** Embeddings generados con mode='passage' (prefijo correcto)
- [ ] **3.e** FAISS index se reconstruye automáticamente post-ingesta
- [ ] **3.f** Logging de páginas procesadas, chunks creados, documentos
- [ ] **3.g** Endpoint REST funcional con validación de archivo
