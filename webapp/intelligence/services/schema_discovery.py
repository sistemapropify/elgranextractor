"""
Servicio de descubrimiento de esquemas de tablas en Azure SQL.

Proporciona funcionalidades para:
- Listar todas las tablas disponibles en la base de datos
- Obtener columnas y metadatos de una tabla específica
- Obtener datos de muestra para previsualización
- Validar que una tabla existe y es accesible

Este servicio es fundamental para el sistema RAG con campos dinámicos (SPEC-003),
ya que permite al administrador seleccionar cualquier tabla del sistema y
el sistema analiza automáticamente su estructura.
"""
import os
import logging
from typing import List, Dict, Optional, Any
from django.db import connections
from django.conf import settings

logger = logging.getLogger(__name__)


class SchemaDiscoveryService:
    """
    Servicio para descubrir y analizar esquemas de tablas en Azure SQL.
    """
    
    # Configuración desde variables de entorno
    DEFAULT_SCHEMA = os.environ.get('RAG_DEFAULT_SCHEMA', 'dbo')
    MAX_TABLES_TO_DISCOVER = int(os.environ.get('RAG_MAX_TABLES_TO_DISCOVER', 50))
    DISCOVERY_CACHE_TTL = int(os.environ.get('RAG_DISCOVERY_CACHE_TTL', 3600))
    
    # Cache simple en memoria (para desarrollo)
    _tables_cache = None
    _tables_cache_timestamp = None
    _columns_cache = {}
    
    @classmethod
    def _get_connection(cls, database_alias: str = 'default'):
        """
        Obtiene conexión a la base de datos.
        
        Args:
            database_alias: Alias de la conexión en settings.DATABASES
            
        Returns:
            Django database connection object
        """
        logger.info(f"SchemaDiscoveryService._get_connection: database_alias={database_alias}")
        try:
            conn = connections[database_alias]
            logger.info(f"Conexión obtenida: {conn}")
            return conn
        except Exception as e:
            logger.error(f"Error obteniendo conexión '{database_alias}': {e}")
            raise
    
    @classmethod
    def list_tables(cls, schema: str = None, database_alias: str = 'default', force_refresh: bool = False) -> List[str]:
        """
        Lista todas las tablas disponibles en Azure SQL.
        
        Args:
            schema: Esquema a consultar (default: 'dbo' o valor de RAG_DEFAULT_SCHEMA)
            database_alias: Alias de la conexión de base de datos
            force_refresh: Si True, ignora la caché y vuelve a consultar la base de datos
            
        Returns:
            Lista de nombres de tablas
        """
        if schema is None:
            schema = cls.DEFAULT_SCHEMA
        
        # DEBUG: Imprimir directamente para ver parámetros
        import sys
        print(f"[DEBUG] SchemaDiscoveryService.list_tables: schema={schema}, database_alias={database_alias}, force_refresh={force_refresh}", file=sys.stderr)
        print(f"[DEBUG] Cache key sería: {database_alias}:{schema}", file=sys.stderr)
        
        logger.info(f"SchemaDiscoveryService.list_tables: schema={schema}, database_alias={database_alias}, cache_key={database_alias}:{schema}, force_refresh={force_refresh}")
        
        # SOLUCIÓN TEMPORAL: Siempre forzar refresh cuando database_alias != 'default'
        # Esto evita problemas con cache de versiones antiguas del código
        if database_alias != 'default':
            force_refresh = True
            print(f"[DEBUG] Forzando refresh para database_alias={database_alias} (no es 'default')", file=sys.stderr)
        
        # Verificar cache (simple implementación para desarrollo)
        cache_key = f"{database_alias}:{schema}"
        
        # Si force_refresh es True, eliminar la entrada específica del cache
        if force_refresh:
            if cls._tables_cache is not None and cache_key in cls._tables_cache:
                del cls._tables_cache[cache_key]
                logger.info(f"Cache eliminado para {cache_key} (force_refresh=True)")
        
        if not force_refresh and (cls._tables_cache is not None and
            cls._tables_cache_timestamp is not None and
            cache_key in cls._tables_cache):
            # Verificar si el cache no ha expirado
            import time
            if time.time() - cls._tables_cache_timestamp < cls.DISCOVERY_CACHE_TTL:
                logger.debug(f"Retornando tablas desde cache para {cache_key}")
                return cls._tables_cache[cache_key]
        
        try:
            conn = cls._get_connection(database_alias)
            
            # Consulta para obtener tablas en SQL Server
            sql = """
            SELECT 
                TABLE_SCHEMA,
                TABLE_NAME,
                TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
            """
            
            with conn.cursor() as cursor:
                cursor.execute(sql, [schema])
                results = cursor.fetchall()
            
            tables = [row[1] for row in results if row[2] == 'BASE TABLE']  # Solo tablas, no vistas
            
            # Limitar si es necesario
            if cls.MAX_TABLES_TO_DISCOVER > 0 and len(tables) > cls.MAX_TABLES_TO_DISCOVER:
                tables = tables[:cls.MAX_TABLES_TO_DISCOVER]
                logger.warning(f"Limitando tablas a {cls.MAX_TABLES_TO_DISCOVER} de {len(results)} totales")
            
            # Actualizar cache
            if cls._tables_cache is None:
                cls._tables_cache = {}
            cls._tables_cache[cache_key] = tables
            import time
            cls._tables_cache_timestamp = time.time()
            
            logger.info(f"Descubiertas {len(tables)} tablas en esquema '{schema}'")
            return tables
            
        except Exception as e:
            logger.error(f"Error listando tablas en esquema '{schema}': {e}")
            raise
    
    @classmethod
    def get_table_columns(cls, table_name: str, schema: str = None, 
                         database_alias: str = 'default') -> List[Dict[str, Any]]:
        """
        Retorna columnas con metadatos de una tabla específica.
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema de la tabla (default: 'dbo' o valor de RAG_DEFAULT_SCHEMA)
            database_alias: Alias de la conexión de base de datos
            
        Returns:
            Lista de diccionarios con información de columnas:
            [
                {
                    'name': 'id',
                    'type': 'int',
                    'nullable': False,
                    'max_length': None,
                    'is_primary': True,
                    'is_identity': True,
                    'default_value': None
                },
                ...
            ]
        """
        if schema is None:
            schema = cls.DEFAULT_SCHEMA
        
        # Verificar cache
        cache_key = f"{database_alias}:{schema}.{table_name}"
        if cache_key in cls._columns_cache:
            logger.debug(f"Retornando columnas desde cache para {cache_key}")
            return cls._columns_cache[cache_key]
        
        try:
            conn = cls._get_connection(database_alias)
            
            # Consulta para obtener información detallada de columnas en SQL Server
            sql = """
            SELECT 
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE 
                    WHEN pk.COLUMN_NAME IS NOT NULL THEN 1
                    ELSE 0
                END AS IS_PRIMARY_KEY,
                COLUMNPROPERTY(OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT 
                    ku.TABLE_SCHEMA,
                    ku.TABLE_NAME, 
                    ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tc
                INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS ku
                    ON tc.CONSTRAINT_TYPE = 'PRIMARY KEY' 
                    AND tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA 
                AND c.TABLE_NAME = pk.TABLE_NAME 
                AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = %s AND c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
            """
            
            with conn.cursor() as cursor:
                cursor.execute(sql, [schema, table_name])
                columns_data = cursor.fetchall()
            
            if not columns_data:
                raise ValueError(f"Tabla '{schema}.{table_name}' no encontrada o sin columnas")
            
            columns = []
            for col in columns_data:
                column_info = {
                    'name': col[0],
                    'type': col[1].lower(),
                    'max_length': col[2],
                    'nullable': col[3] == 'YES',
                    'default_value': col[4],
                    'is_primary': bool(col[5]),
                    'is_identity': bool(col[6]),
                    'is_primary_key': bool(col[5]),  # Alias para compatibilidad
                }
                columns.append(column_info)
            
            # Almacenar en cache
            cls._columns_cache[cache_key] = columns
            
            logger.info(f"Obtenidas {len(columns)} columnas para tabla '{schema}.{table_name}'")
            return columns
            
        except Exception as e:
            logger.error(f"Error obteniendo columnas para tabla '{schema}.{table_name}': {e}")
            raise
    
    @classmethod
    def get_sample_data(cls, table_name: str, limit: int = 5, schema: str = None,
                       database_alias: str = 'default') -> List[Dict[str, Any]]:
        """
        Obtiene muestra de datos para previsualización.
        
        Args:
            table_name: Nombre de la tabla
            limit: Número máximo de registros a retornar
            schema: Esquema de la tabla (default: 'dbo' o valor de RAG_DEFAULT_SCHEMA)
            database_alias: Alias de la conexión de base de datos
            
        Returns:
            Lista de diccionarios con datos de muestra
        """
        if schema is None:
            schema = cls.DEFAULT_SCHEMA
        
        try:
            conn = cls._get_connection(database_alias)
            
            # Primero obtener columnas para construir SELECT *
            columns_info = cls.get_table_columns(table_name, schema, database_alias)
            column_names = [col['name'] for col in columns_info]
            
            # Construir consulta con limit apropiado para SQL Server
            # SQL Server usa TOP en lugar de LIMIT
            quoted_table = f"[{schema}].[{table_name}]" if '.' in table_name else f"[{table_name}]"
            sql = f"SELECT TOP {limit} * FROM {quoted_table}"
            
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            sample_data = []
            for row in rows:
                row_dict = {}
                for i, col_name in enumerate(column_names):
                    # Convertir tipos no serializables
                    value = row[i]
                    if hasattr(value, 'isoformat'):  # Para datetime/date
                        value = value.isoformat()
                    elif value is None:
                        value = None
                    row_dict[col_name] = value
                sample_data.append(row_dict)
            
            logger.info(f"Obtenidos {len(sample_data)} registros de muestra de '{schema}.{table_name}'")
            return sample_data
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de muestra de '{schema}.{table_name}': {e}")
            raise
    
    @classmethod
    def validate_table(cls, table_name: str, schema: str = None,
                      database_alias: str = 'default') -> bool:
        """
        Verifica que la tabla existe y es accesible.
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema de la tabla (default: 'dbo' o valor de RAG_DEFAULT_SCHEMA)
            database_alias: Alias de la conexión de base de datos
            
        Returns:
            True si la tabla existe y es accesible, False en caso contrario
        """
        if schema is None:
            schema = cls.DEFAULT_SCHEMA
        
        try:
            conn = cls._get_connection(database_alias)
            
            # Consulta simple para verificar existencia
            sql = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND TABLE_TYPE = 'BASE TABLE'
            """
            
            with conn.cursor() as cursor:
                cursor.execute(sql, [schema, table_name])
                result = cursor.fetchone()
            
            exists = result[0] > 0 if result else False
            
            if exists:
                logger.debug(f"Tabla '{schema}.{table_name}' validada exitosamente")
            else:
                logger.warning(f"Tabla '{schema}.{table_name}' no encontrada")
            
            return exists
            
        except Exception as e:
            logger.error(f"Error validando tabla '{schema}.{table_name}': {e}")
            return False
    
    @classmethod
    def detect_primary_key_field(cls, table_name: str, schema: str = None,
                                database_alias: str = 'default') -> Optional[str]:
        """
        Detecta automáticamente el campo ID principal de una tabla.
        
        Reglas de detección (en orden de prioridad):
        1. Buscar campo llamado 'id' (case insensitive)
        2. Buscar campo con is_primary = true
        3. Buscar campo llamado '{table_name}_id'
        4. Buscar campo de tipo integer/uniqueidentifier con is_identity = true
        5. Usar el primer campo de tipo integer/uniqueidentifier
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema de la tabla
            database_alias: Alias de la conexión de base de datos
            
        Returns:
            Nombre del campo ID detectado, o None si no se puede determinar
        """
        try:
            columns = cls.get_table_columns(table_name, schema, database_alias)
            
            if not columns:
                return None
            
            # 1. Buscar campo 'id' (case insensitive)
            for col in columns:
                if col['name'].lower() == 'id':
                    logger.debug(f"Campo ID detectado por nombre 'id': {col['name']}")
                    return col['name']
            
            # 2. Buscar campo con is_primary = true
            for col in columns:
                if col.get('is_primary', False) or col.get('is_primary_key', False):
                    logger.debug(f"Campo ID detectado por clave primaria: {col['name']}")
                    return col['name']
            
            # 3. Buscar campo llamado '{table_name}_id'
            table_id_field = f"{table_name.lower()}_id"
            for col in columns:
                if col['name'].lower() == table_id_field:
                    logger.debug(f"Campo ID detectado por patrón '{table_id_field}': {col['name']}")
                    return col['name']
            
            # 4. Buscar campo de tipo integer/uniqueidentifier con is_identity = true
            for col in columns:
                if col.get('is_identity', False) and col['type'] in ('int', 'integer', 'bigint', 'uniqueidentifier'):
                    logger.debug(f"Campo ID detectado por identidad: {col['name']}")
                    return col['name']
            
            # 5. Usar el primer campo de tipo integer/uniqueidentifier
            for col in columns:
                if col['type'] in ('int', 'integer', 'bigint', 'uniqueidentifier'):
                    logger.debug(f"Campo ID detectado por tipo numérico: {col['name']}")
                    return col['name']
            
            # 6. Si no hay, usar el primer campo
            logger.warning(f"No se pudo detectar campo ID claro para tabla '{table_name}', usando primera columna: {columns[0]['name']}")
            return columns[0]['name']
            
        except Exception as e:
            logger.error(f"Error detectando campo ID para tabla '{table_name}': {e}")
            return None
    
    @classmethod
    def analyze_table_schema(cls, table_name: str, schema: str = None,
                            database_alias: str = 'default') -> Dict[str, Any]:
        """
        Analiza y retorna estructura completa de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema de la tabla
            database_alias: Alias de la conexión de base de datos
            
        Returns:
            Diccionario con análisis completo de la tabla:
            {
                'table_name': 'propiedadraw',
                'schema': 'dbo',
                'exists': True,
                'columns': [...],  # Lista de columnas con metadatos
                'primary_key': 'id',  # Campo ID detectado
                'row_count': 1250,  # Número aproximado de filas
                'sample_data': [...]  # Datos de muestra (5 registros)
            }
        """
        if schema is None:
            schema = cls.DEFAULT_SCHEMA
        
        try:
            # Validar que la tabla existe
            if not cls.validate_table(table_name, schema, database_alias):
                return {
                    'table_name': table_name,
                    'schema': schema,
                    'exists': False,
                    'error': f"Tabla '{schema}.{table_name}' no encontrada"
                }
            
            # Obtener columnas
            columns = cls.get_table_columns(table_name, schema, database_alias)
            
            # Detectar campo ID principal
            primary_key = cls.detect_primary_key_field(table_name, schema, database_alias)
            
            # Obtener conteo aproximado de filas
            row_count = 0
            try:
                conn = cls._get_connection(database_alias)
                quoted_table = f"[{schema}].[{table_name}]" if '.' in table_name else f"[{table_name}]"
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) FROM {quoted_table}")
                    result = cursor.fetchone()
                    row_count = result[0] if result else 0
            except Exception as e:
                logger.warning(f"No se pudo obtener conteo de filas para '{table_name}': {e}")
            
            # Obtener datos de muestra
            sample_data = cls.get_sample_data(table_name, limit=5, schema=schema, database_alias=database_alias)
            
            # Construir field_definitions según SPEC-003
            field_definitions = {}
            for col in columns:
                field_definitions[col['name']] = {
                    'type': col['type'],
                    'nullable': col['nullable'],
                    'max_length': col['max_length'],
                    'is_primary': col.get('is_primary', False),
                    'is_identity': col.get('is_identity', False),
                    'default_value': col.get('default_value')
                }
            
            # Retornar análisis completo
            return {
                'table_name': table_name,
                'schema': schema,
                'exists': True,
                'columns': columns,
                'primary_key': primary_key,
                'row_count': row_count,
                'sample_data': sample_data,
                'field_definitions': field_definitions
            }
            
        except Exception as e:
            logger.error(f"Error analizando esquema de tabla '{schema}.{table_name}': {e}")
            return {
                'table_name': table_name,
                'schema': schema,
                'exists': False,
                'error': str(e)
            }