"""
Servicio RAG (Retrieval Augmented Generation) para búsqueda semántica
y gestión de colecciones vectoriales.

Implementa el sistema de embeddings y búsqueda por similitud de coseno
para documentos almacenados en IntelligenceDocument.

OPTIMIZACIONES IMPLEMENTADAS (SPEC-013):
1. Singleton robusto para modelo de embeddings
2. Caché LRU para embeddings de consultas frecuentes
3. Pre-carga opcional del modelo
4. Monitoreo de estado del singleton

MEJORAS IMPLEMENTADAS (2026-07):
1. Modelo migrado a intfloat/multilingual-e5-small (384 dimensiones, ~500MB RAM)
   [FIX-OOM] Cambio desde multilingual-e5-large (1024d, ~2.5GB) para evitar OOM
   en Azure App Service (tiers básicos con ~2GB RAM).
2. Prefijos "query:" y "passage:" para el modelo E5
3. FAISS HNSW index para búsqueda O(log n)
4. Pre-filtrado en SQL para búsquedas con filtros
5. Pipeline de ingesta de PDFs con chunking inteligente

OPTIMIZACIONES SPEC-014:
1. threading.Lock() en lugar de booleano para singleton thread-safe
2. Device detection automático (CPU/GPU CUDA)
3. Batch encoding para múltiples textos
4. torch.no_grad() para inferencia más rápida
5. normalize_embeddings=True en encode()
6. Pre-carga del modelo en startup via apps.py
"""
import os
import json
import hashlib
import time
import threading
import traceback
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import logging
from functools import lru_cache

from django.db import connection, connections
from django.utils import timezone
from django.conf import settings

from ..models import IntelligenceCollection, IntelligenceDocument
from .schema_discovery import SchemaDiscoveryService

# Configuración de logging
logger = logging.getLogger(__name__)


class RAGService:
    """
    Servicio centralizado para operaciones RAG:
    - Generación de embeddings (multilingual-e5-small, 384 dimensiones)
    - Gestión de colecciones vectoriales
    - Sincronización de datos con resolución de FK
    - Búsqueda semántica con FAISS HNSW (O(log n))
    - Pre-filtrado en SQL para búsquedas con filtros
    
    OPTIMIZACIONES:
    - Singleton thread-safe para modelo de embeddings (threading.Lock)
    - Caché LRU para embeddings de consultas
    - Pre-carga opcional del modelo
    - Monitoreo de estado
    - FAISS HNSW index para búsqueda vectorial eficiente
    - Device detection automático (CPU/GPU CUDA)
    - Batch encoding para múltiples textos
    """
    
    # Modelo de embeddings (intfloat/multilingual-e5-small)
    # Modelo multilingüe de 384 dimensiones con soporte para español.
    # Requiere prefijos "query:" para búsquedas y "passage:" para documentos.
    # Token máximo: 512.
    # FIX-OOM: Migrado desde multilingual-e5-large (1024d, ~2.5GB RAM) a
    # multilingual-e5-small (384d, ~500MB RAM) para evitar OOM en Azure App Service.
    EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
    EMBEDDING_DIMENSIONS = 384
    
    # Configuración desde variables de entorno
    SIMILARITY_THRESHOLD = float(os.environ.get('RAG_SIMILARITY_THRESHOLD', 0.2))
    MAX_RESULTS = int(os.environ.get('RAG_MAX_RESULTS', 10))
    BATCH_SIZE = int(os.environ.get('RAG_BATCH_SIZE', 100))
    ENABLE_TEXT_FALLBACK = os.environ.get('RAG_ENABLE_TEXT_FALLBACK', 'true').lower() == 'true'
    
    # El fallback de texto SIEMPRE se ejecuta. No se limita ni se salta.
    # La comparación contra top_k=9999 asegura que siempre sea verdadera.
    MIN_RESULTS_FOR_FALLBACK = int(os.environ.get('RAG_MIN_RESULTS_FOR_FALLBACK', 9999))
    
    # Singleton para el modelo de embeddings (SPEC-014: threading.Lock)
    _embedder = None
    _embedder_lock = threading.Lock()  # Lock thread-safe real
    _device = None  # 'cuda' | 'cpu' — detectado automáticamente
    _model_load_time_ms = 0.0  # Tiempo de carga del modelo
    
    # Caché para embeddings de consultas frecuentes
    _embedding_cache = {}
    _max_cache_size = int(os.environ.get('RAG_EMBEDDING_CACHE_SIZE', 100))
    
    @classmethod
    def _get_available_memory_mb(cls) -> Optional[float]:
        """
        Obtiene la memoria RAM disponible en MB (solo Linux).
        Útil para evitar OOM kills en Azure App Service.
        
        Returns:
            MB disponibles, o None si no se puede determinar (Windows, etc.)
        """
        try:
            import psutil
            available = psutil.virtual_memory().available
            return available / (1024 * 1024)
        except ImportError:
            logger.debug("psutil no disponible, no se puede verificar memoria")
            return None
        except Exception:
            return None

    @classmethod
    def initialize_embedder(cls, force: bool = False):
        """
        Inicializa el modelo de embeddings (sentence-transformers).
        Usa lazy loading para evitar cargar el modelo si no se necesita.
        
        SPEC-014: Double-check locking pattern con threading.Lock(),
        device detection automático (cuda si torch.cuda.is_available()).
        
        FIX-OOM: Verifica memoria disponible antes de cargar el modelo
        para evitar OOM kills en Azure App Service.
        
        Args:
            force: Forzar reinicialización incluso si ya está cargado
            
        Returns:
            Modelo de embeddings cargado
        """
        # Double-check locking pattern
        if cls._embedder is None or force:
            with cls._embedder_lock:
                # Segunda verificación dentro del lock
                if cls._embedder is not None and not force:
                    return cls._embedder
                
                # ── FIX-OOM: Verificar memoria disponible ──
                # multilingual-e5-small necesita ~500MB para cargarse.
                # Si hay menos de 700MB disponibles, no intentar cargar.
                available_mb = cls._get_available_memory_mb()
                if available_mb is not None and available_mb < 700:
                    logger.warning(
                        f"Memoria disponible ({available_mb:.0f}MB) insuficiente para cargar "
                        f"modelo de embeddings ({cls.EMBEDDING_MODEL}). "
                        f"Se cargará cuando haya más memoria disponible."
                    )
                    return None
                    
                try:
                    load_start = time.time()
                    from sentence_transformers import SentenceTransformer
                    import torch
                    
                    # Device detection automático
                    if torch.cuda.is_available():
                        cls._device = 'cuda'
                        logger.info(f"GPU CUDA detectada — cargando modelo en GPU")
                    else:
                        cls._device = 'cpu'
                        logger.info(f"Sin GPU detectada — cargando modelo en CPU")
                    
                    logger.info(f"Inicializando modelo de embeddings: {cls.EMBEDDING_MODEL}")
                    cls._embedder = SentenceTransformer(
                        cls.EMBEDDING_MODEL,
                        device=cls._device
                    )
                    cls._embedder.eval()  # Modo evaluación (desactiva dropout etc.)
                    
                    cls._model_load_time_ms = (time.time() - load_start) * 1000
                    logger.info(
                        f"Modelo de embeddings inicializado "
                        f"({cls.EMBEDDING_MODEL}, "
                        f"{cls.EMBEDDING_DIMENSIONS} dimensiones, "
                        f"device={cls._device}, "
                        f"carga={cls._model_load_time_ms:.0f}ms)"
                    )
                    
                    # Limpiar caché si se fuerza reinicialización
                    if force:
                        cls._embedding_cache.clear()
                        logger.info("Caché de embeddings limpiado por reinicialización forzada")
                        
                except ImportError as e:
                    logger.error(f"Error al importar sentence-transformers: {e}")
                    raise ImportError(
                        "La librería sentence-transformers no está instalada. "
                        "Instala con: pip install sentence-transformers"
                    )
                except Exception as e:
                    logger.error(f"Error al inicializar modelo de embeddings: {e}")
                    # Fallback a CPU si GPU falla (ej: OOM)
                    if cls._device == 'cuda':
                        logger.warning("Fallo en GPU, intentando fallback a CPU...")
                        cls._device = 'cpu'
                        try:
                            from sentence_transformers import SentenceTransformer
                            load_start = time.time()
                            cls._embedder = SentenceTransformer(
                                cls.EMBEDDING_MODEL,
                                device='cpu'
                            )
                            cls._embedder.eval()
                            cls._model_load_time_ms = (time.time() - load_start) * 1000
                            logger.info(f"Fallback a CPU exitoso ({cls._model_load_time_ms:.0f}ms)")
                        except Exception as e2:
                            logger.error(f"Fallback a CPU también falló: {e2}")
                            raise
                    else:
                        raise
        
        return cls._embedder
    
    @classmethod
    def get_embedder(cls):
        """Obtiene el embedder inicializado (lazy loading)."""
        return cls.initialize_embedder()
    
    @classmethod
    def preload_embedder(cls):
        """
        Pre-carga el modelo de embeddings al inicio de la aplicación.
        Útil para evitar latencia en la primera consulta.
        
        Returns:
            True si se cargó exitosamente, False si hubo error
        """
        try:
            embedder = cls.initialize_embedder()
            if embedder:
                logger.info("Modelo de embeddings pre-cargado exitosamente")
                return True
        except Exception as e:
            logger.error(f"Error al pre-cargar modelo de embeddings: {e}")
        
        return False
    
    @classmethod
    def get_embedder_status(cls) -> Dict[str, Any]:
        """
        Obtiene estado del singleton de embeddings.
        
        Returns:
            Dict con información de estado
        """
        return {
            'loaded': cls._embedder is not None,
            'model': cls.EMBEDDING_MODEL,
            'dimensions': cls.EMBEDDING_DIMENSIONS,
            'device': cls._device,
            'load_time_ms': round(cls._model_load_time_ms, 0),
            'cache_size': len(cls._embedding_cache),
            'cache_hits': getattr(cls, '_cache_hits', 0),
            'cache_misses': getattr(cls, '_cache_misses', 0),
        }
    
    @classmethod
    def generate_embedding(cls, text: str, use_cache: bool = True, mode: str = 'passage') -> Optional[bytes]:
        """
        Genera embedding vectorial para un texto con caché LRU.
        
        SPEC-014: Optimizado con torch.no_grad() y normalize_embeddings=True
        para inferencia 2-3x más rápida.
        
        El modelo multilingual-e5-small requiere prefijos específicos:
        - "query: {text}" para textos de búsqueda
        - "passage: {text}" para documentos almacenados
        
        Args:
            text: Texto a convertir en embedding
            use_cache: Usar caché para consultas frecuentes
            mode: 'passage' para documentos, 'query' para búsquedas
            
        Returns:
            Bytes del embedding ({cls.EMBEDDING_DIMENSIONS} dimensiones) o None si hay error
        """
        if not text or not text.strip():
            return None
        
        # Aplicar prefijo según modo (requerido por modelo E5)
        if mode == 'query':
            prefixed_text = f"query: {text}"
        else:
            prefixed_text = f"passage: {text}"
        
        # Verificar caché si está habilitado
        if use_cache:
            cache_key = hashlib.md5(prefixed_text.encode('utf-8')).hexdigest()
            if cache_key in cls._embedding_cache:
                # Actualizar estadísticas de caché
                cls._cache_hits = getattr(cls, '_cache_hits', 0) + 1
                logger.debug(f"Embedding obtenido de caché para: '{text[:50]}...'")
                return cls._embedding_cache[cache_key]
            
            # Actualizar estadísticas de caché
            cls._cache_misses = getattr(cls, '_cache_misses', 0) + 1
        
        try:
            embedder = cls.get_embedder()
            
            # SPEC-014: torch.no_grad() + normalize_embeddings=True
            import torch
            with torch.no_grad():
                embedding_np = embedder.encode(
                    prefixed_text,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
            
            # Verificar dimensiones
            if embedding_np.shape[0] != cls.EMBEDDING_DIMENSIONS:
                logger.warning(f"Embedding tiene dimensiones incorrectas: {embedding_np.shape}")
                # Normalizar si es necesario
                if embedding_np.shape[0] > cls.EMBEDDING_DIMENSIONS:
                    embedding_np = embedding_np[:cls.EMBEDDING_DIMENSIONS]
                else:
                    # Padding con ceros
                    padding = np.zeros(cls.EMBEDDING_DIMENSIONS - embedding_np.shape[0])
                    embedding_np = np.concatenate([embedding_np, padding])
            
            # Convertir a bytes para almacenar en BinaryField
            embedding_bytes = embedding_np.tobytes()
            
            # Almacenar en caché si está habilitado
            if use_cache:
                # Gestionar tamaño de caché (LRU simple)
                if len(cls._embedding_cache) >= cls._max_cache_size:
                    # Eliminar el primer elemento (más antiguo)
                    oldest_key = next(iter(cls._embedding_cache))
                    del cls._embedding_cache[oldest_key]
                
                cls._embedding_cache[cache_key] = embedding_bytes
                logger.debug(f"Embedding almacenado en caché para: '{text[:50]}...'")
            
            return embedding_bytes
            
        except Exception as e:
            logger.error(
                f"Error al generar embedding: {e}\n"
                f"{traceback.format_exc()}"
            )
            return None

    @classmethod
    def generate_embeddings_batch(
        cls,
        texts: List[str],
        mode: str = 'passage',
        batch_size: int = 32,
    ) -> List[Optional[np.ndarray]]:
        """
        Genera embeddings para múltiples textos en batch.
        
        SPEC-014: Mucho más eficiente que llamar generate_embedding() N veces,
        porque sentence-transformers puede paralelizar internamente.
        
        Args:
            texts: Lista de textos a convertir en embeddings
            mode: 'passage' para documentos, 'query' para búsquedas
            batch_size: Tamaño del batch para encoding
            
        Returns:
            Lista de np.ndarray (normalizados) o None por cada texto
        """
        if not texts:
            return []
        
        # Prefijar textos según modo
        prefix = "query: " if mode == 'query' else "passage: "
        prefixed_texts = [f"{prefix}{t}" for t in texts]
        
        try:
            embedder = cls.get_embedder()
            import torch
            
            with torch.no_grad():
                embeddings = embedder.encode(
                    prefixed_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    batch_size=batch_size,
                )
            
            # Asegurar que es una lista de arrays
            if embeddings.ndim == 1:
                embeddings = embeddings.reshape(1, -1)
            
            results: List[Optional[np.ndarray]] = []
            for i, emb in enumerate(embeddings):
                if emb.shape[0] == cls.EMBEDDING_DIMENSIONS:
                    results.append(emb)
                else:
                    logger.warning(
                        f"Embedding {i} tiene dimensiones incorrectas: {emb.shape}"
                    )
                    results.append(None)
            
            return results
            
        except Exception as e:
            logger.error(f"Error al generar embeddings batch: {e}")
            return [None] * len(texts)
    
    @classmethod
    def clear_embedding_cache(cls):
        """
        Limpia la caché de embeddings.
        
        Returns:
            Número de elementos eliminados
        """
        count = len(cls._embedding_cache)
        cls._embedding_cache.clear()
        logger.info(f"Caché de embeddings limpiada ({count} elementos eliminados)")
        return count
    
    @classmethod
    def calculate_content_hash(cls, content: str) -> str:
        """
        Calcula hash SHA256 del contenido para detectar cambios.

        Args:
            content: Contenido del documento

        Returns:
            Hash SHA256 en hexadecimal
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    @classmethod
    def _serialize_row_dict(cls, row_dict):
        """
        Serializa un diccionario de fila de base de datos a JSON,
        convirtiendo tipos no serializables como Decimal, Date, etc.
        Especialmente diseñado para ser compatible con SQL Server ISJSON.
        
        Args:
            row_dict: Diccionario con valores de fila
            
        Returns:
            Diccionario serializable a JSON compatible con SQL Server
        """
        import decimal
        import datetime
        import math
        from django.utils.timezone import is_aware
        
        serializable_dict = {}
        for key, value in row_dict.items():
            if value is None:
                serializable_dict[key] = None
            elif isinstance(value, decimal.Decimal):
                # Convertir Decimal a float, manejando valores especiales
                float_val = float(value)
                # SQL Server no acepta NaN o Infinity en JSON
                if math.isnan(float_val) or math.isinf(float_val):
                    serializable_dict[key] = None
                else:
                    serializable_dict[key] = float_val
            elif isinstance(value, (datetime.date, datetime.datetime)):
                # Convertir fechas a string formato compatible con SQL Server
                # Usar formato YYYY-MM-DD HH:MM:SS para mejor compatibilidad
                if isinstance(value, datetime.datetime):
                    if is_aware(value):
                        value = value.astimezone(datetime.timezone.utc)
                    # Formato: YYYY-MM-DD HH:MM:SS
                    serializable_dict[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:  # datetime.date
                    serializable_dict[key] = value.strftime('%Y-%m-%d')
            elif isinstance(value, str):
                # Limpiar strings de caracteres de control (excepto tab, newline, carriage return)
                # SQL Server ISJSON puede rechazar ciertos caracteres de control
                cleaned = ''.join(
                    char for char in value
                    if ord(char) >= 32 or char in '\t\n\r'
                )
                serializable_dict[key] = cleaned
            elif isinstance(value, (int, bool)):
                # Tipos básicos JSON
                serializable_dict[key] = value
            elif isinstance(value, float):
                # Manejar float especiales para SQL Server
                if math.isnan(value) or math.isinf(value):
                    serializable_dict[key] = None
                else:
                    serializable_dict[key] = value
            else:
                # Para cualquier otro tipo, convertirlo a string
                try:
                    serializable_dict[key] = str(value)
                except:
                    serializable_dict[key] = None
        
        return serializable_dict
    
    @classmethod
    def create_collection(
        cls,
        name: str,
        source_sql: str,
        embedding_fields: List[str],
        min_level: int = 1,
        domain: str = 'general',
        is_public: bool = False,
        description: str = "",
        is_active: bool = True
    ) -> Tuple[bool, str, Optional[IntelligenceCollection]]:
        """
        Crea una nueva colección vectorial.
        
        Args:
            name: Nombre único de la colección
            source_sql: Consulta SQL que devuelve los datos fuente
            embedding_fields: Lista de campos a concatenar para embedding
            min_level: Nivel mínimo requerido (1-5)
            domain: Dominio de la colección
            is_public: Si es accesible públicamente
            description: Descripción opcional
            is_active: Si la colección está activa
            
        Returns:
            Tuple (success, message, collection)
        """
        try:
            # Validar nombre único
            if IntelligenceCollection.objects.filter(name=name).exists():
                return False, f"Ya existe una colección con el nombre '{name}'", None
            
            # Validar SQL básico (no ejecutar, solo verificar sintaxis básica)
            if not source_sql.strip().lower().startswith('select'):
                return False, "La consulta SQL debe comenzar con SELECT", None
            
            # Validar campos de embedding
            if not embedding_fields:
                return False, "Debe especificar al menos un campo para embedding", None
            
            # Crear colección
            collection = IntelligenceCollection.objects.create(
                name=name,
                source_sql=source_sql,
                embedding_fields=embedding_fields,
                min_level=min_level,
                domain=domain,
                is_public=is_public,
                description=description,
                is_active=is_active
            )
            
            logger.info(f"Colección creada: {name} (ID: {collection.id})")
            return True, f"Colección '{name}' creada exitosamente", collection
            
        except Exception as e:
            logger.error(f"Error al crear colección '{name}': {e}")
            return False, f"Error al crear colección: {str(e)}", None
    
    @classmethod
    def _get_connection_for_collection(cls, collection):
        """
        Determina qué conexión de base de datos usar para una colección.
        
        Args:
            collection: IntelligenceCollection object
            
        Returns:
            Django database connection object
        """
        # Prioridad 1: Usar database_alias del modelo si está configurado
        db_alias = getattr(collection, 'database_alias', None)
        if db_alias and db_alias != 'default' and db_alias in connections:
            logger.debug(f"Usando conexión '{db_alias}' desde collection.database_alias para: {collection.name}")
            return connections[db_alias]
        
        # Prioridad 2: Por defecto usar conexión 'default'
        conn = connections['default']
        
        # Prioridad 3: Detección automática por nombre/SQL (legacy)
        collection_name_lower = collection.name.lower()
        source_sql_lower = (collection.source_sql or '').lower()
        
        if ('propifai' in collection_name_lower or
            'properties' in source_sql_lower or
            'from propifai.' in source_sql_lower or
            'from [propifai].' in source_sql_lower or
            'dbpropifai' in source_sql_lower):
            
            # Verificar si existe conexión 'propifai'
            if 'propifai' in connections:
                conn = connections['propifai']
                logger.debug(f"Usando conexión 'propifai' (detección automática) para colección: {collection.name}")
            else:
                logger.warning(f"Conexión 'propifai' no encontrada, usando 'default' para colección: {collection.name}")
        
        return conn
    
    @classmethod
    def sync_collection(
        cls,
        collection_id: int,
        force_full_sync: bool = False
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Sincroniza una colección ejecutando la consulta SQL fuente,
        generando embeddings para documentos nuevos/modificados.

        Args:
            collection_id: ID de la colección a sincronizar
            force_full_sync: Si True, regenera embeddings para todos los documentos

        Returns:
            Tuple (success, message, stats)
        """
        stats = {
            'total_processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        try:
            # Obtener colección
            collection = IntelligenceCollection.objects.get(id=collection_id, is_active=True)
            
            logger.info(f"Iniciando sincronización de colección: {collection.name}")
            
            # Obtener conexión apropiada
            conn = cls._get_connection_for_collection(collection)
            
            # Ejecutar consulta SQL
            with conn.cursor() as cursor:
                cursor.execute(collection.source_sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
            
            logger.info(f"Consulta SQL devolvió {len(rows)} registros")
            
            # Procesar cada registro
            for i, row in enumerate(rows):
                try:
                    # Convertir a diccionario
                    row_dict = dict(zip(columns, row))
                    
                    # Extraer source_id (debe estar en los resultados)
                    source_id = str(row_dict.get('id') or row_dict.get('source_id') or i)
                    
                    # Construir contenido concatenando campos de embedding
                    content_parts = []
                    embedding_fields = collection.embedding_fields  # Ya es una lista, no necesita json.loads
                    
                    for field in embedding_fields:
                        if field in row_dict and row_dict[field]:
                            content_parts.append(str(row_dict[field]))
                    
                    content = " ".join(content_parts)
                    
                    if not content.strip():
                        logger.warning(f"Registro {source_id} sin contenido para embedding, saltando")
                        stats['skipped'] += 1
                        continue
                    
                    # Calcular hash del contenido
                    content_hash = cls.calculate_content_hash(content)
                    
                    # Buscar documento existente
                    try:
                        document = IntelligenceDocument.objects.get(
                            collection=collection,
                            source_id=source_id
                        )
                        
                        # Verificar si el contenido cambió
                        if document.content_hash == content_hash and not force_full_sync:
                            stats['skipped'] += 1
                            continue
                        
                        # Actualizar documento existente
                        document.content = content
                        document.content_hash = content_hash
                        document.metadata_json = json.dumps(cls._serialize_row_dict(row_dict))
                        
                        # Regenerar embedding si el contenido cambió o force_full_sync
                        if document.content_hash != content_hash or force_full_sync:
                            embedding = cls.generate_embedding(content)
                            if embedding:
                                document.embedding = embedding
                        
                        document.save()
                        stats['updated'] += 1
                        logger.debug(f"Documento actualizado: {source_id}")
                        
                    except IntelligenceDocument.DoesNotExist:
                        # Crear nuevo documento
                        embedding = cls.generate_embedding(content)
                        
                        document = IntelligenceDocument.objects.create(
                            collection=collection,
                            source_id=source_id,
                            content=content,
                            content_hash=content_hash,
                            embedding=embedding,
                            metadata_json=json.dumps(cls._serialize_row_dict(row_dict))
                        )
                        stats['created'] += 1
                        logger.debug(f"Documento creado: {source_id}")
                    
                    stats['total_processed'] += 1
                    
                    # Log cada 100 registros
                    if stats['total_processed'] % 100 == 0:
                        logger.info(f"Procesados {stats['total_processed']} registros...")
                    
                except Exception as e:
                    logger.error(f"Error procesando registro {i}: {e}")
                    stats['errors'] += 1
            
            # Actualizar estadísticas de la colección
            collection.last_sync_at = timezone.now()
            collection.last_sync_count = stats['total_processed']
            collection.save()
            
            logger.info(
                f"Sincronización completada para '{collection.name}': "
                f"{stats['created']} creados, {stats['updated']} actualizados, "
                f"{stats['skipped']} saltados, {stats['errors']} errores"
            )
            
            return True, "Sincronización completada exitosamente", stats
            
        except IntelligenceCollection.DoesNotExist:
            return False, f"Colección con ID {collection_id} no encontrada o inactiva", stats
        except Exception as e:
            logger.error(f"Error en sync_collection: {e}")
            return False, f"Error en sincronización: {str(e)}", stats
    
    @classmethod
    def search(
        cls,
        query: str,
        collection_ids: Optional[List[int]] = None,
        access_level: int = 1,
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        profile=None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Realiza búsqueda semántica por similitud de coseno.
        
        Args:
            query: Texto de búsqueda
            collection_ids: IDs de colecciones a buscar (None = todas activas)
            access_level: Nivel de acceso del usuario (deprecated, usar profile)
            limit: Límite de resultados (None = usar valor por defecto)
            similarity_threshold: Umbral de similitud (None = usar valor por defecto)
            profile: UserIntelligenceProfile para filtrar por permisos (reemplaza access_level)
            
        Returns:
            Tuple (success, message, results)
        """
        if not query or not query.strip():
            return False, "Query vacía", []
        
        try:
            # Generar embedding para la query (modo query para multilingual-e5-small)
            query_embedding = cls.generate_embedding(query, mode='query')
            if not query_embedding:
                return False, "No se pudo generar embedding para la query", []
            
            # Convertir embedding a numpy array
            query_vector = np.frombuffer(query_embedding, dtype=np.float32)
            
            # Obtener colecciones filtradas
            collections_query = IntelligenceCollection.objects.filter(
                is_active=True,
            )
            
            if collection_ids:
                collections_query = collections_query.filter(id__in=collection_ids)
            
            collections = list(collections_query)
            
            # Filtrar por perfil de inteligencia si se proporciona
            if profile is not None:
                filtered = []
                extra_ids = set(profile.extra_collections.values_list('id', flat=True)) if hasattr(profile, 'extra_collections') else set()
                blocked_ids_set = set(profile.blocked_collections.values_list('id', flat=True)) if hasattr(profile, 'blocked_collections') else set()
                for coll in collections:
                    if coll.id in blocked_ids_set:
                        continue
                    if profile.level < coll.min_level:
                        continue
                    if coll.is_public or coll.id in extra_ids or coll.domain in profile.allowed_domains:
                        filtered.append(coll)
                collections = filtered
            else:
                # Fallback legacy: filtrar por access_level usando min_level
                collections = [c for c in collections if c.min_level <= access_level]
            
            if not collections:
                return False, "No hay colecciones disponibles para búsqueda", []
            
            # Obtener todos los documentos de las colecciones
            documents = IntelligenceDocument.objects.filter(
                collection__in=collections,
                embedding__isnull=False
            ).select_related('collection')
            
            if not documents.exists():
                return False, "No hay documentos con embeddings en las colecciones seleccionadas", []
            
            # Calcular similitud para cada documento
            results = []
            threshold = similarity_threshold or cls.SIMILARITY_THRESHOLD
            max_results = limit or cls.MAX_RESULTS
            
            for doc in documents:
                try:
                    # Convertir embedding del documento a numpy
                    doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                    
                    # ── FIX-OOM: Validar dimensionalidad del embedding ──
                    # Los embeddings antiguos (1024d del modelo e5-large) tienen
                    # dimensión diferente a la actual (384d del e5-small).
                    # Saltar documentos con dimensionalidad incorrecta.
                    if doc_vector.shape[0] != cls.EMBEDDING_DIMENSIONS:
                        logger.debug(
                            f"Documento {doc.id}: dimensión de embedding {doc_vector.shape[0]} "
                            f"difiere de la esperada {cls.EMBEDDING_DIMENSIONS}. Saltando."
                        )
                        continue
                    
                    # Calcular similitud de coseno
                    similarity = np.dot(query_vector, doc_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                    )
                    
                    # Filtrar por umbral
                    if similarity >= threshold:
                        results.append({
                            'document_id': doc.id,
                            'collection_id': doc.collection.id,
                            'collection_name': doc.collection.name,
                            'source_id': doc.source_id,
                            'content': doc.content,
                            'similarity': float(similarity),
                            'metadata': json.loads(doc.metadata_json) if doc.metadata_json else {},
                            'created_at': doc.created_at.isoformat() if doc.created_at else None
                        })
                        
                except Exception as e:
                    logger.warning(f"Error calculando similitud para documento {doc.id}: {e}")
                    continue
            
            # Ordenar por similitud descendente
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limitar resultados
            results = results[:max_results]
            
            logger.info(f"Búsqueda completada: {len(results)} resultados para query: '{query[:50]}...'")
            
            return True, f"Encontrados {len(results)} resultados", results
            
        except Exception as e:
            logger.error(f"Error en búsqueda RAG: {e}")
            return False, f"Error en búsqueda: {str(e)}", []
    
    @classmethod
    def delete_collection(cls, collection_id: int) -> Tuple[bool, str]:
        """
        Elimina una colección y todos sus documentos.
        
        Args:
            collection_id: ID de la colección a eliminar
            
        Returns:
            Tuple (success, message)
        """
        try:
            collection = IntelligenceCollection.objects.get(id=collection_id)
            collection_name = collection.name
            
            # Eliminar documentos primero
            documents_count = IntelligenceDocument.objects.filter(collection=collection).count()
            IntelligenceDocument.objects.filter(collection=collection).delete()
            
            # Eliminar colección
            collection.delete()
            
            logger.info(f"Colección eliminada: {collection_name} ({documents_count} documentos)")
            return True, f"Colección '{collection_name}' eliminada ({documents_count} documentos)"
            
        except IntelligenceCollection.DoesNotExist:
            return False, f"Colección con ID {collection_id} no encontrada"
        except Exception as e:
            logger.error(f"Error al eliminar colección {collection_id}: {e}")
            return False, f"Error al eliminar colección: {str(e)}"
    
    @classmethod
    def get_collection_stats(cls, collection_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene estadísticas de una colección.
        
        Args:
            collection_id: ID de la colección
            
        Returns:
            Diccionario con estadísticas o None si no existe
        """
        try:
            collection = IntelligenceCollection.objects.get(id=collection_id)
            
            # Contar documentos
            total_docs = IntelligenceDocument.objects.filter(collection=collection).count()
            docs_with_embedding = IntelligenceDocument.objects.filter(
                collection=collection,
                embedding__isnull=False
            ).count()
            
            return {
                'id': collection.id,
                'name': collection.name,
                'description': collection.description,
                'min_level': collection.min_level,
                'domain': collection.domain,
                'is_public': collection.is_public,
                'is_active': collection.is_active,
                'last_sync_at': collection.last_sync_at,
                'last_sync_count': collection.last_sync_count,
                'total_documents': total_docs,
                'documents_with_embedding': docs_with_embedding,
                'embedding_coverage': (docs_with_embedding / total_docs * 100) if total_docs > 0 else 0,
                'created_at': collection.created_at,
                'updated_at': collection.updated_at
            }
            
        except IntelligenceCollection.DoesNotExist:
            return None
    
    @classmethod
    def initialize_default_collections(cls) -> Dict[str, Any]:
        """
        Inicializa las colecciones por defecto según SPEC-003.
        
        Returns:
            Diccionario con resultados de inicialización
        """
        results = {
            'total_created': 0,
            'total_skipped': 0,
            'collections': []
        }
        
        # Definir colecciones por defecto según SPEC-003
        default_collections = [
            {
                'name': 'propiedades_propifai',
                'description': 'Propiedades del portfolio propio de la inmobiliaria',
                'source_sql': """
                    SELECT
                        p.id,
                        p.titulo,
                        p.descripcion,
                        p.direccion,
                        p.distrito,
                        p.tipo_propiedad,
                        p.precio,
                        p.moneda,
                        p.area_construida,
                        p.area_total,
                        p.habitaciones,
                        p.banos,
                        p.estacionamientos,
                        p.condicion,
                        p.fecha_creacion,
                        p.es_propify,
                        CONCAT_WS(' ', p.titulo, p.descripcion, p.direccion, p.distrito,
                                  p.tipo_propiedad, p.condicion) as contenido_embedding
                    FROM propifai_propiedad p
                    WHERE p.activo = 1 AND p.es_propify = 1
                """,
                'embedding_fields': ['titulo', 'descripcion', 'direccion', 'distrito',
                                     'tipo_propiedad', 'condicion'],
                'min_level': 1,  # Nivel más bajo - acceso público
                'domain': 'publico',
                'is_public': True
            },
            {
                'name': 'propiedades_competencia',
                'description': 'Propiedades scrapeadas de portales externos (competencia)',
                'source_sql': """
                    SELECT
                        pr.id,
                        pr.titulo,
                        pr.descripcion,
                        pr.direccion,
                        pr.distrito,
                        pr.tipo_propiedad,
                        pr.precio,
                        pr.moneda,
                        pr.area_construida,
                        pr.area_total,
                        pr.habitaciones,
                        pr.banos,
                        pr.estacionamientos,
                        pr.condicion,
                        pr.fecha_scraping,
                        pr.fuente,
                        CONCAT_WS(' ', pr.titulo, pr.descripcion, pr.direccion, pr.distrito,
                                  pr.tipo_propiedad, pr.condicion, pr.fuente) as contenido_embedding
                    FROM ingestas_propiedadraw pr
                    WHERE pr.activo = 1
                """,
                'embedding_fields': ['titulo', 'descripcion', 'direccion', 'distrito',
                                     'tipo_propiedad', 'condicion', 'fuente'],
                'min_level': 2,  # Nivel intermedio - acceso interno
                'domain': 'general',
                'is_public': False
            },
            {
                'name': 'noticias_mercado',
                'description': 'Noticias y análisis del mercado inmobiliario de Arequipa',
                'source_sql': """
                    SELECT
                        id,
                        titulo,
                        contenido,
                        fuente,
                        fecha_publicacion,
                        categoria,
                        palabras_clave,
                        CONCAT_WS(' ', titulo, contenido, categoria, palabras_clave) as contenido_embedding
                    FROM market_news
                    WHERE activo = 1
                    -- Nota: Esta tabla aún no existe, es para futura implementación
                    LIMIT 0  -- Temporalmente vacío hasta que se implemente la tabla
                """,
                'embedding_fields': ['titulo', 'contenido', 'categoria', 'palabras_clave'],
                'min_level': 3,  # Nivel más alto - acceso estratégico
                'domain': 'gerencia',
                'is_public': False
            }
        ]
        
        logger.info("Inicializando colecciones por defecto según SPEC-003")
        
        for collection_def in default_collections:
            try:
                # Verificar si ya existe
                if IntelligenceCollection.objects.filter(name=collection_def['name']).exists():
                    logger.info(f"Colección '{collection_def['name']}' ya existe, saltando")
                    results['collections'].append({
                        'name': collection_def['name'],
                        'status': 'skipped',
                        'message': 'Ya existe'
                    })
                    results['total_skipped'] += 1
                    continue
                
                # Crear colección
                success, message, collection = cls.create_collection(
                    name=collection_def['name'],
                    source_sql=collection_def['source_sql'],
                    embedding_fields=collection_def['embedding_fields'],
                    min_level=collection_def['min_level'],
                    domain=collection_def.get('domain', 'general'),
                    is_public=collection_def.get('is_public', False),
                    description=collection_def['description'],
                    is_active=True
                )
                
                if success and collection:
                    results['collections'].append({
                        'name': collection_def['name'],
                        'status': 'created',
                        'message': message,
                        'collection_id': collection.id
                    })
                    results['total_created'] += 1
                    logger.info(f"Colección creada: {collection_def['name']} (ID: {collection.id})")
                else:
                    results['collections'].append({
                        'name': collection_def['name'],
                        'status': 'error',
                        'message': message
                    })
                    logger.error(f"Error creando colección {collection_def['name']}: {message}")
                    
            except Exception as e:
                logger.error(f"Error procesando colección {collection_def['name']}: {e}")
                results['collections'].append({
                    'name': collection_def['name'],
                    'status': 'error',
                    'message': str(e)
                })
        
        logger.info(
            f"Inicialización completada: {results['total_created']} creadas, "
            f"{results['total_skipped']} saltadas"
        )
        
        return results
    
    # ============================================================================
    # MÉTODOS NUEVOS PARA SPEC-003: SISTEMA RAG CON CAMPOS DINÁMICOS
    # ============================================================================
    
    @classmethod
    def get_available_tables(cls, schema: str = None, database_alias: str = 'default', force_refresh: bool = False) -> List[str]:
        """
        Retorna tablas disponibles en Azure SQL.
        
        Args:
            schema: Esquema a consultar (default: 'dbo')
            database_alias: Alias de la conexión de base de datos (default: 'default', 'propifai' para dbpropify_be)
            force_refresh: Si True, ignora la caché y vuelve a consultar la base de datos
            
        Returns:
            Lista de nombres de tablas
        """
        try:
            import sys
            print(f"[DEBUG] RAGService.get_available_tables: schema={schema}, database_alias={database_alias}, force_refresh={force_refresh}", file=sys.stderr)
            logger.info(f"RAGService.get_available_tables: schema={schema}, database_alias={database_alias}, force_refresh={force_refresh}")
            return SchemaDiscoveryService.list_tables(schema=schema, database_alias=database_alias, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error obteniendo tablas disponibles: {e}")
            return []
    
    @classmethod
    def analyze_table_schema(cls, table_name: str, schema: str = None, database_alias: str = 'default') -> Dict[str, Any]:
        """
        Retorna estructura completa de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema de la tabla
            database_alias: Alias de la conexión de base de datos (default: 'default', 'propifai' para dbpropify_be)
            
        Returns:
            Diccionario con análisis completo de la tabla
        """
        try:
            return SchemaDiscoveryService.analyze_table_schema(table_name, schema=schema, database_alias=database_alias)
        except Exception as e:
            logger.error(f"Error analizando esquema de tabla '{table_name}': {e}")
            return {
                'table_name': table_name,
                'schema': schema or 'dbo',
                'database': database_alias,
                'exists': False,
                'error': str(e)
            }
    
    @classmethod
    def detect_foreign_keys(cls, table_name: str, schema: str = None, database_alias: str = 'default') -> List[Dict[str, Any]]:
        """
        Detecta foreign keys de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema de la tabla
            database_alias: Alias de la conexión de base de datos
            
        Returns:
            Lista de FK detectadas con columnas de tablas referenciadas
        """
        try:
            return SchemaDiscoveryService.detect_foreign_keys(table_name, schema=schema, database_alias=database_alias)
        except Exception as e:
            logger.error(f"Error detectando foreign keys en '{table_name}': {e}")
            return []
    
    @classmethod
    def create_collection_dynamic(
        cls,
        name: str,
        table_name: str,
        embedding_fields: List[str],
        display_fields: List[str],
        filter_fields: List[str] = None,
        min_level: int = 2,
        domain: str = 'general',
        is_public: bool = False,
        description: str = "",
        schema: str = None,
        database_alias: str = 'default',
        field_definitions: List[Dict[str, Any]] = None,
        table_relationships: List[Dict[str, Any]] = None,
        is_active: bool = True,
        key_field: str = 'id',
    ) -> Tuple[bool, str, Optional[IntelligenceCollection]]:
        """
        Crea colección con campos dinámicos según SPEC-003.
        
        Args:
            name: Nombre único de la colección
            table_name: Nombre exacto de la tabla en Azure SQL
            embedding_fields: Lista de campos (nombres reales) usados para embedding
            display_fields: Lista de campos (nombres reales) a mostrar en resultados
            filter_fields: Lista de campos (nombres reales) que se pueden filtrar
            min_level: Nivel mínimo requerido (1-5)
            domain: Dominio de la colección
            is_public: Si es accesible públicamente
            description: Descripción opcional
            schema: Esquema de la tabla
            database_alias: Alias de la conexión de base de datos (default: 'default', 'propifai' para dbpropify_be)
            field_definitions: Definiciones de campos (si se proporciona, se usa en lugar de analizar la tabla)
            table_relationships: Lista de relaciones FK para resolver durante sync
            is_active: Si la colección está activa
            key_field: Campo clave primaria
            
        Returns:
            Tuple (success, message, collection)
        """
        try:
            import sys
            print(f"[DEBUG RAGService] create_collection_dynamic: table={table_name}, schema={schema}, database_alias={database_alias}", file=sys.stderr)
            
            # Validar nombre único
            if IntelligenceCollection.objects.filter(name=name).exists():
                return False, f"Ya existe una colección con el nombre '{name}'", None
            
            # Validar que la tabla existe
            if not SchemaDiscoveryService.validate_table(table_name, schema=schema, database_alias=database_alias):
                return False, f"Tabla '{table_name}' no encontrada en esquema '{schema or 'dbo'}' (base de datos: {database_alias})", None
            
            # Si no se proporcionaron field_definitions, obtener de la tabla
            if not field_definitions:
                schema_analysis = SchemaDiscoveryService.analyze_table_schema(table_name, schema=schema, database_alias=database_alias)
                if not schema_analysis.get('exists', False):
                    return False, f"No se pudo analizar la tabla '{table_name}': {schema_analysis.get('error', 'Error desconocido')}", None
                field_definitions = schema_analysis.get('field_definitions', {})
                primary_key = schema_analysis.get('primary_key', 'id')
            else:
                primary_key = key_field or 'id'
            
            # Validar que los campos especificados existen en la tabla
            if not field_definitions:
                all_columns = []
            elif isinstance(field_definitions, dict):
                all_columns = list(field_definitions.keys())
            else:
                all_columns = [f.get('name', '') for f in field_definitions]
            
            for field_list, field_type in [
                (embedding_fields, 'embedding'),
                (display_fields, 'display'),
                ((filter_fields or []), 'filter')
            ]:
                for field in field_list:
                    if all_columns and field not in all_columns:
                        return False, f"Campo '{field}' no existe en la tabla '{table_name}' para {field_type}", None
            
            # Crear SQL automático si no se proporciona
            source_sql = f"SELECT * FROM [{schema or 'dbo'}].[{table_name}]"
            
            # Normalizar table_relationships
            if table_relationships is None:
                table_relationships = []
            
            # Crear colección
            collection = IntelligenceCollection.objects.create(
                name=name,
                table_name=table_name,
                description=description,
                source_sql=source_sql,
                field_definitions=field_definitions,
                embedding_fields=embedding_fields,
                display_fields=display_fields,
                filter_fields=filter_fields or [],
                min_level=min_level,
                domain=domain,
                is_public=is_public,
                is_active=is_active,
                table_relationships=table_relationships,
                database_alias=database_alias,
            )
            
            logger.info(f"Colección dinámica creada: {name} (Tabla: {table_name}, ID: {collection.id}, Relaciones: {len(table_relationships)})")
            return True, f"Colección '{name}' creada exitosamente con {len(field_definitions)} campos y {len(table_relationships)} relaciones", collection
            
        except Exception as e:
            logger.error(f"Error al crear colección dinámica '{name}': {e}")
            return False, f"Error al crear colección: {str(e)}", None
    
    @classmethod
    def sync_collection_dynamic(
        cls,
        collection_name: str,
        force_full_sync: bool = False,
        database_alias: str = None
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Sincroniza una colección usando los nombres de campos REALES de la tabla.
        
        Args:
            collection_name: Nombre de la colección a sincronizar
            force_full_sync: Si True, regenera embeddings para todos los documentos
            database_alias: Alias de la base de datos (opcional, se detecta automáticamente)
            
        Returns:
            Tuple (success, message, stats)
        """
        stats = {
            'total_processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        try:
            # Obtener colección
            collection = IntelligenceCollection.objects.get(name=collection_name, is_active=True)
            
            if not collection.table_name:
                return False, "Esta colección no tiene table_name configurado (no es dinámica)", stats
            
            logger.info(f"Iniciando sincronización dinámica de colección: {collection.name} (Tabla: {collection.table_name})")
            
            # Obtener conexión apropiada
            # Prioridad: 1) parámetro explícito, 2) collection.database_alias, 3) detección automática
            if database_alias:
                try:
                    conn = connections[database_alias]
                    logger.info(f"Usando conexión del parámetro: {database_alias}")
                except Exception as e:
                    logger.warning(f"No se pudo usar conexión '{database_alias}': {e}, usando collection.database_alias")
                    conn = cls._get_connection_for_collection(collection)
            else:
                conn = cls._get_connection_for_collection(collection)
            
            # Usar source_sql personalizado si existe, de lo contrario construir consulta automática
            if collection.source_sql and collection.source_sql.strip():
                sql = collection.source_sql
                table_name = collection.table_name
                logger.info(f"Usando source_sql personalizado para colección: {collection.name}")
            else:
                schema = 'dbo'  # Por defecto, podría extraerse de field_definitions en el futuro
                table_name = collection.table_name
                sql = f"SELECT * FROM [{schema}].[{table_name}]"
            
            # Ejecutar consulta SQL
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
            
            logger.info(f"Consulta SQL devolvió {len(rows)} registros de '{table_name}'")
            
            # Obtener field_definitions de la colección
            raw_field_defs = collection.field_definitions or {}
            
            # Normalizar: si es lista, convertir a dict indexado por 'name'
            if isinstance(raw_field_defs, list):
                field_definitions = {}
                for item in raw_field_defs:
                    if isinstance(item, dict) and 'name' in item:
                        field_definitions[item['name']] = item
            else:
                field_definitions = raw_field_defs
            
            # Determinar campo ID
            primary_key = None
            for field_name, field_def in field_definitions.items():
                if isinstance(field_def, dict) and field_def.get('is_primary', False):
                    primary_key = field_name
                    break
            
            if not primary_key:
                # Buscar campo llamado 'id' (case insensitive)
                for col in columns:
                    if col.lower() == 'id':
                        primary_key = col
                        break
            
            if not primary_key and columns:
                primary_key = columns[0]  # Usar primera columna como fallback
            
            # Obtener relaciones entre tablas configuradas
            table_relationships = collection.table_relationships or []
            logger.info(f"Relaciones entre tablas configuradas: {len(table_relationships)}")
            
            # Procesar cada registro
            for i, row in enumerate(rows):
                try:
                    # Convertir a diccionario
                    row_dict = dict(zip(columns, row))
                    
                    # Extraer source_id usando el campo primary_key
                    source_id = str(row_dict.get(primary_key) if primary_key in row_dict else i)
                    
                    # Construir field_values con TODOS los campos reales
                    # Usar _serialize_row_dict para manejar Decimal y otros tipos no serializables
                    field_values = cls._serialize_row_dict(row_dict)
                    
                    # --- RESOLVER RELACIONES FK ---
                    # Para cada relación configurada, consultar la tabla referenciada
                    # y agregar texto enriquecido al contenido del embedding.
                    # También actualiza field_values con los valores resueltos
                    # para que el LLM vea nombres reales (ej: "Cayma") en lugar de IDs numéricos.
                    for rel in table_relationships:
                        try:
                            fk_column = rel.get('column', '')
                            ref_table = rel.get('referenced_table', '')
                            ref_column = rel.get('referenced_column', 'id')
                            ref_schema = rel.get('referenced_schema', 'dbo')
                            display_fields = rel.get('display_fields', [])
                            label = rel.get('label', fk_column)
                            
                            # Obtener el valor FK de la fila actual
                            fk_value = row_dict.get(fk_column)
                            
                            # Solo resolver si el FK tiene un valor válido
                            if fk_value is not None and fk_value != '' and ref_table:
                                try:
                                    resolved_text = cls._resolve_foreign_key(
                                        fk_value=fk_value,
                                        referenced_table=ref_table,
                                        referenced_column=ref_column,
                                        referenced_schema=ref_schema,
                                        display_fields=display_fields,
                                        label=label,
                                        database_alias=database_alias or 'propifai',
                                        conn=conn
                                    )
                                    if resolved_text:
                                        # --- ACTUALIZAR field_values CON VALORES RESUELTOS ---
                                        # Guardar SOLO el primer display_field como valor resuelto
                                        # (ej: district_name="Sachaca"), sin duplicar todos los display_fields
                                        if display_fields:
                                            resolved_key = fk_column
                                            for suffix in ['_fk_id', '_fk', '_id']:
                                                if resolved_key.endswith(suffix):
                                                    resolved_key = resolved_key[:-len(suffix)]
                                            resolved_key = f"{resolved_key}_name"
                                            
                                            try:
                                                if conn is None:
                                                    conn = connections[database_alias or 'propifai']
                                                display_cols = ', '.join([f'[{c}]' for c in display_fields])
                                                sql = f"SELECT {display_cols} FROM [{ref_schema}].[{ref_table}] WHERE [{ref_column}] = %s"
                                                with conn.cursor() as cursor:
                                                    cursor.execute(sql, (fk_value,))
                                                    row = cursor.fetchone()
                                                    if row:
                                                        # Guardar SOLO el primer campo como valor resuelto (sin duplicados)
                                                        first_val = row[0]
                                                        if first_val is not None:
                                                            if hasattr(first_val, 'isoformat'):
                                                                first_val = first_val.isoformat()
                                                            elif isinstance(first_val, bytes):
                                                                first_val = first_val.decode('utf-8', errors='replace')
                                                            field_values[resolved_key] = str(first_val)
                                            except Exception as fk_err:
                                                logger.debug(f"No se pudo obtener valor resuelto para {fk_column}={fk_value}: {fk_err}")
                                except Exception as rel_err:
                                    logger.warning(f"Error resolviendo FK {fk_column}={fk_value} -> {ref_table}: {rel_err}")
                        except Exception as rel_err:
                            logger.warning(f"Error procesando relación: {rel_err}")
                    
                    # Construir texto para embedding usando los campos en embedding_fields
                    # PRIMERO intenta con field_values actualizados (que tienen nombres resueltos),
                    # LUEGO con row_dict original como fallback
                    content_parts = []
                    for field in collection.embedding_fields:
                        # Buscar primero en field_values (valores resueltos post-FK)
                        val = field_values.get(field) or row_dict.get(field)
                        if val is not None and val != '':
                            content_parts.append(str(val))
                    
                    # ── Refactor D3: Inyectar etiquetas semánticas de la colección ──
                    # Las semantic_tags se agregan al contenido del embedding para
                    # mejorar la búsqueda conceptual. Por ejemplo, una colección con
                    # tags ['terreno', 'construccion', 'educacion'] hará que propiedades
                    # sean encontradas por consultas como "donde construir un colegio".
                    semantic_tags = collection.semantic_tags or []
                    if semantic_tags:
                        tags_text = " | ".join(
                            f"categoria: {tag}" for tag in semantic_tags
                        )
                        content_parts.append(tags_text)
                        logger.debug(
                            f"Etiquetas semánticas inyectadas en embedding "
                            f"para {source_id}: {semantic_tags}"
                        )
                    
                    content = " ".join(content_parts)
                    
                    if not content.strip():
                        logger.warning(f"Registro {source_id} sin contenido para embedding, saltando")
                        stats['skipped'] += 1
                        continue
                    
                    # Calcular hash del contenido
                    content_hash = cls.calculate_content_hash(content)
                    
                    # Buscar documento existente
                    try:
                        document = IntelligenceDocument.objects.get(
                            collection=collection,
                            source_id=source_id
                        )
                        
                        # Verificar si el contenido cambió
                        if document.content_hash == content_hash and not force_full_sync:
                            stats['skipped'] += 1
                            continue
                        
                        # Actualizar documento existente
                        document.content = content
                        document.content_hash = content_hash
                        document.field_values = field_values
                        
                        # Regenerar embedding si el contenido cambió o force_full_sync
                        if document.content_hash != content_hash or force_full_sync:
                            embedding = cls.generate_embedding(content, mode='passage')
                            if embedding:
                                document.embedding = embedding
                        
                        document.save()
                        stats['updated'] += 1
                        logger.debug(f"Documento actualizado: {source_id}")
                        
                    except IntelligenceDocument.DoesNotExist:
                        # Crear nuevo documento
                        embedding = cls.generate_embedding(content, mode='passage')
                        
                        document = IntelligenceDocument.objects.create(
                            collection=collection,
                            source_id=source_id,
                            content=content,
                            content_hash=content_hash,
                            embedding=embedding,
                            field_values=field_values
                        )
                        stats['created'] += 1
                        logger.debug(f"Documento creado: {source_id}")
                    
                    stats['total_processed'] += 1
                    
                    # Log cada 100 registros
                    if stats['total_processed'] % 100 == 0:
                        logger.info(f"Procesados {stats['total_processed']} registros...")
                    
                except Exception as e:
                    logger.error(f"Error procesando registro {i}: {e}")
                    stats['errors'] += 1
            
            # Actualizar estadísticas de la colección
            collection.last_sync_at = timezone.now()
            collection.last_sync_count = stats['total_processed']
            collection.save()
            
            logger.info(
                f"Sincronización dinámica completada para '{collection.name}': "
                f"{stats['created']} creados, {stats['updated']} actualizados, "
                f"{stats['skipped']} saltados, {stats['errors']} errores"
            )
            
            # Reconstruir índice FAISS después de sync (si está disponible)
            try:
                from .faiss_index import FAISSIndexManager
                indexed = FAISSIndexManager.rebuild_for_collection(
                    collection.name,
                    cls.EMBEDDING_DIMENSIONS
                )
                if indexed > 0:
                    logger.info(f"Índice FAISS reconstruido para '{collection.name}': {indexed} vectores")
            except ImportError:
                logger.debug("FAISS no disponible, saltando reconstrucción de índice")
            except Exception as e:
                logger.warning(f"Error reconstruyendo índice FAISS para '{collection.name}': {e}")
            
            return True, "Sincronización dinámica completada exitosamente", stats
            
        except IntelligenceCollection.DoesNotExist:
            return False, f"Colección '{collection_name}' no encontrada o inactiva", stats
        except Exception as e:
            logger.error(f"Error en sync_collection_dynamic: {e}")
            return False, f"Error en sincronización dinámica: {str(e)}", stats
    
    @classmethod
    def _resolve_foreign_key(
        cls,
        fk_value: Any,
        referenced_table: str,
        referenced_column: str = 'id',
        referenced_schema: str = 'dbo',
        display_fields: List[str] = None,
        label: str = '',
        database_alias: str = 'propifai',
        conn = None
    ) -> Optional[str]:
        """
        Resuelve un valor FK consultando la tabla referenciada y generando texto enriquecido.
        
        Args:
            fk_value: Valor del FK a resolver
            referenced_table: Nombre de la tabla referenciada
            referenced_column: Columna de join en la tabla referenciada
            referenced_schema: Esquema de la tabla referenciada
            display_fields: Campos a incluir en el texto enriquecido
            label: Etiqueta descriptiva para el texto generado
            database_alias: Alias de la base de datos
            conn: Conexión existente (opcional, para reutilizar)
            
        Returns:
            Texto enriquecido o None si no se pudo resolver
        """
        if not fk_value or not referenced_table or not display_fields:
            return None
        
        try:
            # Obtener conexión
            if conn is None:
                conn = connections[database_alias]
            
            # Construir consulta para obtener los campos solicitados
            display_cols = ', '.join([f'[{c}]' for c in display_fields])
            sql = f"SELECT {display_cols} FROM [{referenced_schema}].[{referenced_table}] WHERE [{referenced_column}] = %s"
            
            with conn.cursor() as cursor:
                cursor.execute(sql, (fk_value,))
                row = cursor.fetchone()
                
                if row is None:
                    logger.debug(f"FK {fk_value} no encontrado en {referenced_table}.{referenced_column}")
                    return None
                
                # Construir texto enriquecido
                parts = []
                for i, field_name in enumerate(display_fields):
                    val = row[i]
                    if val is not None:
                        # Serializar valores especiales
                        if hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        elif isinstance(val, bytes):
                            val = val.decode('utf-8', errors='replace')
                        parts.append(f"{field_name}: {val}")
                
                if not parts:
                    return None
                
                # Formatear con label si existe
                if label:
                    enriched = f"{label}: {' | '.join(parts)}"
                else:
                    enriched = ' | '.join(parts)
                
                logger.debug(f"FK resuelto: {fk_value} -> {enriched[:100]}...")
                return enriched
                
        except Exception as e:
            logger.warning(f"Error resolviendo FK {fk_value} en {referenced_table}: {e}")
            return None
    
    @classmethod
    def _build_field_values_to_display(cls, doc) -> Dict[str, Any]:
        """
        Construye field_values para mostrar, incluyendo campos FK resueltos.
        
        Si la colección tiene display_fields configurados, solo incluye esos campos
        MÁS los campos FK resueltos (los que terminan en '_name').
        Si no hay display_fields, devuelve todos los field_values.
        """
        display_fields = doc.collection.display_fields or []
        all_field_values = doc.field_values or {}
        
        if not display_fields:
            return all_field_values
        
        field_values_to_display = {}
        
        # 1. Incluir campos explícitos de display_fields
        for field in display_fields:
            if field in all_field_values:
                field_values_to_display[field] = all_field_values[field]
        
        # 2. Incluir automáticamente campos FK resueltos (_name)
        #    para que el LLM vea nombres reales en lugar de IDs numéricos
        for key, value in all_field_values.items():
            if key.endswith('_name') and value is not None and value != '':
                field_values_to_display[key] = value
        
        return field_values_to_display

    @classmethod
    def _text_search_fallback(
        cls,
        query: str,
        collections,
        filters: Dict[str, Any] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda por texto como fallback cuando la búsqueda vectorial no encuentra resultados.
        Busca palabras clave de la query en el contenido de los documentos.
        
        Args:
            query: Texto de búsqueda
            collections: QuerySet de colecciones
            filters: Filtros adicionales
            limit: Número máximo de resultados
            
        Returns:
            Lista de diccionarios con resultados
        """
        if not query or not query.strip():
            return []
        
        try:
            # Extraer palabras clave de la query (ignorar palabras comunes)
            stop_words = {'que', 'en', 'el', 'la', 'los', 'las', 'de', 'del', 'para', 'con',
                         'por', 'un', 'una', 'y', 'e', 'o', 'a', 'al', 'es', 'se', 'no',
                         'me', 'te', 'le', 'lo', 'tu', 'su', 'como', 'mas', 'pero',
                         'tienes', 'puedes', 'quiero', 'necesito', 'hay', 'esta', 'este'}
            
            words = query.lower().split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]
            
            if not keywords:
                logger.info(f"No se extrajeron palabras clave de la query: '{query}'")
                return []
            
            logger.info(f"Búsqueda por texto con palabras clave: {keywords}")
            
            # Construir query de búsqueda por contenido
            from django.db.models import Q
            
            text_query = Q()
            for keyword in keywords:
                text_query |= Q(content__icontains=keyword)
            
            # Obtener documentos que coincidan
            documents = IntelligenceDocument.objects.filter(
                collection__in=collections,
                embedding__isnull=False  # Solo documentos con embedding
            ).filter(text_query).select_related('collection')
            
            # --- F1-002: Aplicar filtros SQL también en el fallback de texto ---
            if filters:
                try:
                    filter_q = Q()
                    for field_name, field_value in filters.items():
                        filter_q &= Q(**{f'field_values__{field_name}': field_value})
                    documents = documents.filter(filter_q)
                    logger.debug(
                        f"F1-002: Filtros aplicados en text_fallback vía Django ORM: {filters}"
                    )
                except Exception as orm_err:
                    logger.warning(
                        f"F1-002: Django ORM falló en text_fallback, usando RawSQL JSON_VALUE: {orm_err}"
                    )
                    for field_name, field_value in filters.items():
                        sql_clause = f"JSON_VALUE(field_values, '$.\"{field_name}\"') = %s"
                        documents = documents.extra(
                            where=[sql_clause],
                            params=[str(field_value)]
                        )
            
            documents = documents[:limit * 3]  # Obtener más para filtrar después
            
            if not documents:
                logger.info(f"No se encontraron documentos con palabras clave: {keywords}")
                return []
            
            # Calcular score de relevancia basado en cuántas palabras clave coinciden
            results = []
            for doc in documents:
                content_lower = doc.content.lower()
                match_count = sum(1 for kw in keywords if kw in content_lower)
                match_ratio = match_count / len(keywords) if keywords else 0
                
                # Score: 0.5 base + bonus por coincidencias
                score = 0.5 + (match_ratio * 0.3)
                
                # Obtener field_values incluyendo FK resueltos
                field_values_to_display = cls._build_field_values_to_display(doc)
                
                result = {
                    'document_id': str(doc.id),
                    'collection_name': doc.collection.name,
                    'source_id': doc.source_id,
                    'similarity': min(score, 0.99),  # No superar 0.99
                    'field_values': field_values_to_display,
                    'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None,
                    'search_type': 'text',
                    'match_keywords': match_count,
                    'total_keywords': len(keywords)
                }
                results.append(result)
            
            # Ordenar por score descendente
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limitar resultados
            results = results[:limit]
            
            logger.info(f"Búsqueda por texto: {len(results)} resultados para keywords: {keywords}")
            return results
            
        except Exception as e:
            logger.error(f"Error en búsqueda por texto fallback: {e}")
            return []
    
    @classmethod
    def get_accessible_collections(cls, collection_names: List[str], profile=None) -> List:
        """
        Filtra colecciones según el perfil de inteligencia del usuario.
        
        Si no se proporciona profile, retorna todas las colecciones activas
        (comportamiento original, sin filtro de permisos).
        
        Args:
            collection_names: Nombres de colecciones solicitadas
            profile: UserIntelligenceProfile opcional para filtrar por permisos
            
        Returns:
            QuerySet de IntelligenceCollection filtrado
        """
        collections = IntelligenceCollection.objects.filter(
            name__in=collection_names,
            is_active=True
        )
        
        if not collections.exists():
            return collections
        
        if profile is None:
            # Sin perfil: retornar todas (comportamiento legacy)
            return collections
        
        # Filtrar por perfil de inteligencia
        accessible_ids = []
        blocked_ids = []
        
        # Obtener IDs de colecciones extra y bloqueadas del perfil
        extra_ids = set(profile.extra_collections.values_list('id', flat=True)) if hasattr(profile, 'extra_collections') else set()
        blocked_ids_set = set(profile.blocked_collections.values_list('id', flat=True)) if hasattr(profile, 'blocked_collections') else set()
        
        for coll in collections:
            # 1. Bloqueo explícito
            if coll.id in blocked_ids_set:
                blocked_ids.append(str(coll.id))
                continue
            
            # 2. Verificar nivel mínimo
            if profile.level < coll.min_level:
                logger.debug(f"Colección '{coll.name}': nivel insuficiente ({profile.level} < {coll.min_level})")
                continue
            
            # 3. Colección pública → acceso concedido
            if coll.is_public:
                accessible_ids.append(coll.id)
                continue
            
            # 4. Colección extra → acceso concedido
            if coll.id in extra_ids:
                accessible_ids.append(coll.id)
                continue
            
            # 5. Verificar dominio
            if coll.domain in profile.allowed_domains:
                accessible_ids.append(coll.id)
                continue
            
            logger.debug(f"Colección '{coll.name}': dominio '{coll.domain}' no permitido para el usuario")
        
        if blocked_ids:
            logger.warning(f"Colecciones bloqueadas para el usuario: {blocked_ids}")
        
        if not accessible_ids:
            logger.warning(f"El usuario no tiene acceso a ninguna de las colecciones solicitadas: {collection_names}")
            return IntelligenceCollection.objects.none()
        
        return collections.filter(id__in=accessible_ids)
    
    @classmethod
    def search_dynamic(
        cls,
        query: str,
        collection_names: List[str],
        filters: Dict[str, Any] = None,
        top_k: int = 9999,
        profile=None
    ) -> List[Dict[str, Any]]:
        """
        Busca en colecciones dinámicas y retorna field_values con nombres REALES.
        
        Args:
            query: Texto de búsqueda
            collection_names: Nombres de colecciones a buscar
            filters: Diccionario con filtros a aplicar {campo: valor}
            top_k: Número máximo de resultados
            profile: UserIntelligenceProfile opcional para filtrar por permisos
            
        Returns:
            Lista de diccionarios con resultados
        """
        if not query or not query.strip():
            return []
        
        try:
            # Generar embedding para la query (modo query para multilingual-e5-small)
            query_embedding = cls.generate_embedding(query, mode='query')
            if not query_embedding:
                logger.error("No se pudo generar embedding para la query")
                return []
            
            # Convertir embedding a numpy array
            query_vector = np.frombuffer(query_embedding, dtype=np.float32)
            
            # Obtener colecciones filtradas por perfil de inteligencia
            collections = cls.get_accessible_collections(collection_names, profile=profile)
            
            if not collections.exists():
                logger.warning(f"No se encontraron colecciones accesibles con nombres: {collection_names}")
                return []
            
            # --- PRE-FILTRADO EN SQL (F1-002) ---
            # Aplicar filtros directamente en la BD en lugar de cargar todo a memoria.
            # Estrategia:
            #   1. Django JSONField key transforms (field_values__campo=valor)
            #   2. Fallback: RawSQL con JSON_VALUE() si el ORM no soporta la sintaxis
            documents = IntelligenceDocument.objects.filter(
                collection__in=collections,
                embedding__isnull=False
            ).select_related('collection')
            
            total_pre_filtro = documents.count()
            
            if filters:
                from django.db.models import Q
                filter_q = Q()
                filter_details = []
                
                for field_name, field_value in filters.items():
                    filter_details.append(f"{field_name}={field_value}")
                    # Opción 1: Django JSONField key transform
                    # En SQL Server con mssql-django se traduce internamente
                    # usando JSON_VALUE, pero puede fallar según la version del driver
                    filter_q &= Q(**{f'field_values__{field_name}': field_value})
                
                try:
                    documents = documents.filter(filter_q)
                    logger.info(
                        f"F1-002: Filtros aplicados vía Django ORM: {', '.join(filter_details)} | "
                        f"Docs pre-filtro: {total_pre_filtro} | Docs post-filtro: {documents.count()}"
                    )
                except Exception as orm_err:
                    # Opción 2 (fallback): RawSQL con JSON_VALUE (SQL Server nativo)
                    logger.warning(
                        f"F1-002: Django ORM falló para filtros, usando RawSQL JSON_VALUE: {orm_err}"
                    )
                    documents = IntelligenceDocument.objects.filter(
                        collection__in=collections,
                        embedding__isnull=False
                    ).select_related('collection')
                    
                    for field_name, field_value in filters.items():
                        # JSON_VALUE extrae el valor de un campo JSON en SQL Server
                        # $."campo" es la notación JSON path de SQL Server
                        sql_clause = f"JSON_VALUE(field_values, '$.\"{field_name}\"') = %s"
                        documents = documents.extra(
                            where=[sql_clause],
                            params=[str(field_value)]
                        )
                    
                    logger.info(
                        f"F1-002: Filtros aplicados vía RawSQL JSON_VALUE: {', '.join(filter_details)} | "
                        f"Docs pre-filtro: {total_pre_filtro} | Docs post-filtro: {documents.count()}"
                    )
            
            # --- BÚSQUEDA SEMÁNTICA (P2) ---
            # Si hay filtros aplicados, NO usar FAISS (no soporta filtros).
            # Usar búsqueda O(n) que respeta el QuerySet filtrado.
            results = []
            threshold = cls.SIMILARITY_THRESHOLD
            use_faiss = not filters  # FAISS solo cuando no hay filtros
            
            if use_faiss:
                # OPTIMIZACIÓN: Cuando usamos FAISS, NO necesitamos hacer
                # documents.count() ni documents.exists() porque FAISS
                # ya nos da los resultados directamente.
                try:
                    from .faiss_index import FAISSIndexManager
                    
                    # Procesar cada colección por separado (cada una tiene su propio índice FAISS)
                    for collection in collections:
                        faiss_index = FAISSIndexManager.get_instance(
                            collection.name,
                            cls.EMBEDDING_DIMENSIONS
                        )
                        
                        if faiss_index.is_loaded:
                            # Búsqueda FAISS con top_k original (9999).
                            # Retorna TODOS los resultados sin limitar.
                            faiss_results = faiss_index.search(query_vector, top_k=top_k)
                            
                            if faiss_results:
                                # Obtener documentos completos desde BD
                                doc_ids = [r['document_id'] for r in faiss_results]
                                docs_map = {
                                    str(d.id): d
                                    for d in IntelligenceDocument.objects.filter(id__in=doc_ids)
                                }
                                
                                for fr in faiss_results:
                                    doc = docs_map.get(fr['document_id'])
                                    if doc and fr['similarity'] >= threshold:
                                        field_values_to_display = cls._build_field_values_to_display(doc)
                                        
                                        results.append({
                                            'document_id': str(doc.id),
                                            'collection_name': doc.collection.name,
                                            'source_id': doc.source_id,
                                            'similarity': fr['similarity'],
                                            'field_values': field_values_to_display,
                                            'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
                                            'created_at': doc.created_at.isoformat() if doc.created_at else None,
                                            'search_type': 'vector_faiss'
                                        })
                        else:
                            # Fallback: búsqueda O(n) para esta colección
                            logger.debug(f"FAISS no disponible para '{collection.name}', usando búsqueda O(n)")
                            collection_docs = documents.filter(collection=collection)
                            
                            for doc in collection_docs:
                                try:
                                    doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                                    similarity = np.dot(query_vector, doc_vector) / (
                                        np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                                    )
                                    
                                    if similarity >= threshold:
                                        field_values_to_display = cls._build_field_values_to_display(doc)
                                        
                                        results.append({
                                            'document_id': str(doc.id),
                                            'collection_name': doc.collection.name,
                                            'source_id': doc.source_id,
                                            'similarity': float(similarity),
                                            'field_values': field_values_to_display,
                                            'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
                                            'created_at': doc.created_at.isoformat() if doc.created_at else None,
                                            'search_type': 'vector'
                                        })
                                except Exception as e:
                                    logger.warning(f"Error calculando similitud para documento {doc.id}: {e}")
                                    continue
                    
                except ImportError:
                    # FAISS no instalado, usar búsqueda O(n) tradicional
                    logger.debug("FAISS no disponible, usando búsqueda O(n) tradicional")
                    use_faiss = False
            
            if not use_faiss:
                # Búsqueda O(n) tradicional - respeta filtros SQL
                # OPTIMIZACIÓN: Solo procesar documentos que existen
                if not documents.exists():
                    if filters:
                        logger.info(f"F1-002: Sin documentos después de filtrar: {filters}")
                    return []
                
                logger.debug(
                    f"Usando búsqueda O(n) tradicional "
                    f"(faiss={'no disponible' if use_faiss is False else 'filtros activos'})"
                )
                for doc in documents:
                    try:
                        doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                        similarity = np.dot(query_vector, doc_vector) / (
                            np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                        )
                        
                        if similarity >= threshold:
                            field_values_to_display = cls._build_field_values_to_display(doc)
                            
                            results.append({
                                'document_id': str(doc.id),
                                'collection_name': doc.collection.name,
                                'source_id': doc.source_id,
                                'similarity': float(similarity),
                                'field_values': field_values_to_display,
                                'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
                                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                                'search_type': 'vector'
                            })
                    except Exception as e:
                        logger.warning(f"Error calculando similitud para documento {doc.id}: {e}")
                        continue
            
            # Si hay pocos resultados con búsqueda vectorial, activar fallback de texto para recuperar más.
            # El fallback busca por palabras clave en SQL (LIKE) y es costoso (~6-60s).
            # Solo se activa cuando la búsqueda vectorial devuelve muy pocos resultados (< MIN_RESULTS_FOR_FALLBACK).
            # Los resultados del fallback se DEDUPLICAN contra los vectoriales, no se pierden.
            # top_k NO se usa aquí porque es 9999 (siempre activaría el fallback).
            # El fallback de texto solo se activa si hay muy pocos resultados vectoriales.
            # La condición original `len(results) < top_k` con top_k=9999 SIEMPRE activaba el fallback,
            # causando 60-90s de latencia innecesaria cuando FAISS ya encontró suficientes resultados.
            if len(results) < cls.MIN_RESULTS_FOR_FALLBACK and cls.ENABLE_TEXT_FALLBACK:
                logger.info(
                    f"Búsqueda vectorial encontró solo {len(results)} resultados "
                    f"(< mínimo {cls.MIN_RESULTS_FOR_FALLBACK}). "
                    f"Activando fallback de texto..."
                )
                
                # Búsqueda por texto en el contenido
                # El limit usa el valor original. Si hay pocos resultados vectoriales,
                # el fallback busca más sin limitar la cantidad.
                text_results = cls._text_search_fallback(
                    query=query,
                    collections=collections,
                    filters=filters,
                    limit=top_k - len(results)
                )
                
                # Agregar resultados de texto
                for text_result in text_results:
                    text_result['search_type'] = 'text'
                    results.append(text_result)
            
            # Eliminar duplicados por document_id
            seen_ids = set()
            unique_results = []
            for r in results:
                doc_id = r.get('document_id')
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_results.append(r)
            
            logger.debug(
                f"F1-002: Deduplicados: {len(results)} → {len(unique_results)} únicos"
            )
            results = unique_results
            
            # Ordenar por similitud descendente (los resultados de texto tendrán similarity=0.5)
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limitar resultados
            results = results[:top_k]
            
            # Log detallado - incluyendo vector_faiss
            vector_count = sum(1 for r in results if r.get('search_type') in ('vector', 'vector_faiss'))
            text_count = sum(1 for r in results if r.get('search_type') == 'text')
            faiss_count = sum(1 for r in results if r.get('search_type') == 'vector_faiss')
            
            logger.info(
                f"Búsqueda dinámica completada: {len(results)} resultados "
                f"(vector: {vector_count}, faiss: {faiss_count}, texto: {text_count}) "
                f"para query: '{query[:80]}...'"
            )
            return results
            
        except Exception as e:
            logger.error(f"Error en búsqueda dinámica RAG: {e}")
            return []


# =============================================================================
# FUNCIÓN HELPER: get_collections_for_user
# =============================================================================

def get_collections_for_user(user) -> List[IntelligenceCollection]:
    """
    Obtiene todas las colecciones de inteligencia accesibles para un usuario.
    
    Usa el UserIntelligenceProfile del usuario para filtrar colecciones según:
    - Nivel mínimo (min_level)
    - Dominios permitidos (allowed_domains)
    - Colecciones extra (extra_collections)
    - Colecciones bloqueadas (blocked_collections)
    - Flag is_public
    
    Args:
        user: Instancia de User (de intelligence.models)
        
    Returns:
        Lista de IntelligenceCollection accesibles para el usuario
    """
    from intelligence.models import UserIntelligenceProfile
    
    try:
        profile = UserIntelligenceProfile.objects.get(user=user)
    except UserIntelligenceProfile.DoesNotExist:
        logger.warning(f"Usuario {user.id} no tiene perfil de inteligencia. Retornando colecciones públicas.")
        return list(IntelligenceCollection.objects.filter(is_active=True, is_public=True))
    
    collections = list(IntelligenceCollection.objects.filter(is_active=True))
    
    extra_ids = set(profile.extra_collections.values_list('id', flat=True)) if hasattr(profile, 'extra_collections') else set()
    blocked_ids_set = set(profile.blocked_collections.values_list('id', flat=True)) if hasattr(profile, 'blocked_collections') else set()
    
    accessible = []
    for coll in collections:
        # Bloqueo explícito
        if coll.id in blocked_ids_set:
            continue
        
        # Nivel mínimo
        if profile.level < coll.min_level:
            continue
        
        # Pública o extra → acceso directo
        if coll.is_public or coll.id in extra_ids:
            accessible.append(coll)
            continue
        
        # Coincidencia de dominio
        if coll.domain in profile.allowed_domains:
            accessible.append(coll)
            continue
    
    logger.info(f"get_collections_for_user(user={user.id}): {len(accessible)}/{len(collections)} colecciones accesibles")
    return accessible
