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
    def list_tables(cls, schema: str = None, database_alias: str = 'default', force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Lista todas las tablas disponibles en Azure SQL con metadatos.
        
        Args:
            schema: Esquema a consultar (default: 'dbo' o valor de RAG_DEFAULT_SCHEMA)
            database_alias: Alias de la conexión de base de datos
            force_refresh: Si True, ignora la caché y vuelve a consultar la base de datos
            
        Returns:
            Lista de diccionarios con información de tablas:
            [
                {
                    'name': 'nombre_tabla',
                    'schema': 'dbo',
                    'type': 'BASE TABLE',
                    'row_count': 1234
                },
                ...
            ]
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
            
            # Obtener solo tablas (no vistas)
            table_names = [row[1] for row in results if row[2] == 'BASE TABLE']
            
            # Limitar si es necesario
            if cls.MAX_TABLES_TO_DISCOVER > 0 and len(table_names) > cls.MAX_TABLES_TO_DISCOVER:
                table_names = table_names[:cls.MAX_TABLES_TO_DISCOVER]
                logger.warning(f"Limitando tablas a {cls.MAX_TABLES_TO_DISCOVER} de {len(results)} totales")
            
            # Obtener conteos de filas para cada tabla
            tables_with_metadata = []
            for table_name in table_names:
                try:
                    # Consulta para obtener conteo de filas
                    count_sql = f"SELECT COUNT(*) FROM [{schema}].[{table_name}]"
                    with conn.cursor() as cursor:
                        cursor.execute(count_sql)
                        row_count = cursor.fetchone()[0]
                except Exception as count_error:
                    logger.warning(f"No se pudo obtener conteo de filas para tabla {table_name}: {count_error}")
                    row_count = None
                
                tables_with_metadata.append({
                    'name': table_name,
                    'schema': schema,
                    'type': 'BASE TABLE',
                    'row_count': row_count
                })
            
            # Actualizar cache
            if cls._tables_cache is None:
                cls._tables_cache = {}
            cls._tables_cache[cache_key] = tables_with_metadata
            import time
            cls._tables_cache_timestamp = time.time()
            
            logger.info(f"Descubiertas {len(tables_with_metadata)} tablas en esquema '{schema}'")
            return tables_with_metadata
            
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
        Analiza y retorna estructura completa de una tabla con sugerencias inteligentes.
        
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
                'field_definitions': {...},
                'field_analysis': {...},  # Análisis inteligente de campos
                'suggestions': {...}      # Sugerencias de configuración
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
            
            # Análisis inteligente de campos
            field_analysis = cls._analyze_field_types(columns, sample_data)
            
            # Generar sugerencias de configuración
            suggestions = cls._generate_configuration_suggestions(columns, field_analysis, primary_key)
            
            # Retornar análisis completo
            return {
                'table_name': table_name,
                'schema': schema,
                'exists': True,
                'columns': columns,
                'primary_key': primary_key,
                'row_count': row_count,
                'sample_data': sample_data,
                'field_definitions': field_definitions,
                'field_analysis': field_analysis,
                'suggestions': suggestions
            }
            
        except Exception as e:
            logger.error(f"Error analizando esquema de tabla '{schema}.{table_name}': {e}")
            return {
                'table_name': table_name,
                'schema': schema,
                'exists': False,
                'error': str(e)
            }
    
    @classmethod
    def _analyze_field_types(cls, columns: List[Dict[str, Any]], sample_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Analiza tipos de campo y determina categorías para sugerencias.
        
        Args:
            columns: Lista de columnas con metadatos
            sample_data: Datos de muestra para análisis adicional
            
        Returns:
            Diccionario con análisis por campo:
            {
                'field_name': {
                    'category': 'text'|'numeric'|'date'|'boolean'|'identifier'|'categorical',
                    'suggested_for_embedding': True|False,
                    'suggested_for_display': True|False,
                    'suggested_for_filtering': True|False,
                    'serialization_safe': True|False,
                    'notes': 'Notas sobre el tipo de campo'
                }
            }
        """
        field_analysis = {}
        
        for col in columns:
            field_name = col['name']
            field_type = col['type'].lower()
            is_primary = col.get('is_primary', False)
            is_identity = col.get('is_identity', False)
            max_length = col.get('max_length')
            
            # Determinar categoría del campo
            category = 'other'
            suggested_for_embedding = False
            suggested_for_display = False
            suggested_for_filtering = False
            serialization_safe = True
            notes = []
            
            # Análisis basado en tipo de campo
            if any(text_type in field_type for text_type in ['char', 'varchar', 'text', 'nchar', 'nvarchar', 'ntext']):
                category = 'text'
                suggested_for_embedding = max_length and max_length >= 50  # Texto largo para embedding
                suggested_for_display = True
                suggested_for_filtering = max_length and max_length <= 100  # Texto corto para filtrado
                notes.append(f"Campo de texto (max_length: {max_length})")
                
            elif any(num_type in field_type for num_type in ['int', 'bigint', 'smallint', 'tinyint', 'decimal', 'numeric', 'float', 'real', 'money']):
                category = 'numeric'
                suggested_for_display = True
                suggested_for_filtering = True
                # Decimal/numeric pueden tener problemas de serialización
                if 'decimal' in field_type or 'numeric' in field_type:
                    serialization_safe = False
                    notes.append("Decimal - requiere serialización especial")
                else:
                    notes.append(f"Campo numérico ({field_type})")
                    
            elif any(date_type in field_type for date_type in ['date', 'datetime', 'datetime2', 'smalldatetime', 'time', 'timestamp']):
                category = 'date'
                suggested_for_display = True
                suggested_for_filtering = True
                notes.append(f"Campo de fecha/hora ({field_type})")
                
            elif any(bool_type in field_type for bool_type in ['bit', 'boolean']):
                category = 'boolean'
                suggested_for_filtering = True
                suggested_for_display = True
                notes.append("Campo booleano")
                
            elif 'uniqueidentifier' in field_type or 'guid' in field_type:
                category = 'identifier'
                suggested_for_display = False
                suggested_for_filtering = False
                notes.append("Identificador único (GUID)")
                
            # Campos ID especiales
            if is_primary or is_identity or field_name.lower() in ['id', 'id_', '_id']:
                category = 'identifier'
                suggested_for_embedding = False
                suggested_for_display = True  # Mostrar ID en resultados
                suggested_for_filtering = False
                notes.append("Campo identificador principal")
            
            # Análisis adicional basado en nombre del campo
            field_name_lower = field_name.lower()
            if any(name_part in field_name_lower for name_part in ['nombre', 'descripcion', 'titulo', 'texto', 'comentario', 'observacion']):
                if category != 'text':
                    category = 'text'
                suggested_for_embedding = True
                notes.append("Nombre sugiere contenido textual")
                
            elif any(name_part in field_name_lower for name_part in ['precio', 'valor', 'monto', 'costo', 'importe']):
                if category != 'numeric':
                    category = 'numeric'
                suggested_for_display = True
                notes.append("Nombre sugiere valor monetario")
                
            elif any(name_part in field_name_lower for name_part in ['fecha', 'fec_', '_fecha', 'created', 'updated', 'timestamp']):
                if category != 'date':
                    category = 'date'
                suggested_for_display = True
                notes.append("Nombre sugiere fecha")
            
            # Análisis de datos de muestra para campos categóricos
            if sample_data and len(sample_data) > 0:
                unique_values = set()
                for row in sample_data:
                    if field_name in row:
                        value = row[field_name]
                        if value is not None:
                            unique_values.add(str(value))
                
                if 1 < len(unique_values) <= 10:  # Entre 2 y 10 valores únicos
                    suggested_for_filtering = True
                    notes.append(f"Valores categóricos detectados ({len(unique_values)} valores únicos en muestra)")
            
            field_analysis[field_name] = {
                'category': category,
                'suggested_for_embedding': suggested_for_embedding,
                'suggested_for_display': suggested_for_display,
                'suggested_for_filtering': suggested_for_filtering,
                'serialization_safe': serialization_safe,
                'notes': '; '.join(notes) if notes else 'Sin notas especiales'
            }
        
        return field_analysis
    
    @classmethod
    def _generate_configuration_suggestions(cls, columns: List[Dict[str, Any]],
                                          field_analysis: Dict[str, Dict[str, Any]],
                                          primary_key: str) -> Dict[str, Any]:
        """
        Genera sugerencias de configuración automática para RAG.
        
        Args:
            columns: Lista de columnas
            field_analysis: Análisis de campos
            primary_key: Campo ID principal
            
        Returns:
            Diccionario con sugerencias:
            {
                'embedding_fields': ['field1', 'field2'],
                'display_fields': ['field1', 'field3', 'field4'],
                'filter_fields': ['field5', 'field6'],
                'validation_warnings': ['warning1', 'warning2'],
                'configuration_summary': 'Resumen de configuración'
            }
        """
        suggestions = {
            'embedding_fields': [],
            'display_fields': [],
            'filter_fields': [],
            'validation_warnings': [],
            'configuration_summary': ''
        }
        
        # 1. Campos para embedding (búsqueda semántica)
        for field_name, analysis in field_analysis.items():
            if analysis['suggested_for_embedding']:
                suggestions['embedding_fields'].append(field_name)
        
        # Si no hay campos sugeridos para embedding, buscar alternativas
        if not suggestions['embedding_fields']:
            for field_name, analysis in field_analysis.items():
                if analysis['category'] == 'text' and field_name != primary_key:
                    suggestions['embedding_fields'].append(field_name)
                    suggestions['validation_warnings'].append(
                        f"Campo '{field_name}' seleccionado para embedding por falta de mejores opciones"
                    )
                    break
        
        # 2. Campos para visualización (incluir ID y campos informativos)
        if primary_key and primary_key in field_analysis:
            suggestions['display_fields'].append(primary_key)
        
        for field_name, analysis in field_analysis.items():
            if analysis['suggested_for_display'] and field_name not in suggestions['display_fields']:
                suggestions['display_fields'].append(field_name)
        
        # Limitar campos de visualización a un máximo razonable
        if len(suggestions['display_fields']) > 8:
            suggestions['display_fields'] = suggestions['display_fields'][:8]
            suggestions['validation_warnings'].append(
                f"Limitados campos de visualización a 8 de {len(field_analysis)} totales"
            )
        
        # 3. Campos para filtrado
        for field_name, analysis in field_analysis.items():
            if analysis['suggested_for_filtering']:
                suggestions['filter_fields'].append(field_name)
        
        # 4. Validaciones y advertencias
        for field_name, analysis in field_analysis.items():
            if not analysis['serialization_safe']:
                suggestions['validation_warnings'].append(
                    f"Campo '{field_name}' ({analysis['category']}) puede requerir serialización especial"
                )
        
        if not suggestions['embedding_fields']:
            suggestions['validation_warnings'].append(
                "ADVERTENCIA: No se detectaron campos adecuados para embedding. La búsqueda semántica puede no funcionar bien."
            )
        
        # 5. Resumen de configuración
        summary_parts = []
        if suggestions['embedding_fields']:
            summary_parts.append(f"{len(suggestions['embedding_fields'])} campos para embedding")
        if suggestions['display_fields']:
            summary_parts.append(f"{len(suggestions['display_fields'])} campos para visualización")
        if suggestions['filter_fields']:
            summary_parts.append(f"{len(suggestions['filter_fields'])} campos para filtrado")
        
        suggestions['configuration_summary'] = "Configuración sugerida: " + ", ".join(summary_parts)
        
        return suggestions