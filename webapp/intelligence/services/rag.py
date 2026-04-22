"""
Servicio RAG (Retrieval Augmented Generation) para búsqueda semántica
y gestión de colecciones vectoriales.

Implementa el sistema de embeddings y búsqueda por similitud de coseno
para documentos almacenados en IntelligenceDocument.
"""
import os
import json
import hashlib
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import logging

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
    - Generación de embeddings
    - Gestión de colecciones
    - Sincronización de datos
    - Búsqueda semántica
    """
    
    # Modelo de embeddings (all-MiniLM-L6-v2)
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS = 384
    
    # Configuración desde variables de entorno
    SIMILARITY_THRESHOLD = float(os.environ.get('RAG_SIMILARITY_THRESHOLD', 0.7))
    MAX_RESULTS = int(os.environ.get('RAG_MAX_RESULTS', 10))
    BATCH_SIZE = int(os.environ.get('RAG_BATCH_SIZE', 100))
    
    # Singleton para el modelo de embeddings
    _embedder = None
    
    @classmethod
    def initialize_embedder(cls):
        """
        Inicializa el modelo de embeddings (sentence-transformers).
        Usa lazy loading para evitar cargar el modelo si no se necesita.
        
        Returns:
            Modelo de embeddings cargado
        """
        if cls._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Inicializando modelo de embeddings: {cls.EMBEDDING_MODEL}")
                cls._embedder = SentenceTransformer(cls.EMBEDDING_MODEL)
                logger.info(f"Modelo de embeddings inicializado ({cls.EMBEDDING_DIMENSIONS} dimensiones)")
            except ImportError as e:
                logger.error(f"Error al importar sentence-transformers: {e}")
                raise ImportError(
                    "La librería sentence-transformers no está instalada. "
                    "Instala con: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error(f"Error al inicializar modelo de embeddings: {e}")
                raise
        
        return cls._embedder
    
    @classmethod
    def get_embedder(cls):
        """Obtiene el embedder inicializado (lazy loading)."""
        return cls.initialize_embedder()
    
    @classmethod
    def generate_embedding(cls, text: str) -> Optional[bytes]:
        """
        Genera embedding vectorial para un texto.
        
        Args:
            text: Texto a convertir en embedding
            
        Returns:
            Bytes del embedding (384 dimensiones) o None si hay error
        """
        if not text or not text.strip():
            return None
        
        try:
            embedder = cls.get_embedder()
            # Generar embedding
            embedding_np = embedder.encode(text, convert_to_numpy=True)
            
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
            return embedding_np.tobytes()
            
        except Exception as e:
            logger.error(f"Error al generar embedding: {e}")
            return None
    
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
        access_level: int = 1,
        description: str = "",
        is_active: bool = True
    ) -> Tuple[bool, str, Optional[IntelligenceCollection]]:
        """
        Crea una nueva colección vectorial.
        
        Args:
            name: Nombre único de la colección
            source_sql: Consulta SQL que devuelve los datos fuente
            embedding_fields: Lista de campos a concatenar para embedding
            access_level: Nivel de acceso requerido (1, 2, 3)
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
                embedding_fields=embedding_fields,  # JSONField acepta listas directamente
                access_level=access_level,
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
        # Por defecto usar conexión 'default'
        conn = connections['default']
        
        # Si la colección es de Propifai o hace referencia a tabla 'properties'
        # o si el SQL hace referencia a la base de datos propifai
        collection_name_lower = collection.name.lower()
        source_sql_lower = collection.source_sql.lower()
        
        if ('propifai' in collection_name_lower or
            'properties' in source_sql_lower or
            'from propifai.' in source_sql_lower or
            'from [propifai].' in source_sql_lower or
            'dbpropifai' in source_sql_lower):
            
            # Verificar si existe conexión 'propifai'
            if 'propifai' in connections:
                conn = connections['propifai']
                logger.debug(f"Usando conexión 'propifai' para colección: {collection.name}")
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
        similarity_threshold: Optional[float] = None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Realiza búsqueda semántica por similitud de coseno.
        
        Args:
            query: Texto de búsqueda
            collection_ids: IDs de colecciones a buscar (None = todas activas)
            access_level: Nivel de acceso del usuario
            limit: Límite de resultados (None = usar valor por defecto)
            similarity_threshold: Umbral de similitud (None = usar valor por defecto)
            
        Returns:
            Tuple (success, message, results)
        """
        if not query or not query.strip():
            return False, "Query vacía", []
        
        try:
            # Generar embedding para la query
            query_embedding = cls.generate_embedding(query)
            if not query_embedding:
                return False, "No se pudo generar embedding para la query", []
            
            # Convertir embedding a numpy array
            query_vector = np.frombuffer(query_embedding, dtype=np.float32)
            
            # Obtener colecciones filtradas
            collections_query = IntelligenceCollection.objects.filter(
                is_active=True,
                access_level__lte=access_level  # Usuario tiene acceso igual o mayor
            )
            
            if collection_ids:
                collections_query = collections_query.filter(id__in=collection_ids)
            
            collections = list(collections_query)
            
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
                'access_level': collection.access_level,
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
                'access_level': 1  # Nivel más bajo - acceso público
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
                'access_level': 2  # Nivel intermedio - acceso interno
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
                'access_level': 3  # Nivel más alto - acceso estratégico
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
                    access_level=collection_def['access_level'],
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
            database_alias: Alias de la conexión de base de datos (default: 'default', 'propifai' para dbpropify)
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
            database_alias: Alias de la conexión de base de datos (default: 'default', 'propifai' para dbpropify)
            
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
    def create_collection_dynamic(
        cls,
        name: str,
        table_name: str,
        embedding_fields: List[str],
        display_fields: List[str],
        filter_fields: List[str],
        access_level: int = 2,
        description: str = "",
        schema: str = None,
        database_alias: str = 'default'
    ) -> Tuple[bool, str, Optional[IntelligenceCollection]]:
        """
        Crea colección con campos dinámicos según SPEC-003.
        
        Args:
            name: Nombre único de la colección
            table_name: Nombre exacto de la tabla en Azure SQL
            embedding_fields: Lista de campos (nombres reales) usados para embedding
            display_fields: Lista de campos (nombres reales) a mostrar en resultados
            filter_fields: Lista de campos (nombres reales) que se pueden filtrar
            access_level: Nivel de acceso requerido (1, 2, 3)
            description: Descripción opcional
            schema: Esquema de la tabla
            database_alias: Alias de la conexión de base de datos (default: 'default', 'propifai' para dbpropify)
            
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
            
            # Obtener field_definitions de la tabla
            schema_analysis = SchemaDiscoveryService.analyze_table_schema(table_name, schema=schema, database_alias=database_alias)
            if not schema_analysis.get('exists', False):
                return False, f"No se pudo analizar la tabla '{table_name}': {schema_analysis.get('error', 'Error desconocido')}", None
            
            field_definitions = schema_analysis.get('field_definitions', {})
            primary_key = schema_analysis.get('primary_key', 'id')
            
            # Validar que los campos especificados existen en la tabla
            all_columns = [col['name'] for col in schema_analysis.get('columns', [])]
            
            for field_list, field_type in [
                (embedding_fields, 'embedding'),
                (display_fields, 'display'),
                (filter_fields, 'filter')
            ]:
                for field in field_list:
                    if field not in all_columns:
                        return False, f"Campo '{field}' no existe en la tabla '{table_name}' para {field_type}", None
            
            # Crear SQL automático si no se proporciona
            source_sql = f"SELECT * FROM [{schema or 'dbo'}].[{table_name}]"
            
            # Crear colección
            collection = IntelligenceCollection.objects.create(
                name=name,
                table_name=table_name,
                description=description,
                source_sql=source_sql,
                field_definitions=field_definitions,
                embedding_fields=embedding_fields,
                display_fields=display_fields,
                filter_fields=filter_fields,
                access_level=access_level,
                is_active=True
            )
            
            logger.info(f"Colección dinámica creada: {name} (Tabla: {table_name}, ID: {collection.id})")
            return True, f"Colección '{name}' creada exitosamente con {len(field_definitions)} campos", collection
            
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
            if database_alias:
                # Usar el database_alias proporcionado
                try:
                    conn = connections[database_alias]
                    logger.info(f"Usando conexión específica: {database_alias}")
                except Exception as e:
                    logger.warning(f"No se pudo usar conexión '{database_alias}': {e}, usando detección automática")
                    conn = cls._get_connection_for_collection(collection)
            else:
                # Detectar automáticamente
                conn = cls._get_connection_for_collection(collection)
            
            # Construir consulta SQL automática
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
            field_definitions = collection.field_definitions or {}
            
            # Determinar campo ID
            primary_key = None
            for field_name, field_def in field_definitions.items():
                if field_def.get('is_primary', False):
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
                    
                    # Construir texto para embedding usando solo los campos en embedding_fields
                    content_parts = []
                    for field in collection.embedding_fields:
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
                        document.field_values = field_values
                        
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
            
            return True, "Sincronización dinámica completada exitosamente", stats
            
        except IntelligenceCollection.DoesNotExist:
            return False, f"Colección '{collection_name}' no encontrada o inactiva", stats
        except Exception as e:
            logger.error(f"Error en sync_collection_dynamic: {e}")
            return False, f"Error en sincronización dinámica: {str(e)}", stats
    
    @classmethod
    def search_dynamic(
        cls,
        query: str,
        collection_names: List[str],
        filters: Dict[str, Any] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Busca en colecciones dinámicas y retorna field_values con nombres REALES.
        
        Args:
            query: Texto de búsqueda
            collection_names: Nombres de colecciones a buscar
            filters: Diccionario con filtros a aplicar {campo: valor}
            top_k: Número máximo de resultados
            
        Returns:
            Lista de diccionarios con resultados
        """
        if not query or not query.strip():
            return []
        
        try:
            # Generar embedding para la query
            query_embedding = cls.generate_embedding(query)
            if not query_embedding:
                logger.error("No se pudo generar embedding para la query")
                return []
            
            # Convertir embedding a numpy array
            query_vector = np.frombuffer(query_embedding, dtype=np.float32)
            
            # Obtener colecciones
            collections = IntelligenceCollection.objects.filter(
                name__in=collection_names,
                is_active=True
            )
            
            if not collections.exists():
                logger.warning(f"No se encontraron colecciones con nombres: {collection_names}")
                return []
            
            # Obtener todos los documentos de las colecciones
            documents = IntelligenceDocument.objects.filter(
                collection__in=collections,
                embedding__isnull=False
            ).select_related('collection')
            
            # Aplicar filtros si se proporcionan
            if filters:
                # Filtrado básico por campo (igualdad exacta)
                for field_name, field_value in filters.items():
                    # Filtrar documentos cuyo field_values[field_name] == field_value
                    # Esto es ineficiente para muchos documentos, pero funciona para demostración
                    filtered_docs = []
                    for doc in documents:
                        if field_name in doc.field_values and doc.field_values[field_name] == field_value:
                            filtered_docs.append(doc)
                    documents = filtered_docs
            
            if not documents:
                return []
            
            # Calcular similitud para cada documento
            results = []
            threshold = cls.SIMILARITY_THRESHOLD
            
            for doc in documents:
                try:
                    # Convertir embedding del documento a numpy
                    doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                    
                    # Calcular similitud de coseno
                    similarity = np.dot(query_vector, doc_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                    )
                    
                    # Filtrar por umbral
                    if similarity >= threshold:
                        # Obtener solo los campos display_fields de la colección
                        display_fields = doc.collection.display_fields or []
                        field_values_to_display = {}
                        
                        if display_fields:
                            for field in display_fields:
                                if field in doc.field_values:
                                    field_values_to_display[field] = doc.field_values[field]
                        else:
                            # Si no hay display_fields definidos, mostrar todos
                            field_values_to_display = doc.field_values
                        
                        result = {
                            'document_id': str(doc.id),
                            'collection_name': doc.collection.name,
                            'source_id': doc.source_id,
                            'similarity': float(similarity),
                            'field_values': field_values_to_display,
                            'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
                            'created_at': doc.created_at.isoformat() if doc.created_at else None
                        }
                        results.append(result)
                        
                except Exception as e:
                    logger.warning(f"Error calculando similitud para documento {doc.id}: {e}")
                    continue
            
            # Ordenar por similitud descendente
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limitar resultados
            results = results[:top_k]
            
            logger.info(f"Búsqueda dinámica completada: {len(results)} resultados para query: '{query[:50]}...'")
            return results
            
        except Exception as e:
            logger.error(f"Error en búsqueda dinámica RAG: {e}")
            return []
