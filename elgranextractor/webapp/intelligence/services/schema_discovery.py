"""
schema_discovery.py - Descubrimiento y análisis de esquemas de bases de datos.

Proporciona servicios para:
- Listar tablas disponibles en una BD
- Obtener columnas, tipos, PKs
- Analizar y sugerir configuraciones para colecciones RAG
- Detectar foreign keys (declarativas e inferidas por naming)
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from django.db import connections
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SchemaDiscoveryService:
    """
    Servicio para descubrir y analizar esquemas de bases de datos.
    Soporta múltiples bases de datos configuradas en Django.
    """

    # Cache en memoria para evitar consultas repetitivas
    _tables_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
    _columns_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
    _cache_ttl = 300  # 5 minutos

    @classmethod
    def _get_cache_key(cls, prefix: str, *args) -> str:
        return f"{prefix}:" + ":".join(str(a) for a in args)

    @classmethod
    def _get_connection(cls, database_alias: str = 'default'):
        """
        Obtiene una conexión a la base de datos especificada.
        
        Args:
            database_alias: Alias de la BD en settings.DATABASES
            
        Returns:
            Conexión Django
            
        Raises:
            ValueError: Si el alias no existe
        """
        if database_alias not in settings.DATABASES:
            available = list(settings.DATABASES.keys())
            raise ValueError(
                f"Base de datos '{database_alias}' no configurada. "
                f"Disponibles: {available}"
            )
        return connections[database_alias]

    @classmethod
    def list_tables(cls, schema: str = None, database_alias: str = 'default', 
                    force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Lista todas las tablas disponibles en la base de datos.
        
        Args:
            schema: Esquema (default: 'dbo' para SQL Server)
            database_alias: Alias de conexión
            force_refresh: Si True, ignora cache
            
        Returns:
            Lista de dicts con información de cada tabla
        """
        import time
        
        cache_key = cls._get_cache_key('tables', database_alias, schema or 'dbo')
        
        if not force_refresh and cache_key in cls._tables_cache:
            cached_data, cached_time = cls._tables_cache[cache_key]
            if time.time() - cached_time < cls._cache_ttl:
                return cached_data

        tables = []
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            with conn.cursor() as cursor:
                # Obtener tablas del esquema
                cursor.execute("""
                    SELECT
                        TABLE_NAME,
                        TABLE_SCHEMA,
                        TABLE_TYPE
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_TYPE = 'BASE TABLE'
                      AND TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME
                """, (schema,))
                
                for row in cursor.fetchall():
                    table_name = row[0]
                    table_schema = row[1]
                    
                    # Obtener count de columnas
                    try:
                        cursor.execute("""
                            SELECT COUNT(*)
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
                        """, (table_name, table_schema))
                        col_count = cursor.fetchone()[0]
                    except Exception:
                        col_count = 0
                    
                    # Obtener count aproximado de filas
                    try:
                        cursor.execute(
                            f"SELECT COUNT(*) FROM [{table_schema}].[{table_name}]"
                        )
                        row_count = cursor.fetchone()[0]
                    except Exception:
                        row_count = 0
                    
                    tables.append({
                        'name': table_name,
                        'schema': table_schema,
                        'columns': col_count,
                        'rows': row_count,
                        'type': 'table'
                    })
            
            # Cachear resultados
            cls._tables_cache[cache_key] = (tables, time.time())
            
        except Exception as e:
            logger.error(f"Error listando tablas en '{database_alias}': {e}")
            raise
        
        return tables

    @classmethod
    def get_table_columns(cls, table_name: str, schema: str = None, 
                          database_alias: str = 'default') -> List[Dict[str, Any]]:
        """
        Obtiene las columnas de una tabla específica.
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema (default: 'dbo')
            database_alias: Alias de conexión
            
        Returns:
            Lista de dicts con info de cada columna
        """
        import time
        
        cache_key = cls._get_cache_key('columns', database_alias, schema or 'dbo', table_name)
        
        if cache_key in cls._columns_cache:
            cached_data, cached_time = cls._columns_cache[cache_key]
            if time.time() - cached_time < cls._cache_ttl:
                return cached_data

        columns = []
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        COLUMN_NAME,
                        DATA_TYPE,
                        CHARACTER_MAXIMUM_LENGTH,
                        IS_NULLABLE,
                        COLUMN_DEFAULT,
                        ORDINAL_POSITION
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
                    ORDER BY ORDINAL_POSITION
                """, (table_name, schema))
                
                for row in cursor.fetchall():
                    column_name = row[0]
                    data_type = row[1]
                    max_length = row[2]
                    is_nullable = row[3]
                    default_value = row[4]
                    
                    columns.append({
                        'name': column_name,
                        'column_name': column_name,
                        'type': data_type,
                        'data_type': data_type,
                        'max_length': max_length,
                        'nullable': is_nullable == 'YES',
                        'default': default_value,
                        'position': row[5]
                    })
            
            cls._columns_cache[cache_key] = (columns, time.time())
            
        except Exception as e:
            logger.error(f"Error obteniendo columnas de '{table_name}': {e}")
            raise
        
        return columns

    @classmethod
    def get_sample_data(cls, table_name: str, limit: int = 5, schema: str = None,
                        database_alias: str = 'default') -> List[Dict[str, Any]]:
        """
        Obtiene una muestra de datos de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            limit: Número máximo de filas
            schema: Esquema (default: 'dbo')
            database_alias: Alias de conexión
            
        Returns:
            Lista de dicts con datos de muestra
        """
        sample_data = []
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT TOP {limit} * FROM [{schema}].[{table_name}]"
                )
                columns = [desc[0] for desc in cursor.description]
                
                for row in cursor.fetchall():
                    row_dict = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        # Serializar tipos no estándar
                        if hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        elif isinstance(val, bytes):
                            val = val.decode('utf-8', errors='replace')[:200]
                        row_dict[col] = val
                    sample_data.append(row_dict)
                    
        except Exception as e:
            logger.error(f"Error obteniendo sample data de '{table_name}': {e}")
        
        return sample_data

    @classmethod
    def validate_table(cls, table_name: str, schema: str = None,
                       database_alias: str = 'default') -> bool:
        """
        Verifica si una tabla existe y es accesible.
        
        Returns:
            True si la tabla existe
        """
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
                """, (table_name, schema))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Error validando tabla '{table_name}': {e}")
            return False

    @classmethod
    def detect_primary_key_field(cls, table_name: str, schema: str = None,
                                 database_alias: str = 'default') -> Optional[str]:
        """
        Detecta el campo primary key de una tabla.
        
        Returns:
            Nombre de la columna PK o None
        """
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            with conn.cursor() as cursor:
                # Consultar PK desde INFORMATION_SCHEMA
                cursor.execute("""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsPrimaryKey') = 1
                      AND TABLE_NAME = %s AND TABLE_SCHEMA = %s
                """, (table_name, schema))
                
                row = cursor.fetchone()
                if row:
                    return row[0]
                
                # Fallback: buscar columna 'id'
                cursor.execute("""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s
                      AND LOWER(COLUMN_NAME) IN ('id', 'id_', f'{table_name}_id')
                """, (table_name, schema))
                row = cursor.fetchone()
                if row:
                    return row[0]
                    
        except Exception as e:
            logger.error(f"Error detectando PK en '{table_name}': {e}")
        
        return None

    @classmethod
    def analyze_table_schema(cls, table_name: str, schema: str = None,
                             database_alias: str = 'default') -> Dict[str, Any]:
        """
        Análisis completo del esquema de una tabla para configuración RAG.
        
        Returns:
            Dict con: columns, primary_key, field_analysis, suggestions, sample_data
        """
        result = {
            'table_name': table_name,
            'schema': schema or 'dbo',
            'database': database_alias,
            'columns': [],
            'primary_key': None,
            'field_analysis': {},
            'suggestions': {},
            'sample_data': [],
            'row_count': 0,
            'error': None
        }
        
        try:
            # Validar tabla
            if not cls.validate_table(table_name, schema, database_alias):
                result['error'] = f"La tabla '{table_name}' no existe en el esquema '{schema or 'dbo'}'"
                return result
            
            # Obtener columnas
            columns = cls.get_table_columns(table_name, schema, database_alias)
            result['columns'] = columns
            
            # Obtener row count
            conn = cls._get_connection(database_alias)
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) FROM [{schema or 'dbo'}].[{table_name}]"
                )
                result['row_count'] = cursor.fetchone()[0]
            
            # Detectar PK
            pk = cls.detect_primary_key_field(table_name, schema, database_alias)
            result['primary_key'] = pk
            
            # Obtener sample data
            sample_data = cls.get_sample_data(table_name, limit=5, schema=schema, database_alias=database_alias)
            result['sample_data'] = sample_data
            
            # Analizar tipos de campos
            field_analysis = cls._analyze_field_types(columns, sample_data)
            result['field_analysis'] = field_analysis
            
            # Generar sugerencias de configuración
            suggestions = cls._generate_configuration_suggestions(columns, field_analysis, pk)
            result['suggestions'] = suggestions
            
        except Exception as e:
            logger.error(f"Error analizando esquema de '{table_name}': {e}")
            result['error'] = str(e)
        
        return result

    @classmethod
    def _analyze_field_types(cls, columns: List[Dict[str, Any]], 
                             sample_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Analiza y categoriza los campos de una tabla para uso en RAG.
        
        Categorías:
        - text_content: Campos de texto largos ideales para embedding
        - identifier: IDs, códigos
        - categorical: Campos con valores limitados (estados, tipos)
        - numeric: Valores numéricos
        - date: Fechas
        - boolean: Flags
        - geographic: Direcciones, ubicaciones
        - foreign_key: IDs que referencian otras tablas
        
        Returns:
            Dict con análisis por campo
        """
        field_analysis = {}
        
        # Palabras clave para identificar categorías
        text_keywords = ['nombre', 'name', 'descripcion', 'description', 'titulo', 'title',
                        'detalle', 'detail', 'contenido', 'content', 'texto', 'text',
                        'observacion', 'observation', 'comentario', 'comment', 'nota', 'note',
                        'direccion', 'address', 'ubicacion', 'location', 'resumen', 'summary',
                        'caracteristica', 'feature', 'especificacion', 'specification']
        
        id_keywords = ['id', 'codigo', 'code', 'key', 'uuid', 'guid']
        
        categorical_keywords = ['tipo', 'type', 'estado', 'status', 'categoria', 'category',
                               'clase', 'class', 'grupo', 'group', 'nivel', 'level',
                               'condicion', 'condition', 'moneda', 'currency']
        
        geographic_keywords = ['direccion', 'address', 'ubicacion', 'location', 'distrito',
                              'district', 'ciudad', 'city', 'provincia', 'province',
                              'departamento', 'region', 'pais', 'country', 'zona', 'zone',
                              'latitud', 'latitude', 'longitud', 'longitude', 'coord']
        
        fk_keywords = ['_id', '_fk']
        
        for col in columns:
            col_name = col.get('name') or col.get('column_name', '')
            col_type = col.get('type') or col.get('data_type', '')
            col_name_lower = col_name.lower()
            
            analysis = {
                'name': col_name,
                'type': col_type,
                'category': 'unknown',
                'suggested_for_embedding': False,
                'suggested_for_display': False,
                'suggested_for_filtering': False,
                'serialization_safe': True,
                'notes': ''
            }
            
            # Detectar tipo por nombre y tipo de dato
            is_fk = any(kw in col_name_lower for kw in fk_keywords)
            
            # --- Identificar categoría ---
            if col_type in ('int', 'bigint', 'smallint', 'tinyint') and (
                col_name_lower == 'id' or col_name_lower.endswith('_id')):
                if is_fk:
                    analysis['category'] = 'foreign_key'
                    analysis['suggested_for_filtering'] = True
                    analysis['notes'] = 'Foreign key (requiere JOIN para texto completo)'
                else:
                    analysis['category'] = 'identifier'
                    analysis['notes'] = 'Identificador numérico'
            
            elif col_type in ('uniqueidentifier', 'uuid'):
                analysis['category'] = 'identifier'
                analysis['notes'] = 'Identificador único'
            
            elif any(kw in col_name_lower for kw in id_keywords):
                analysis['category'] = 'identifier'
                analysis['notes'] = 'Campo identificador'
            
            elif col_type in ('text', 'ntext', 'varchar', 'nvarchar', 'char', 'nchar'):
                max_len = col.get('max_length') or 0
                
                # Texto largo -> embedding
                if max_len > 200 or max_len == -1 or max_len == 0:
                    if any(kw in col_name_lower for kw in text_keywords):
                        analysis['category'] = 'text_content'
                        analysis['suggested_for_embedding'] = True
                        analysis['suggested_for_display'] = True
                        analysis['notes'] = 'Texto largo ideal para embedding'
                    elif any(kw in col_name_lower for kw in categorical_keywords):
                        analysis['category'] = 'categorical'
                        analysis['suggested_for_filtering'] = True
                        analysis['notes'] = 'Campo categórico'
                    elif any(kw in col_name_lower for kw in geographic_keywords):
                        analysis['category'] = 'geographic'
                        analysis['suggested_for_embedding'] = True
                        analysis['suggested_for_display'] = True
                        analysis['suggested_for_filtering'] = True
                        analysis['notes'] = 'Información geográfica'
                    else:
                        analysis['category'] = 'text_content'
                        analysis['suggested_for_embedding'] = True
                        analysis['suggested_for_display'] = True
                        analysis['notes'] = 'Campo de texto'
                else:
                    # Texto corto
                    if any(kw in col_name_lower for kw in categorical_keywords):
                        analysis['category'] = 'categorical'
                        analysis['suggested_for_filtering'] = True
                        analysis['suggested_for_display'] = True
                        analysis['notes'] = 'Campo categórico'
                    elif any(kw in col_name_lower for kw in geographic_keywords):
                        analysis['category'] = 'geographic'
                        analysis['suggested_for_embedding'] = True
                        analysis['suggested_for_display'] = True
                        analysis['suggested_for_filtering'] = True
                        analysis['notes'] = 'Información geográfica'
                    elif any(kw in col_name_lower for kw in text_keywords):
                        analysis['category'] = 'text_content'
                        analysis['suggested_for_embedding'] = True
                        analysis['suggested_for_display'] = True
                        analysis['notes'] = 'Texto informativo'
                    else:
                        analysis['category'] = 'categorical'
                        analysis['suggested_for_display'] = True
                        analysis['notes'] = 'Valor corto'
            
            elif col_type in ('decimal', 'numeric', 'float', 'real', 'money', 'smallmoney'):
                analysis['category'] = 'numeric'
                analysis['suggested_for_display'] = True
                analysis['suggested_for_filtering'] = True
                analysis['notes'] = 'Valor numérico'
            
            elif col_type in ('int', 'bigint', 'smallint', 'tinyint'):
                if is_fk:
                    analysis['category'] = 'foreign_key'
                    analysis['notes'] = 'Foreign key (requiere JOIN para texto completo)'
                else:
                    analysis['category'] = 'numeric'
                    analysis['suggested_for_filtering'] = True
                    analysis['notes'] = 'Valor numérico entero'
            
            elif col_type in ('datetime', 'datetime2', 'date', 'smalldatetime', 'timestamp'):
                analysis['category'] = 'date'
                analysis['suggested_for_filtering'] = True
                analysis['suggested_for_display'] = True
                analysis['notes'] = 'Campo de fecha'
            
            elif col_type in ('bit', 'boolean'):
                analysis['category'] = 'boolean'
                analysis['suggested_for_filtering'] = True
                analysis['notes'] = 'Valor booleano'
            
            elif col_type in ('geometry', 'geography'):
                analysis['category'] = 'geographic'
                analysis['serialization_safe'] = False
                analysis['notes'] = 'Dato espacial (requiere serialización)'
            
            elif col_type in ('image', 'binary', 'varbinary', 'filestream'):
                analysis['category'] = 'binary'
                analysis['serialization_safe'] = False
                analysis['suggested_for_embedding'] = False
                analysis['suggested_for_display'] = False
                analysis['notes'] = 'Dato binario (no serializable directamente)'
            
            else:
                analysis['category'] = 'other'
                analysis['notes'] = f'Tipo no clasificado: {col_type}'
            
            field_analysis[col_name] = analysis
        
        return field_analysis

    @classmethod
    def _generate_configuration_suggestions(cls, columns: List[Dict[str, Any]],
                                            field_analysis: Dict[str, Dict[str, Any]],
                                            primary_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera sugerencias de configuración para una colección RAG.
        
        Returns:
            Dict con: embedding_fields, display_fields, filter_fields, 
                     configuration_summary, validation_warnings
        """
        suggestions = {
            'embedding_fields': [],
            'display_fields': [],
            'filter_fields': [],
            'configuration_summary': '',
            'validation_warnings': []
        }
        
        # 1. Campos para embedding (priorizar texto)
        for field_name, analysis in field_analysis.items():
            if analysis['suggested_for_embedding'] and analysis['serialization_safe']:
                suggestions['embedding_fields'].append(field_name)
        
        # Si no hay campos sugeridos para embedding, tomar los primeros campos de texto
        if not suggestions['embedding_fields']:
            for field_name, analysis in field_analysis.items():
                if analysis['category'] in ('text_content', 'geographic') and analysis['serialization_safe']:
                    suggestions['embedding_fields'].append(field_name)
                    if len(suggestions['embedding_fields']) >= 3:
                        break
        
        # Si sigue sin haber, warning
        if not suggestions['embedding_fields']:
            for field_name, analysis in field_analysis.items():
                if analysis['category'] not in ('binary', 'identifier', 'date') and analysis['serialization_safe']:
                    suggestions['embedding_fields'].append(field_name)
                    if len(suggestions['embedding_fields']) >= 2:
                        break
            if suggestions['embedding_fields']:
                suggestions['validation_warnings'].append(
                    "No se encontraron campos de texto ideales para embedding. "
                    "Se usaron campos numéricos como alternativa."
                )
            else:
                suggestions['validation_warnings'].append(
                    "ADVERTENCIA: No se detectaron campos adecuados para embedding. "
                    "La búsqueda semántica puede no funcionar bien."
                )
        
        # 2. Campos para visualización
        if primary_key and primary_key in field_analysis:
            suggestions['display_fields'].append(primary_key)
        
        for field_name, analysis in field_analysis.items():
            if analysis['suggested_for_display'] and field_name not in suggestions['display_fields']:
                suggestions['display_fields'].append(field_name)
        
        # Limitar a 8
        if len(suggestions['display_fields']) > 8:
            suggestions['display_fields'] = suggestions['display_fields'][:8]
            suggestions['validation_warnings'].append(
                "Campos de visualización limitados a 8"
            )
        
        # 3. Campos para filtrado
        for field_name, analysis in field_analysis.items():
            if analysis['suggested_for_filtering']:
                suggestions['filter_fields'].append(field_name)
        
        # 4. Validaciones
        for field_name, analysis in field_analysis.items():
            if not analysis['serialization_safe']:
                suggestions['validation_warnings'].append(
                    f"Campo '{field_name}' ({analysis['category']}) "
                    f"puede requerir serialización especial"
                )
        
        # 5. Resumen
        summary_parts = []
        if suggestions['embedding_fields']:
            summary_parts.append(f"{len(suggestions['embedding_fields'])} campos para embedding")
        if suggestions['display_fields']:
            summary_parts.append(f"{len(suggestions['display_fields'])} campos para visualización")
        if suggestions['filter_fields']:
            summary_parts.append(f"{len(suggestions['filter_fields'])} campos para filtrado")
        
        suggestions['configuration_summary'] = "Configuración sugerida: " + ", ".join(summary_parts)
        
        return suggestions

    @classmethod
    def _get_columns_flexible(cls, table_name: str, schema: str = None,
                              preferred_alias: str = 'default',
                              fallback_aliases: List[str] = None) -> Tuple[List[Dict[str, Any]], str]:
        """
        Obtiene columnas de una tabla intentando en múltiples BDs.
        
        Primero intenta en preferred_alias, luego en cada fallback_aliases.
        Retorna (columns, database_alias_donde_se_encontró).
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema (default: 'dbo')
            preferred_alias: Alias preferido de conexión
            fallback_aliases: Lista de aliases alternativos si no se encuentra
            
        Returns:
            Tuple de (lista de columnas, alias donde se encontró)
        """
        schema = schema or 'dbo'
        fallback_aliases = fallback_aliases or []
        
        # Intentar en el alias preferido primero
        aliases_to_try = [preferred_alias] + [a for a in fallback_aliases if a != preferred_alias]
        
        for alias in aliases_to_try:
            try:
                columns = cls.get_table_columns(table_name, schema=schema, database_alias=alias)
                if columns:
                    return columns, alias
            except Exception:
                continue
        
        # Si no se encontró en ningún lado, intentar con el preferido (para obtener el error original)
        return cls.get_table_columns(table_name, schema=schema, database_alias=preferred_alias), preferred_alias

    @classmethod
    def detect_foreign_keys(cls, table_name: str, schema: str = None,
                            database_alias: str = 'default') -> List[Dict[str, Any]]:
        """
        Detecta foreign keys de una tabla.
        
        Estrategia:
        1. Consulta INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS (FK declarativas)
        2. Si no encuentra, infiere FK candidates desde columnas que terminan en '_id' o contienen '_fk'
        3. Para cada candidate, intenta adivinar la tabla referenciada
        
        Es flexible: si la tabla no existe en database_alias, intenta en otras BDs
        (ej. 'default') para obtener las columnas, pero busca las tablas referenciadas
        en la BD original (database_alias).
        
        Args:
            table_name: Nombre de la tabla
            schema: Esquema (default: 'dbo')
            database_alias: Alias de conexión
            
        Returns:
            Lista de dicts con: column, referenced_table, referenced_column,
            referenced_columns, is_inferred (True si se infirió por naming)
        """
        foreign_keys = []
        
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            # --- ESTRATEGIA 1: FK declarativas desde INFORMATION_SCHEMA ---
            fk_query = """
                SELECT
                    KCU1.COLUMN_NAME AS FK_COLUMN,
                    KCU2.TABLE_NAME AS REFERENCED_TABLE,
                    KCU2.COLUMN_NAME AS REFERENCED_COLUMN,
                    KCU2.TABLE_SCHEMA AS REFERENCED_SCHEMA
                FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS RC
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU1
                    ON RC.CONSTRAINT_NAME = KCU1.CONSTRAINT_NAME
                    AND KCU1.TABLE_NAME = %s AND KCU1.TABLE_SCHEMA = %s
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU2
                    ON RC.UNIQUE_CONSTRAINT_NAME = KCU2.CONSTRAINT_NAME
            """
            
            with conn.cursor() as cursor:
                cursor.execute(fk_query, (table_name, schema))
                fk_rows = cursor.fetchall()
                
                for row in fk_rows:
                    fk_column = row[0]
                    ref_table = row[1]
                    ref_column = row[2]
                    ref_schema = row[3]
                    
                    ref_columns = cls.get_table_columns(ref_table, schema=ref_schema, database_alias=database_alias)
                    
                    foreign_keys.append({
                        'column': fk_column,
                        'referenced_table': ref_table,
                        'referenced_column': ref_column,
                        'referenced_schema': ref_schema,
                        'is_inferred': False,
                        'referenced_columns': [
                            {
                                'name': col.get('name') or col.get('column_name', ''),
                                'type': col.get('type') or col.get('data_type', ''),
                                'max_length': col.get('max_length'),
                                'nullable': col.get('nullable', True)
                            }
                            for col in ref_columns
                        ]
                    })
            
            # --- ESTRATEGIA 2: Inferir FK desde naming de columnas ---
            # Obtener columnas de forma flexible: intenta en database_alias,
            # si no encuentra, prueba en 'default' (para tablas Django como propifai_propiedad)
            all_columns, _ = cls._get_columns_flexible(
                table_name, schema=schema,
                preferred_alias=database_alias,
                fallback_aliases=['default']
            )
            declared_fk_columns = {fk['column'] for fk in foreign_keys}
            
            # Patrones de columnas que parecen FK
            fk_pattern = re.compile(r'^(.+?)(?:_fk_?|_id)$', re.IGNORECASE)
            
            # Columnas que definitivamente NO son FK aunque terminen en _id
            skip_columns = {
                'id', 'row_id', 'rowversion', 'created_at', 'updated_at',
                'created_by', 'updated_by', 'modified_at', 'modified_by',
                'deleted_at', 'deleted_by', 'version_id', 'batch_id',
                'session_id', 'transaction_id', 'request_id'
            }
            
            inferred_candidates = []
            for col in all_columns:
                col_name = col.get('name') or col.get('column_name', '')
                col_name_lower = col_name.lower()
                
                # Saltar si ya es FK declarativa
                if col_name in declared_fk_columns:
                    continue
                
                # Saltar columnas que claramente NO son FK
                if col_name_lower in skip_columns:
                    continue
                
                # Saltar columnas que son PK (se llaman 'id' a secas)
                if col_name_lower == 'id':
                    continue
                
                match = fk_pattern.match(col_name)
                if match:
                    base_name = match.group(1)
                    guessed_table = cls._guess_referenced_table(base_name, conn, schema)
                    
                    inferred_candidates.append({
                        'column': col_name,
                        'data_type': col.get('type') or col.get('data_type', ''),
                        'nullable': col.get('nullable', True),
                        'guessed_table': guessed_table,
                        'base_name': base_name
                    })
            
            # Para cada candidate inferido, obtener columnas de la tabla adivinada
            for cand in inferred_candidates:
                ref_table = cand['guessed_table']
                ref_columns = []
                
                if ref_table:
                    try:
                        ref_columns = cls.get_table_columns(ref_table, schema=schema, database_alias=database_alias)
                    except Exception:
                        ref_columns = []
                
                foreign_keys.append({
                    'column': cand['column'],
                    'referenced_table': ref_table or f"??_{cand['base_name']}",
                    'referenced_column': 'id',
                    'referenced_schema': schema,
                    'is_inferred': True,
                    'data_type': cand['data_type'],
                    'nullable': cand['nullable'],
                    'referenced_columns': [
                        {
                            'name': col.get('name') or col.get('column_name', ''),
                            'type': col.get('type') or col.get('data_type', ''),
                            'max_length': col.get('max_length'),
                            'nullable': col.get('nullable', True)
                        }
                        for col in ref_columns
                    ]
                })
            
            logger.info(
                f"FK detectadas en {table_name}: {len(foreign_keys)} "
                f"({sum(1 for f in foreign_keys if not f.get('is_inferred'))} declarativas, "
                f"{sum(1 for f in foreign_keys if f.get('is_inferred'))} inferidas)"
            )
            
        except Exception as e:
            logger.error(f"Error detectando foreign keys en '{table_name}': {e}")
        
        return foreign_keys

    @classmethod
    def _guess_referenced_table(cls, base_name: str, conn, schema: str = 'dbo') -> Optional[str]:
        """
        Intenta adivinar el nombre de la tabla referenciada a partir del nombre base
        de una columna FK.
        
        Ejemplos:
            'district_fk' -> 'districts', 'district'
            'assigned_agent' -> 'agents', 'agent'
            'property_type' -> 'property_types', 'property_type'
        """
        base_lower = base_name.lower().strip()
        
        # Mapa de nombres conocidos para el dominio inmobiliario
        known_mappings = {
            'district': ['districts', 'district'],
            'city': ['cities', 'city'],
            'country': ['countries', 'country'],
            'property_type': ['property_types', 'property_type'],
            'property': ['properties', 'property'],
            'agent': ['agents', 'agent', 'users'],
            'assigned_agent': ['agents', 'agent', 'users'],
            'user': ['users', 'user'],
            'client': ['clients', 'client', 'customers', 'customer'],
            'owner': ['owners', 'owner'],
            'status': ['status', 'property_status'],
            'currency': ['currencies', 'currency'],
            'zone': ['zones', 'zone', 'cuadrantizacion_zonavalor'],
            'cuadrante': ['cuadrantizacion_zonavalor', 'zones', 'zone'],
            'category': ['categories', 'category'],
            'brand': ['brands', 'brand'],
            'supplier': ['suppliers', 'supplier', 'providers', 'provider'],
        }
        
        if base_lower in known_mappings:
            candidates = known_mappings[base_lower]
        else:
            # Generar candidatos: pluralizar
            if base_lower.endswith('y'):
                candidates = [base_lower[:-1] + 'ies', base_lower + 's']
            elif base_lower.endswith('s'):
                candidates = [base_lower, base_lower[:-1]]
            elif base_lower.endswith('ss'):
                candidates = [base_lower + 'es', base_lower]
            else:
                candidates = [base_lower + 's', base_lower + 'es', base_lower]
        
        # Buscar en la BD
        for candidate in candidates:
            try:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                        "WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s",
                        (candidate, schema)
                    )
                    if c.fetchone():
                        return candidate
            except Exception:
                pass
        
        # Si no se encontró exacto, buscar LIKE
        # NOTA: Usar CONCAT para evitar que pyodbc interprete % en el parámetro
        try:
            with conn.cursor() as c:
                c.execute(
                    "SELECT TOP 5 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE CONCAT('%%', %s, '%%')",
                    (schema, base_lower)
                )
                matches = [row[0] for row in c.fetchall()]
                if matches:
                    return matches[0]
        except Exception:
            pass
        
        return None

    @classmethod
    def get_available_tables_for_relationships(cls, database_alias: str = 'default', 
                                                schema: str = None) -> List[Dict[str, Any]]:
        """
        Obtiene lista de tablas disponibles para construir relaciones manuales.
        Util para el frontend cuando el usuario quiere mapear FK manualmente.
        
        Returns:
            Lista de dicts con: table_name, schema, column_count, columns
        """
        tables = []
        try:
            conn = cls._get_connection(database_alias)
            schema = schema or 'dbo'
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT TABLE_NAME, TABLE_SCHEMA
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_TYPE = 'BASE TABLE'
                      AND TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME
                """, (schema,))
                
                for row in cursor.fetchall():
                    table_name = row[0]
                    table_schema = row[1]
                    
                    try:
                        columns = cls.get_table_columns(table_name, schema=table_schema, database_alias=database_alias)
                    except Exception:
                        columns = []
                    
                    tables.append({
                        'table_name': table_name,
                        'schema': table_schema,
                        'column_count': len(columns),
                        'columns': [
                            {
                                'name': col.get('name') or col.get('column_name', ''),
                                'type': col.get('type') or col.get('data_type', ''),
                            }
                            for col in columns
                        ]
                    })
            
        except Exception as e:
            logger.error(f"Error obteniendo tablas disponibles para relaciones: {e}")
        
        return tables