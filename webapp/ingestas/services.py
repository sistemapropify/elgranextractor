import re
import pandas as pd
import sys
from django.db import connection
from django.contrib.auth.models import User
from .models import CampoDinamico, MigracionPendiente


class SugeridorCampos:
    """Clase para analizar columnas de Excel y sugerir nombres y tipos."""

    @staticmethod
    def convertir_a_snake_case(texto):
        """Convierte un texto a snake_case."""
        import unicodedata
        # Normalizar texto: eliminar acentos y caracteres diacríticos
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join([c for c in texto if not unicodedata.combining(c)])
        # Reemplazar espacios y caracteres especiales por guiones bajos
        texto = re.sub(r'[^\w\s]', '', texto)
        texto = re.sub(r'\s+', '_', texto.strip())
        texto = texto.lower()
        return texto

    @staticmethod
    def inferir_tipo_dato(valores_muestra):
        """Infiere el tipo de dato a partir de una muestra de valores."""
        import pandas as pd
        if not valores_muestra:
            return 'VARCHAR'
        
        # Intentar detectar tipos
        enteros = 0
        decimales = 0
        fechas = 0
        booleanos = 0
        
        for val in valores_muestra:
            if pd.isna(val):
                continue
            # Booleanos
            if str(val).lower() in ('true', 'false', 'si', 'no', '1', '0', 'sí'):
                booleanos += 1
            # Fechas (patrones simples)
            if isinstance(val, pd.Timestamp) or isinstance(val, str) and re.match(r'\d{4}-\d{2}-\d{2}', str(val)):
                fechas += 1
            # Números
            try:
                float_val = float(val)
                if float_val.is_integer():
                    enteros += 1
                else:
                    decimales += 1
            except (ValueError, TypeError):
                pass
        
        total = len([v for v in valores_muestra if not pd.isna(v)])
        if total == 0:
            return 'VARCHAR'
        
        # Decidir por mayoría
        if booleanos / total > 0.8:
            return 'BOOLEAN'
        elif fechas / total > 0.7:
            return 'DATE'
        elif enteros / total > 0.8:
            return 'INTEGER'
        elif decimales / total > 0.7:
            return 'DECIMAL'
        else:
            return 'VARCHAR'

    @staticmethod
    def analizar_columna(nombre_columna, valores_muestra):
        """Retorna dict con sugerencias para una columna."""
        nombre_sugerido_bd = SugeridorCampos.convertir_a_snake_case(nombre_columna)
        titulo_sugerido_display = nombre_columna.title()
        tipo_sugerido = SugeridorCampos.inferir_tipo_dato(valores_muestra)
        
        # Buscar campos existentes similares
        similares_existentes = []
        campos_existentes = CampoDinamico.objects.filter(
            nombre_campo_bd__icontains=nombre_sugerido_bd[:10]
        )[:5]
        for campo in campos_existentes:
            similares_existentes.append({
                'nombre_campo_bd': campo.nombre_campo_bd,
                'titulo_display': campo.titulo_display,
                'tipo_dato': campo.tipo_dato,
            })
        
        return {
            'nombre_sugerido_bd': nombre_sugerido_bd,
            'titulo_sugerido_display': titulo_sugerido_display,
            'tipo_sugerido': tipo_sugerido,
            'similares_existentes': similares_existentes,
        }


class EjecutorMigraciones:
    """Clase para ejecutar migraciones de campos dinámicos en la base de datos."""

    @staticmethod
    def validar_nombre_snake_case(nombre):
        """Valida que el nombre esté en snake_case."""
        if not re.match(r'^[a-z][a-z0-9_]*$', nombre):
            raise ValueError(f"El nombre '{nombre}' no está en snake_case válido. Solo letras minúsculas, números y guiones bajos.")
        return True

    @staticmethod
    def mapear_tipo_django(tipo_dato):
        """Mapea tipo de dato a tipo de columna SQL según el backend."""
        tipo_dato = tipo_dato.upper()
        # Mapeo para SQL Server
        mapping = {
            'VARCHAR': 'VARCHAR(255)',
            'INTEGER': 'INT',
            'DECIMAL': 'DECIMAL(15,2)',
            'BOOLEAN': 'BIT',
            'DATE': 'DATE',
            'DATETIME': 'DATETIME2',
        }
        return mapping.get(tipo_dato, 'VARCHAR(255)')

    @staticmethod
    def columna_existe_en_tabla(nombre_campo_bd, tabla='dbo.ingestas_propiedadraw'):
        """Verifica si una columna ya existe en la tabla física."""
        from django.db import connection
        esquema, nombre_tabla = tabla.split('.') if '.' in tabla else ('dbo', tabla)
        with connection.cursor() as cursor:
            check_sql = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """
            cursor.execute(check_sql, [esquema, nombre_tabla, nombre_campo_bd])
            return cursor.fetchone() is not None

    @staticmethod
    def ejecutar_migracion(nombre_campo_bd, titulo_display, tipo_dato, user):
        """
        Ejecuta ALTER TABLE ADD COLUMN y crea registro en CampoDinamico.
        
        Returns:
            dict: {'success': bool, 'message': str, 'campo_creado': CampoDinamico or None, 'logs': list}
        """
        import pandas as pd
        logs = []
        try:
            # 1. Validar nombre
            EjecutorMigraciones.validar_nombre_snake_case(nombre_campo_bd)
            logs.append({'nivel': 'debug', 'mensaje': f'Nombre validado: {nombre_campo_bd}'})
            
            # 2. Verificar si ya existe
            if CampoDinamico.objects.filter(nombre_campo_bd=nombre_campo_bd).exists():
                msg = f'El campo {nombre_campo_bd} ya existe en la base de datos.'
                logs.append({'nivel': 'warning', 'mensaje': msg})
                return {
                    'success': False,
                    'message': msg,
                    'campo_creado': None,
                    'logs': logs
                }
            
            # 3. Ejecutar ALTER TABLE
            # Incluir esquema dbo para SQL Server
            tabla = 'dbo.ingestas_propiedadraw'
            tipo_sql = EjecutorMigraciones.mapear_tipo_django(tipo_dato)
            
            with connection.cursor() as cursor:
                # Verificar si la columna ya existe en la tabla (SQL Server syntax)
                # TABLE_NAME no incluye esquema, necesitamos filtrar por TABLE_SCHEMA también
                # tabla = 'dbo.ingestas_propiedadraw' -> esquema = 'dbo', nombre_tabla = 'ingestas_propiedadraw'
                esquema, nombre_tabla = tabla.split('.') if '.' in tabla else ('dbo', tabla)
                check_sql = """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """
                logs.append({'nivel': 'debug', 'mensaje': f'Verificando columna: esquema={esquema}, tabla={nombre_tabla}, campo={nombre_campo_bd}'})
                try:
                    cursor.execute(check_sql, [esquema, nombre_tabla, nombre_campo_bd])
                except Exception as e:
                    logs.append({'nivel': 'error', 'mensaje': f'Error al verificar columna: {e}'})
                    # Continuar igual, puede que la tabla no tenga esquema en INFORMATION_SCHEMA
                    pass
                if cursor.fetchone():
                    msg = f'La columna {nombre_campo_bd} ya existe en la tabla {tabla}.'
                    logs.append({'nivel': 'warning', 'mensaje': msg})
                    return {
                        'success': False,
                        'message': msg,
                        'campo_creado': None,
                        'logs': logs
                    }
                
                # Ejecutar ALTER TABLE (SQL Server syntax - sin COLUMN)
                sql = f'ALTER TABLE {tabla} ADD {nombre_campo_bd} {tipo_sql}'
                logs.append({'nivel': 'debug', 'mensaje': f'Ejecutando SQL: {sql}'})
                try:
                    cursor.execute(sql)
                except Exception as e:
                    # Capturar error de columna duplicada (código 2705)
                    error_msg = str(e)
                    if '2705' in error_msg or 'duplicate' in error_msg.lower() or 'already exists' in error_msg.lower():
                        msg = f'La columna {nombre_campo_bd} ya existe en la tabla {tabla}.'
                        logs.append({'nivel': 'error', 'mensaje': msg})
                        return {
                            'success': False,
                            'message': msg,
                            'campo_creado': None,
                            'logs': logs
                        }
                    else:
                        logs.append({'nivel': 'error', 'mensaje': f'Error al ejecutar ALTER TABLE: {e}'})
                        raise
            
            # 4. Crear registro en CampoDinamico
            # Manejar usuario anónimo
            creado_por = None
            if user and not user.is_anonymous:
                creado_por = user
            
            campo = CampoDinamico.objects.create(
                nombre_campo_bd=nombre_campo_bd,
                titulo_display=titulo_display,
                tipo_dato=tipo_dato,
                creado_por=creado_por
            )
            logs.append({'nivel': 'info', 'mensaje': f'Campo dinámico creado en modelo: {nombre_campo_bd}'})
            
            # 5. Marcar migración como completada
            MigracionPendiente.objects.filter(
                nombre_campo_bd=nombre_campo_bd,
                estado='pendiente'
            ).update(
                estado='completada',
                ejecutada_en=pd.Timestamp.now()
            )
            logs.append({'nivel': 'info', 'mensaje': 'Migración marcada como completada'})
            
            return {
                'success': True,
                'message': f'Campo {nombre_campo_bd} creado exitosamente.',
                'campo_creado': campo,
                'logs': logs
            }
            
        except Exception as e:
            # Registrar error en MigracionPendiente
            MigracionPendiente.objects.create(
                nombre_campo_bd=nombre_campo_bd,
                titulo_display=titulo_display,
                tipo_dato=tipo_dato,
                estado='error',
                error_mensaje=str(e)
            )
            logs.append({'nivel': 'error', 'mensaje': f'Error al crear campo: {str(e)}'})
            return {
                'success': False,
                'message': f'Error al crear campo: {str(e)}',
                'campo_creado': None,
                'logs': logs
            }


class ProcesadorExcel:
    """Clase para procesar archivos Excel y cargar datos."""
    
    @staticmethod
    def leer_archivo(archivo):
        """Lee archivo Excel o CSV y retorna DataFrame."""
        import pandas as pd
        if archivo.name.endswith('.csv'):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo, engine='openpyxl')
        return df
    
    @staticmethod
    def obtener_preview(df, filas=5):
        """Retorna primeras filas como lista de diccionarios."""
        import pandas as pd
        preview = df.head(filas).replace({pd.NA: None, pd.NaT: None})
        # Convertir Timestamps a strings para serialización JSON
        def convert_value(val):
            if isinstance(val, pd.Timestamp):
                return val.isoformat()
            return val
        # Aplicar conversión a todas las celdas usando apply sobre cada columna
        for col in preview.columns:
            preview[col] = preview[col].apply(convert_value)
        return preview.to_dict('records')
    
    @staticmethod
    def detectar_columnas(df):
        """Retorna lista de columnas con información básica."""
        import pandas as pd
        import numpy as np
        columnas = []
        for col in df.columns:
            valores_muestra = df[col].head(20).tolist()
            # Convertir Timestamps a strings para serialización JSON
            valores_serializables = []
            for val in valores_muestra:
                if isinstance(val, pd.Timestamp):
                    valores_serializables.append(val.isoformat())
                elif pd.isna(val):
                    valores_serializables.append(None)
                elif isinstance(val, (np.integer, np.floating)):
                    # Convertir tipos numpy a tipos Python nativos
                    valores_serializables.append(val.item())
                else:
                    valores_serializables.append(val)
            columnas.append({
                'nombre': col,
                'tipo_pandas': str(df[col].dtype),
                'valores_muestra': valores_serializables,
                'no_nulos': int(df[col].notna().sum()),
                'total': int(len(df[col])),
            })
        return columnas

    @staticmethod
    def importar_datos(df, mapeos, nombre_fuente, portal_origen, user):
        """
        Importa filas del DataFrame a PropiedadRaw usando los mapeos proporcionados.
        
        Args:
            df: DataFrame de pandas con los datos originales
            mapeos: dict donde clave es nombre_columna_origen y valor es dict con:
                - campo_bd: nombre del campo en la base de datos (snake_case)
                - titulo_display: título para mostrar
                - tipo_dato: tipo de dato (VARCHAR, INTEGER, etc.)
            nombre_fuente: nombre de la fuente (ej: PortalInmobiliarioXYZ)
            portal_origen: portal de origen (ej: urbania, adondevivir)
            user: usuario que realiza la importación
            
        Returns:
            dict con estadísticas: {'filas_procesadas': int, 'campos_creados': int, 'errores': int, 'debug': str, 'logs': list}
        """
        from .models import PropiedadRaw, MapeoFuente, CampoDinamico
        import pandas as pd
        import numpy as np
        
        filas_procesadas = 0
        errores = 0
        debug_msgs = []
        logs = []  # Lista de logs estructurados para la interfaz
        
        # Crear o actualizar MapeoFuente
        mapeo_fuente, created = MapeoFuente.objects.update_or_create(
            nombre_fuente=nombre_fuente,
            portal_origen=portal_origen,
            defaults={'mapeos_confirmados': mapeos}
        )
        
        log_info = f'DataFrame shape: {df.shape}, mapeos: {len(mapeos)}'
        debug_msgs.append(log_info)
        logs.append({'nivel': 'info', 'mensaje': log_info})
        
        # Iterar sobre cada fila del DataFrame
        for idx, row in df.iterrows():
            try:
                # Preparar atributos extras (campos dinámicos)
                atributos_extras = {}
                # Campos fijos (si existen columnas con nombres específicos)
                tipo_propiedad = row.get('Tipo de Propiedad') if 'Tipo de Propiedad' in row else None
                precio_usd = row.get('Precio USD') if 'Precio USD' in row else None
                ubicacion = row.get('Ubicación') if 'Ubicación' in row else None
                metros_cuadrados = row.get('Metros Cuadrados') if 'Metros Cuadrados' in row else None
                habitaciones = row.get('Habitaciones') if 'Habitaciones' in row else None
                banos = row.get('Baños') if 'Baños' in row else None
                estacionamientos = row.get('Estacionamientos') if 'Estacionamientos' in row else None
                descripcion = row.get('Descripción') if 'Descripción' in row else None
                url_fuente = row.get('URL Fuente') if 'URL Fuente' in row else None
                
                # Convertir tipos adecuadamente
                def convertir_valor(val, tipo_dato):
                    if pd.isna(val):
                        return None
                    if tipo_dato == 'INTEGER':
                        try:
                            return int(float(val))
                        except (ValueError, TypeError):
                            return None
                    elif tipo_dato == 'DECIMAL':
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return None
                    elif tipo_dato == 'BOOLEAN':
                        if isinstance(val, str):
                            return val.lower() in ('true', 'si', 'sí', '1', 'yes')
                        return bool(val)
                    elif tipo_dato in ('DATE', 'DATETIME'):
                        try:
                            # Convertir a datetime de pandas
                            dt = pd.to_datetime(val)
                            # Para DATE, devolver string YYYY-MM-DD
                            if tipo_dato == 'DATE':
                                return dt.strftime('%Y-%m-%d')
                            else:
                                # DATETIME: devolver string ISO
                                return dt.isoformat()
                        except (ValueError, TypeError):
                            return None
                    else:  # VARCHAR
                        return str(val) if not pd.isna(val) else None
                
                # Procesar cada columna mapeada
                for col_origen, info in mapeos.items():
                    if col_origen in row:
                        valor = row[col_origen]
                        valor_convertido = convertir_valor(valor, info['tipo_dato'])
                        atributos_extras[info['campo_bd']] = valor_convertido
                        # Log para depuración: verificar si el campo tiene columna física
                        campo_dinamico = CampoDinamico.objects.filter(nombre_campo_bd=info['campo_bd']).first()
                        if campo_dinamico:
                            # Verificar si la columna existe en la tabla física
                            columna_fisica = EjecutorMigraciones.columna_existe_en_tabla(info['campo_bd'])
                            logs.append({'nivel': 'debug', 'mensaje': f'Campo {info["campo_bd"]} tiene columna física: {columna_fisica}'})
                
                # Crear registro en PropiedadRaw
                propiedad = PropiedadRaw.objects.create(
                    fuente_excel=nombre_fuente,
                    tipo_propiedad=tipo_propiedad,
                    precio_usd=precio_usd,
                    moneda='USD',
                    ubicacion=ubicacion,
                    metros_cuadrados=metros_cuadrados,
                    habitaciones=habitaciones,
                    banos=banos,
                    estacionamientos=estacionamientos,
                    descripcion=descripcion,
                    url_fuente=url_fuente,
                    atributos_extras=atributos_extras
                )
                filas_procesadas += 1
                if filas_procesadas % 10 == 0:
                    msg = f'Fila {idx} procesada'
                    debug_msgs.append(msg)
                    logs.append({'nivel': 'debug', 'mensaje': msg})
            except Exception as e:
                errores += 1
                error_msg = f'Error en fila {idx}: {str(e)}'
                debug_msgs.append(error_msg)
                logs.append({'nivel': 'error', 'mensaje': error_msg})
                continue
        
        final_msg = f'Total filas procesadas: {filas_procesadas}, errores: {errores}'
        debug_msgs.append(final_msg)
        logs.append({'nivel': 'info', 'mensaje': final_msg})
        
        return {
            'filas_procesadas': filas_procesadas,
            'campos_creados': len(mapeos),
            'errores': errores,
            'debug': ' | '.join(debug_msgs),
            'logs': logs
        }