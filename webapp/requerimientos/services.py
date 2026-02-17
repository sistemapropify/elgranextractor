import re
import pandas as pd
import sys
import json
import requests
from django.db import connection
from django.contrib.auth.models import User
from .models import CampoDinamicoRequerimiento, MigracionPendienteRequerimiento, RequerimientoRaw


class SugeridorCamposRequerimiento:
    """Clase para analizar columnas de Excel y sugerir nombres y tipos para requerimientos."""

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
            if str(val).lower() in ('true', 'false', 'si', 'no', '1', '0', 'sí', 'verdadero', 'falso'):
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
        nombre_sugerido_bd = SugeridorCamposRequerimiento.convertir_a_snake_case(nombre_columna)
        titulo_sugerido_display = nombre_columna.title()
        tipo_sugerido = SugeridorCamposRequerimiento.inferir_tipo_dato(valores_muestra)
        
        # Buscar campos existentes similares
        similares_existentes = []
        campos_existentes = CampoDinamicoRequerimiento.objects.filter(
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

    @staticmethod
    def sugerir_campos(df):
        """Analiza todas las columnas del DataFrame y retorna sugerencias."""
        sugerencias = []
        
        for columna in df.columns:
            # Tomar muestra de valores (máximo 50)
            valores_muestra = df[columna].dropna().head(50).tolist()
            analisis = SugeridorCamposRequerimiento.analizar_columna(columna, valores_muestra)
            
            sugerencias.append({
                'nombre_columna': columna,
                'nombre_sugerido': analisis['nombre_sugerido_bd'],
                'titulo_display': analisis['titulo_sugerido_display'],
                'tipo_dato': analisis['tipo_sugerido'],
                'similares_existentes': analisis['similares_existentes'],
            })
        
        return sugerencias


class EjecutorMigracionesRequerimiento:
    """Clase para ejecutar migraciones de campos dinámicos en la base de datos para requerimientos."""

    @staticmethod
    def validar_nombre_snake_case(nombre):
        """Valida que el nombre esté en snake_case válido."""
        if not re.match(r'^[a-z][a-z0-9_]*$', nombre):
            raise ValueError(f"Nombre '{nombre}' no es snake_case válido. Use letras minúsculas, números y guiones bajos.")
        return True

    @staticmethod
    def mapear_tipo_django(tipo_dato):
        """Mapea tipos de datos personalizados a tipos de Django/SQL Server."""
        mapeo = {
            'VARCHAR': 'NVARCHAR(MAX)',
            'INTEGER': 'INT',
            'DECIMAL': 'DECIMAL(18, 2)',
            'BOOLEAN': 'BIT',
            'DATE': 'DATE',
            'DATETIME': 'DATETIME2',
        }
        return mapeo.get(tipo_dato.upper(), 'NVARCHAR(MAX)')

    @staticmethod
    def columna_existe_en_tabla(nombre_campo_bd, tabla='dbo.requerimientos_requerimientoraw'):
        """Verifica si una columna ya existe en la tabla física."""
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{tabla.split('.')[-1]}' 
                AND COLUMN_NAME = '{nombre_campo_bd}'
            """)
            return cursor.fetchone() is not None

    @staticmethod
    def ejecutar_migracion(nombre_campo_bd, titulo_display, tipo_dato, user):
        """
        Ejecuta la migración para agregar un campo dinámico a la tabla RequerimientoRaw.
        
        Args:
            nombre_campo_bd: Nombre del campo en snake_case
            titulo_display: Título para mostrar en interfaces
            tipo_dato: VARCHAR, INTEGER, DECIMAL, BOOLEAN, DATE, DATETIME
            user: Usuario que crea el campo
        """
        EjecutorMigracionesRequerimiento.validar_nombre_snake_case(nombre_campo_bd)
        
        # Verificar si ya existe como campo dinámico
        campo_existente = CampoDinamicoRequerimiento.objects.filter(
            nombre_campo_bd=nombre_campo_bd
        ).first()
        
        if campo_existente:
            raise ValueError(f"El campo '{nombre_campo_bd}' ya existe en la tabla de campos dinámicos.")
        
        # Verificar si la columna ya existe físicamente
        if EjecutorMigracionesRequerimiento.columna_existe_en_tabla(nombre_campo_bd):
            raise ValueError(f"La columna '{nombre_campo_bd}' ya existe en la tabla física.")
        
        # Crear registro de migración pendiente
        migracion = MigracionPendienteRequerimiento.objects.create(
            nombre_campo_bd=nombre_campo_bd,
            titulo_display=titulo_display,
            tipo_dato=tipo_dato,
            estado='pendiente'
        )
        
        try:
            # Ejecutar ALTER TABLE
            tipo_sql = EjecutorMigracionesRequerimiento.mapear_tipo_django(tipo_dato)
            tabla = 'dbo.requerimientos_requerimientoraw'
            
            with connection.cursor() as cursor:
                # Para SQL Server
                cursor.execute(f"""
                    ALTER TABLE {tabla}
                    ADD [{nombre_campo_bd}] {tipo_sql} NULL
                """)
            
            # Actualizar estado de migración
            migracion.estado = 'completada'
            migracion.ejecutada_en = pd.Timestamp.now()
            migracion.save()
            
            # Crear registro de campo dinámico
            CampoDinamicoRequerimiento.objects.create(
                nombre_campo_bd=nombre_campo_bd,
                titulo_display=titulo_display,
                tipo_dato=tipo_dato,
                creado_por=user
            )
            
            return True
            
        except Exception as e:
            # Registrar error
            migracion.estado = 'error'
            migracion.error_mensaje = str(e)
            migracion.save()
            raise


class ProcesadorExcelRequerimiento:
    """Clase para procesar archivos Excel y cargar datos de requerimientos."""

    @staticmethod
    def leer_archivo(archivo):
        """Lee un archivo Excel o CSV y retorna un DataFrame."""
        if archivo.name.lower().endswith('.csv'):
            # Intentar diferentes codificaciones
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            for encoding in encodings:
                try:
                    return pd.read_csv(archivo, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            # Último intento
            return pd.read_csv(archivo, encoding=None)
        else:
            return pd.read_excel(archivo, engine='openpyxl')

    @staticmethod
    def obtener_preview(df, filas=5):
        """Retorna primeras filas como lista de diccionarios."""
        def convert_value(val):
            if pd.isna(val):
                return None
            if isinstance(val, pd.Timestamp):
                return val.strftime('%Y-%m-%d %H:%M:%S')
            return str(val)
        
        preview = []
        for _, row in df.head(filas).iterrows():
            preview.append({col: convert_value(row[col]) for col in df.columns})
        return preview

    @staticmethod
    def detectar_columnas(df):
        """Detecta columnas y sugiere mapeos automáticos."""
        sugerencias = SugeridorCamposRequerimiento.sugerir_campos(df)
        return sugerencias

    @staticmethod
    def importar_datos(df, mapeos, nombre_fuente, portal_origen, user):
        """
        Importa datos desde DataFrame a la tabla RequerimientoRaw.
        
        Args:
            df: DataFrame con datos
            mapeos: Dict con mapeo {columna_origen: {campo_bd, titulo_display, tipo_dato}}
            nombre_fuente: Nombre de la fuente
            portal_origen: Portal de origen
            user: Usuario que importa
        
        Returns:
            Dict con resultados: {'importados': int, 'errores': int, 'detalles': list}
        """
        importados = 0
        errores = 0
        detalles = []
        
        # Verificar qué campos dinámicos existen físicamente en la tabla
        from django.db import connection
        campos_fisicos = set()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'requerimientos_requerimientoraw'
            """)
            for row in cursor.fetchall():
                campos_fisicos.add(row[0].lower())
        
        # Campos base que siempre existen
        campos_base = {'id', 'fuente_excel', 'fecha_ingesta', 'atributos_extras'}
        todos_campos_fisicos = campos_fisicos.union(campos_base)
        
        for idx, row in df.iterrows():
            try:
                # Preparar datos para creación
                datos = {
                    'fuente_excel': nombre_fuente,
                    'atributos_extras': {}
                }
                
                # Procesar cada columna mapeada
                for col_orig, mapeo in mapeos.items():
                    if col_orig in df.columns and not pd.isna(row[col_orig]):
                        valor = row[col_orig]
                        campo_bd = mapeo['campo_bd']
                        
                        # Verificar si el campo existe físicamente en la tabla
                        if campo_bd in todos_campos_fisicos:
                            # El campo existe físicamente, poner el dato ahí
                            datos[campo_bd] = valor
                        else:
                            # El campo no existe físicamente, poner en atributos_extras
                            datos['atributos_extras'][campo_bd] = valor
                
                # Crear registro
                requerimiento = RequerimientoRaw.objects.create(**datos)
                importados += 1
                
                # Obtener algún identificador para el mensaje
                identificador = datos.get('cliente_nombre',
                                  datos.get('email',
                                  datos.get('telefono',
                                  datos['atributos_extras'].get('cliente_nombre',
                                  datos['atributos_extras'].get('email',
                                  datos['atributos_extras'].get('telefono', f'ID {requerimiento.id}'))))))
                
                detalles.append({
                    'fila': idx + 2,  # +2 porque Excel empieza en 1 y header es fila 1
                    'estado': 'OK',
                    'mensaje': f'Requerimiento creado: {identificador}'
                })
                
            except Exception as e:
                errores += 1
                detalles.append({
                    'fila': idx + 2,
                    'estado': 'ERROR',
                    'mensaje': str(e)[:200]
                })
        
        return {
            'importados': importados,
            'errores': errores,
            'detalles': detalles
        }


class ExtractorInteligenteRequerimientos:
    """Clase para extracción inteligente de datos de textos no estructurados usando DeepSeek API."""
    
    # API key de DeepSeek (debería estar en settings, pero usamos una constante por ahora)
    DEEPSEEK_API_KEY = "sk-460d28e38c7e4b05a13fa2bebd27159c"
    DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
    
    @staticmethod
    def extraer_datos_requerimiento(texto, campos_solicitados=None):
        """
        Extrae datos estructurados de un texto no estructurado de requerimiento inmobiliario.
        
        Args:
            texto: Texto no estructurado (ej: "🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 ...")
            campos_solicitados: Lista de campos a extraer (opcional)
            
        Returns:
            Dict con datos extraídos
        """
        if campos_solicitados is None:
            campos_solicitados = [
                'presupuesto', 'tipo_inmueble', 'ubicacion', 'zonas_interes',
                'banos', 'habitaciones', 'contacto', 'cliente', 'estado_credito',
                'moneda', 'fecha_requerimiento', 'notas'
            ]
        
        prompt = f"""Eres un experto en extracción de datos de requerimientos inmobiliarios. Extrae la información estructurada del siguiente texto y devuélvela en formato JSON válido.

Texto del requerimiento:
{texto}

Campos a extraer (si están presentes en el texto):
{', '.join(campos_solicitados)}

Instrucciones:
1. Extrae solo los datos que aparecen explícitamente en el texto.
2. Si un campo no está presente, omítelo del JSON.
3. Convierte valores monetarios a números (ej: "USD 130,000" → 130000).
4. Normaliza tipos de inmueble: "Departamento", "Casa", "Oficina", "Local", "Terreno".
5. Para ubicaciones, extrae distrito, ciudad, departamento si están mencionados.
6. Para contactos, extrae teléfono y nombre si están presentes.
7. Devuelve un objeto JSON con los campos extraídos.

Respuesta debe ser SOLO el JSON, sin explicaciones."""
        
        headers = {
            "Authorization": f"Bearer {ExtractorInteligenteRequerimientos.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un asistente especializado en extracción estructurada de datos de textos inmobiliarios. Siempre respondes con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                ExtractorInteligenteRequerimientos.DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            content = response.json()["choices"][0]["message"]["content"]
            
            # Extraer JSON de la respuesta
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                datos = json.loads(json_match.group())
                return datos
            else:
                return {"error": "No se pudo extraer JSON", "raw_response": content}
                
        except Exception as e:
            return {"error": str(e), "raw_response": None}
    
    @staticmethod
    def procesar_columna_texto(df, nombre_columna, crear_campos=True):
        """
        Procesa una columna de texto no estructurado para extraer datos estructurados.
        
        Args:
            df: DataFrame con los datos
            nombre_columna: Nombre de la columna que contiene texto no estructurado
            crear_campos: Si True, sugiere crear campos dinámicos basados en los datos extraídos
            
        Returns:
            Dict con resultados y sugerencias de campos
        """
        if nombre_columna not in df.columns:
            return {"error": f"Columna '{nombre_columna}' no encontrada en el DataFrame"}
        
        # Tomar una muestra de textos para análisis
        textos_muestra = df[nombre_columna].dropna().head(10).tolist()
        
        if not textos_muestra:
            return {"error": "No hay textos para analizar"}
        
        # Analizar el primer texto para obtener campos
        primer_texto = textos_muestra[0]
        datos_ejemplo = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(primer_texto)
        
        # Sugerir campos basados en los datos extraídos
        campos_sugeridos = []
        if isinstance(datos_ejemplo, dict) and "error" not in datos_ejemplo:
            for campo, valor in datos_ejemplo.items():
                # Inferir tipo de dato
                if isinstance(valor, (int, float)):
                    tipo_dato = "DECIMAL" if isinstance(valor, float) else "INTEGER"
                elif isinstance(valor, bool):
                    tipo_dato = "BOOLEAN"
                else:
                    tipo_dato = "VARCHAR(500)"
                
                campos_sugeridos.append({
                    "nombre_campo": campo,
                    "titulo_display": campo.replace('_', ' ').title(),
                    "tipo_dato": tipo_dato,
                    "ejemplo": valor
                })
        
        return {
            "textos_analizados": len(textos_muestra),
            "campos_sugeridos": campos_sugeridos,
            "ejemplo_extraccion": datos_ejemplo,
            "recomendacion": "Se recomienda crear campos dinámicos para los datos extraídos y procesar cada fila individualmente."
        }
    
    @staticmethod
    def analizar_dataframe_completo(df, max_muestras_por_columna=5):
        """
        Analiza todo el DataFrame para sugerir campos dinámicos basados en el contenido de todas las columnas.
        
        Args:
            df: DataFrame con los datos del Excel
            max_muestras_por_columna: Número máximo de muestras a analizar por columna
            
        Returns:
            Dict con sugerencias de campos para cada columna y recomendaciones generales
        """
        import pandas as pd
        
        resultados = {}
        campos_sugeridos_global = []
        
        for columna in df.columns:
            # Obtener muestras de la columna
            muestras = df[columna].dropna().head(max_muestras_por_columna).tolist()
            if not muestras:
                resultados[columna] = {"error": "Columna vacía"}
                continue
            
            # Determinar si la columna contiene texto no estructurado (basado en heurísticas)
            es_texto_largo = any(isinstance(val, str) and len(val) > 50 for val in muestras)
            contiene_emojis = any(isinstance(val, str) and any(c in val for c in ['🏢', '✨', '📍', '💰', '📲']) for val in muestras)
            
            if es_texto_largo or contiene_emojis:
                # Es texto no estructurado, usar IA para extraer campos
                texto_ejemplo = muestras[0]
                datos_extraidos = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto_ejemplo)
                if isinstance(datos_extraidos, dict) and "error" not in datos_extraidos:
                    campos_columna = []
                    for campo, valor in datos_extraidos.items():
                        tipo = "VARCHAR(500)" if isinstance(valor, str) else "INTEGER" if isinstance(valor, int) else "DECIMAL" if isinstance(valor, float) else "BOOLEAN"
                        campos_columna.append({
                            "nombre_campo": campo,
                            "titulo_display": campo.replace('_', ' ').title(),
                            "tipo_dato": tipo,
                            "ejemplo": valor,
                            "origen": f"Extraído de columna '{columna}'"
                        })
                        campos_sugeridos_global.append({
                            "nombre_campo": campo,
                            "tipo_dato": tipo,
                            "origen": columna
                        })
                    resultados[columna] = {
                        "tipo": "texto_no_estructurado",
                        "campos_sugeridos": campos_columna,
                        "ejemplo_extraccion": datos_extraidos
                    }
                else:
                    resultados[columna] = {
                        "tipo": "texto_no_estructurado",
                        "error": "No se pudieron extraer datos estructurados",
                        "raw": datos_extraidos
                    }
            else:
                # Columna estructurada, usar sugeridor normal
                sugerencia = SugeridorCamposRequerimiento.analizar_columna(columna, muestras)
                resultados[columna] = {
                    "tipo": "estructurado",
                    "sugerencia": sugerencia
                }
                # Si la sugerencia incluye un nombre de campo, agregar a la lista global
                if sugerencia.get('campo_bd'):
                    campos_sugeridos_global.append({
                        "nombre_campo": sugerencia['campo_bd'],
                        "tipo_dato": sugerencia['tipo_dato'],
                        "origen": columna
                    })
        
        # Consolidar campos sugeridos (eliminar duplicados)
        campos_unicos = {}
        for campo in campos_sugeridos_global:
            nombre = campo["nombre_campo"]
            if nombre not in campos_unicos:
                campos_unicos[nombre] = campo
            else:
                # Si ya existe, combinar tipos (preferir el más específico)
                pass
        
        return {
            "analisis_por_columna": resultados,
            "campos_sugeridos_consolidados": list(campos_unicos.values()),
            "recomendacion": f"Se analizaron {len(df.columns)} columnas. Se sugieren {len(campos_unicos)} campos dinámicos."
        }