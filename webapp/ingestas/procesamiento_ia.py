"""
Módulo de procesamiento de archivos Excel con análisis de IA para extracción de campos dinámicos.
"""
import re
import pandas as pd
import sys
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LoggerDetallado:
    """Sistema de logging detallado con formato específico."""
    
    @staticmethod
    def log(nivel: str, modulo: str, mensaje: str, datos: Optional[Dict] = None):
        """
        Registra un mensaje con formato: [YYYY-MM-DD HH:MM:SS] [NIVEL] [MÓDULO] Mensaje descriptivo
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mensaje_formateado = f"[{timestamp}] [{nivel.upper()}] [{modulo}] {mensaje}"
        if datos:
            mensaje_formateado += f" | {json.dumps(datos, ensure_ascii=False)}"
        
        # Imprimir a consola
        print(mensaje_formateado)
        
        # También escribir a archivo de log (opcional)
        with open('debug_logs.txt', 'a', encoding='utf-8') as f:
            f.write(mensaje_formateado + '\n')
        
        # Usar logging estándar según nivel
        if nivel == 'DEBUG':
            logger.debug(mensaje_formateado)
        elif nivel == 'INFO':
            logger.info(mensaje_formateado)
        elif nivel == 'WARN':
            logger.warning(mensaje_formateado)
        elif nivel == 'ERROR':
            logger.error(mensaje_formateado)
        elif nivel == 'SUCCESS':
            logger.info(mensaje_formateado)  # No hay nivel SUCCESS, usamos INFO
    
    @staticmethod
    def info(modulo: str, mensaje: str, datos: Optional[Dict] = None):
        LoggerDetallado.log('INFO', modulo, mensaje, datos)
    
    @staticmethod
    def debug(modulo: str, mensaje: str, datos: Optional[Dict] = None):
        LoggerDetallado.log('DEBUG', modulo, mensaje, datos)
    
    @staticmethod
    def warn(modulo: str, mensaje: str, datos: Optional[Dict] = None):
        LoggerDetallado.log('WARN', modulo, mensaje, datos)
    
    @staticmethod
    def error(modulo: str, mensaje: str, datos: Optional[Dict] = None):
        LoggerDetallado.log('ERROR', modulo, mensaje, datos)
    
    @staticmethod
    def success(modulo: str, mensaje: str, datos: Optional[Dict] = None):
        LoggerDetallado.log('SUCCESS', modulo, mensaje, datos)


class CargadorArchivo:
    """Módulo de carga de archivo Excel con validaciones."""
    
    COLUMNAS_ESTANDAR = ['fuente', 'fecha', 'hora', 'agente', 'requerimiento', 'tipo']
    
    @staticmethod
    def validar_formato(nombre_archivo: str) -> bool:
        """Valida que el archivo sea Excel (.xlsx, .xls) o CSV."""
        extensiones_validas = ['.xlsx', '.xls', '.csv']
        return any(nombre_archivo.lower().endswith(ext) for ext in extensiones_validas)
    
    @staticmethod
    def cargar_archivo(ruta_archivo: str) -> pd.DataFrame:
        """
        Carga archivo Excel o CSV y retorna DataFrame.
        Realiza detección automática de encabezados.
        """
        LoggerDetallado.info('CARGA', f'Cargando archivo: {ruta_archivo}')
        
        if not CargadorArchivo.validar_formato(ruta_archivo):
            raise ValueError(f'Formato de archivo no válido: {ruta_archivo}')
        
        try:
            if ruta_archivo.lower().endswith('.csv'):
                df = pd.read_csv(ruta_archivo, index_col=False)
            else:
                df = pd.read_excel(ruta_archivo, engine='openpyxl')
        except Exception as e:
            LoggerDetallado.error('CARGA', f'Error al cargar archivo: {str(e)}')
            raise
        
        LoggerDetallado.debug('CARGA', f'Columnas originales: {list(df.columns)}')
        LoggerDetallado.debug('CARGA', f'Shape original: {df.shape}')
        
        # Si no hay columnas, el archivo está vacío o no se pudieron detectar
        if len(df.columns) == 0:
            raise ValueError('El archivo no contiene columnas detectables. Verifique que el archivo tenga datos estructurados y un formato válido (Excel/CSV).')
        
        # Eliminar columnas sin nombre (Unnamed) solo si hay otras columnas con nombre
        columnas_unnamed = [col for col in df.columns if isinstance(col, str) and col.startswith('Unnamed')]
        if columnas_unnamed:
            # Si todas las columnas son Unnamed, no eliminamos ninguna (podría ser archivo sin encabezados)
            if len(columnas_unnamed) == len(df.columns):
                LoggerDetallado.warn('CARGA', f'Todas las columnas son "Unnamed". Se mantendrán como columnas de datos.')
                # Renombrar columnas a col_0, col_1, etc.
                df.columns = [f'col_{i}' for i in range(len(df.columns))]
            else:
                df = df.drop(columns=columnas_unnamed)
                LoggerDetallado.debug('CARGA', f'Columnas sin nombre eliminadas: {columnas_unnamed}')
        
        LoggerDetallado.info('CARGA', f'Archivo cargado. Filas: {len(df)}, Columnas: {len(df.columns)}')
        LoggerDetallado.debug('CARGA', f'Columnas detectadas: {list(df.columns)}')
        
        return df
    
    @staticmethod
    def detectar_columnas_estandar(df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """
        Detecta columnas estándar por similitud de nombres.
        Retorna mapeo {columna_estandar: nombre_columna_en_df}
        """
        mapeo = {}
        columnas_df = [str(col).lower().strip() for col in df.columns]
        
        for estandar in CargadorArchivo.COLUMNAS_ESTANDAR:
            encontrado = None
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if estandar in col_lower or col_lower in estandar:
                    encontrado = col
                    break
            mapeo[estandar] = encontrado
        
        LoggerDetallado.info('DETECCION', f'Columnas estándar detectadas: {mapeo}')
        return mapeo
    
    @staticmethod
    def validar_columna_requerimiento(df: pd.DataFrame, columna_requerimiento: str) -> bool:
        """Valida que la columna requerimiento no esté vacía."""
        if columna_requerimiento not in df.columns:
            return False
        
        vacios = df[columna_requerimiento].isna().sum()
        total = len(df)
        if vacios == total:
            LoggerDetallado.error('VALIDACION', 'Columna requerimiento completamente vacía')
            return False
        
        LoggerDetallado.info('VALIDACION', 
                            f'Columna requerimiento: {vacios} vacíos de {total} filas')
        return True
    
    @staticmethod
    def detectar_columna_texto_principal(df: pd.DataFrame) -> Optional[str]:
        """
        Detecta la columna más probable que contenga texto de requerimiento/descripción.
        Busca sinónimos y columnas con contenido textual.
        """
        sinónimos = [
            'requerimiento', 'descripcion', 'descripción', 'texto', 'comentario',
            'mensaje', 'solicitud', 'observacion', 'observación', 'detalle',
            'requerimientos', 'descripciones', 'comentarios'
        ]
        
        # Primero buscar por nombre de columna
        columnas_df = [str(col).lower().strip() for col in df.columns]
        for col_name, col_lower in zip(df.columns, columnas_df):
            for sin in sinónimos:
                if sin in col_lower:
                    LoggerDetallado.info('DETECCION',
                                        f'Columna de texto detectada por nombre: {col_name}')
                    return col_name
        
        # Si no encuentra, buscar columnas con tipo object/string que tengan contenido
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
                # Verificar que no esté mayormente vacía
                no_vacios = df[col].dropna().shape[0]
                if no_vacios > 0:
                    LoggerDetallado.info('DETECCION',
                                        f'Columna de texto detectada por tipo: {col} ({no_vacios} no vacíos)')
                    return col
        
        LoggerDetallado.warn('DETECCION', 'No se detectó columna de texto principal')
        return None

    @staticmethod
    def obtener_preview(df: pd.DataFrame, filas: int = 10) -> List[Dict]:
        """Retorna preview de las primeras filas como lista de diccionarios."""
        preview = df.head(filas).replace({pd.NA: None, pd.NaT: None})
        # Convertir Timestamps a strings
        for col in preview.columns:
            if pd.api.types.is_datetime64_any_dtype(preview[col]):
                preview[col] = preview[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        return preview.to_dict('records')


class MotorIA:
    """Motor de análisis con IA para extraer campos dinámicos de descripciones textuales."""
    
    CATEGORIAS_CAMPOS = {
        'UBICACIÓN': ['zona', 'distrito', 'referencia_ubicacion', 'cerca_a'],
        'PROPIEDAD': ['tipo_inmueble', 'dormitorios', 'banos', 'area_m2', 'cochera', 'ascensor'],
        'CONDICIONES': ['amoblado', 'pet_friendly', 'antiguedad', 'estado'],
        'ECONÓMICO': ['presupuesto', 'moneda', 'rango_precio', 'modalidad_pago'],
        'TEMPORAL': ['fecha_inicio', 'duracion_contrato', 'urgencia'],
        'CONTACTO/AGENTE': ['nombre_agente', 'telefono', 'correo']
    }
    
    @staticmethod
    def generar_prompt(texto: str) -> str:
        """
        Genera prompt para IA basado en el texto de requerimiento.
        """
        prompt = f"""
Analiza el siguiente texto en español que describe un requerimiento inmobiliario.
Identifica la intención: ¿es VENTA, ALQUILER, REQUERIMIENTO, ANTICRESIS?
Extrae datos estructurados incluso si están escritos de forma coloquial.
Normaliza valores (ej: "3 dor" → dormitorios: 3).
Si un dato no está presente, omite el campo, no inventes.
Prioriza precisión sobre completitud.

Texto a analizar: "{texto}"

Proporciona la respuesta en formato JSON con la siguiente estructura:
{{
  "intencion": "VENTA|ALQUILER|REQUERIMIENTO|ANTICRESIS|DESCONOCIDO",
  "campos_detectados": {{
    "campo1": "valor_normalizado",
    "campo2": "valor_normalizado"
  }},
  "confianza": 0.95
}}

Solo responde con el JSON, sin explicaciones adicionales.
"""
        return prompt.strip()
    
    @staticmethod
    def llamar_ia(prompt: str) -> Dict:
        """
        Simula llamada a IA (por ahora mock).
        En producción se integraría con OpenAI, DeepSeek, etc.
        """
        # TODO: Integrar con API real
        # Por ahora, retorna un mock basado en palabras clave
        texto = prompt.lower()
        
        # Detección simple de intención
        intencion = 'DESCONOCIDO'
        if 'venta' in texto:
            intencion = 'VENTA'
        elif 'alquiler' in texto or 'alquilar' in texto:
            intencion = 'ALQUILER'
        elif 'requerimiento' in texto:
            intencion = 'REQUERIMIENTO'
        
        # Extracción simple de campos (mock)
        campos = {}
        if 'dormitorio' in texto or 'habitacion' in texto:
            # Buscar número
            match = re.search(r'(\d+)\s*(dormitorio|habitacion)', texto)
            if match:
                campos['dormitorios'] = int(match.group(1))
            else:
                campos['dormitorios'] = 1
        
        if 'baño' in texto or 'banos' in texto:
            match = re.search(r'(\d+)\s*(baño|banos)', texto)
            if match:
                campos['banos'] = int(match.group(1))
        
        if 'm2' in texto or 'metro' in texto:
            match = re.search(r'(\d+)\s*m2', texto)
            if match:
                campos['area_m2'] = int(match.group(1))
        
        if 'presupuesto' in texto or 'precio' in texto:
            match = re.search(r'(\d+[\d,]*)\s*(soles|usd|dólar)', texto)
            if match:
                campos['presupuesto'] = match.group(1)
                campos['moneda'] = 'USD' if 'usd' in texto or 'dólar' in texto else 'PEN'
        
        return {
            "intencion": intencion,
            "campos_detectados": campos,
            "confianza": 0.7 if campos else 0.3
        }
    
    @staticmethod
    def analizar_fila(texto: str, fila_idx: int) -> Dict:
        """
        Analiza una fila individual con IA.
        """
        LoggerDetallado.debug('IA', f'Analizando fila {fila_idx}')
        
        prompt = MotorIA.generar_prompt(texto)
        prompt_truncado = (prompt[:200] + '...') if len(prompt) > 200 else prompt
        LoggerDetallado.debug('IA', f'Prompt enviado (truncado): {prompt_truncado}')
        
        try:
            respuesta = MotorIA.llamar_ia(prompt)
            LoggerDetallado.debug('IA', f'Respuesta cruda: {respuesta}')
            
            # Validar respuesta
            if not isinstance(respuesta, dict) or 'campos_detectados' not in respuesta:
                raise ValueError('Respuesta de IA no válida')
            
            return respuesta
        except Exception as e:
            LoggerDetallado.error('IA', f'Error en análisis de fila {fila_idx}: {str(e)}')
            return {
                "intencion": "ERROR",
                "campos_detectados": {},
                "confianza": 0.0,
                "error": str(e)
            }


class NormalizadorCampos:
    """Sistema de deduplicación y normalización de campos dinámicos."""
    
    @staticmethod
    def normalizar_nombre(campo: str) -> str:
        """
        Normaliza nombre de campo: lowercase, snake_case, sin tildes.
        """
        import unicodedata
        # Eliminar tildes
        campo = ''.join(c for c in unicodedata.normalize('NFD', campo) 
                       if unicodedata.category(c) != 'Mn')
        # Convertir a snake_case
        campo = re.sub(r'[^\w\s]', '', campo)
        campo = re.sub(r'\s+', '_', campo.strip())
        campo = campo.lower()
        return campo
    
    @staticmethod
    def detectar_sinonimos(campo: str, campos_existentes: List[str]) -> Optional[str]:
        """
        Detecta si el campo es sinónimo de algún campo existente.
        Retorna el campo existente unificado o None si no hay sinónimo.
        """
        sinonimos = {
            'dormitorios': ['habitaciones', 'cuartos', 'dorm', 'habitacion'],
            'banos': ['baños', 'bano', 'baño'],
            'area_m2': ['metros_cuadrados', 'superficie', 'm2', 'area'],
            'presupuesto': ['precio', 'costo', 'valor'],
            'moneda': ['divisa', 'tipo_moneda'],
            'tipo_inmueble': ['tipo', 'inmueble', 'propiedad'],
            'zona': ['distrito', 'ubicacion', 'localidad'],
        }
        
        campo_norm = NormalizadorCampos.normalizar_nombre(campo)
        
        for existente in campos_existentes:
            existente_norm = NormalizadorCampos.normalizar_nombre(existente)
            if campo_norm == existente_norm:
                return existente
            
            # Verificar sinonimos
            for clave, lista in sinonimos.items():
                if campo_norm in lista and existente_norm == clave:
                    return clave
                if existente_norm in lista and campo_norm == clave:
                    return clave
        
        return None
    
    @staticmethod
    def unificar_campos(campos_detectados: List[Dict]) -> Dict[str, List]:
        """
        Unifica campos detectados en todas las filas, normalizando nombres y fusionando sinónimos.
        Retorna diccionario con campos únicos y valores de ejemplo.
        """
        campos_unicos = {}
        valores_ejemplo = {}
        
        for idx, deteccion in enumerate(campos_detectados):
            for campo, valor in deteccion.get('campos_detectados', {}).items():
                campo_norm = NormalizadorCampos.normalizar_nombre(campo)
                
                # Verificar sinónimos
                campo_unificado = NormalizadorCampos.detectar_sinonimos(
                    campo_norm, list(campos_unicos.keys())
                )
                if campo_unificado is None:
                    campo_unificado = campo_norm
                
                # Registrar campo único
                if campo_unificado not in campos_unicos:
                    campos_unicos[campo_unificado] = {
                        'nombre_original': campo,
                        'ocurrencias': 1,
                        'valores_ejemplo': [valor]
                    }
                else:
                    campos_unicos[campo_unificado]['ocurrencias'] += 1
                    if valor not in campos_unicos[campo_unificado]['valores_ejemplo']:
                        campos_unicos[campo_unificado]['valores_ejemplo'].append(valor)
        
        LoggerDetallado.info('NORMALIZACION', 
                            f'Campos dinámicos únicos detectados: {len(campos_unicos)}')
        return campos_unicos


class ProcesadorExcelIA:
    """Clase principal que orquesta el procesamiento completo."""
    
    def __init__(self, debug_mode: bool = True):
        self.debug_mode = debug_mode
        self.logger = LoggerDetallado
        self.cargador = CargadorArchivo
        self.motor_ia = MotorIA
        self.normalizador = NormalizadorCampos
        
    def procesar_archivo(self, ruta_archivo: str, max_filas: int = 50) -> Dict:
        """
        Procesa archivo Excel completo según flujo esperado.
        """
        self.logger.info('SISTEMA', 'Sistema iniciado, esperando archivo...')
        
        # 1. CARGA
        self.logger.info('CARGA', f"Archivo '{ruta_archivo}' cargado")
        df = self.cargador.cargar_archivo(ruta_archivo)
        
        # 2. DETECCIÓN DE COLUMNA DE TEXTO PRINCIPAL
        mapeo_columnas = self.cargador.detectar_columnas_estandar(df)
        columna_requerimiento = mapeo_columnas.get('requerimiento')
        
        # Si no se detecta por nombre estándar, usar detección flexible
        if not columna_requerimiento:
            columna_requerimiento = self.cargador.detectar_columna_texto_principal(df)
        
        if not columna_requerimiento:
            raise ValueError('No se detectó columna de texto para análisis. Asegúrese de que el archivo contenga una columna con descripciones textuales.')
        
        # Validar que la columna exista y tenga al menos algún contenido
        if columna_requerimiento not in df.columns:
            raise ValueError(f'Columna detectada "{columna_requerimiento}" no existe en el DataFrame')
        
        # Validación flexible: permitir columnas con algunos vacíos
        vacios = df[columna_requerimiento].isna().sum()
        total = len(df)
        if vacios == total:
            self.logger.warn('VALIDACION', 'Columna de texto completamente vacía, pero se intentará procesar')
        else:
            self.logger.info('VALIDACION',
                            f'Columna de texto: {columna_requerimiento} ({vacios} vacíos de {total} filas)')
        
        self.logger.info('VALIDACION',
                        f"Columnas base encontradas: {mapeo_columnas}. Columna de texto: {columna_requerimiento}")
        
        # Limitar filas si es necesario
        if max_filas and len(df) > max_filas:
            df = df.head(max_filas)
            self.logger.warn('PROCESAMIENTO', 
                            f'Se limitará el procesamiento a {max_filas} filas por lote')
        
        total_filas = len(df)
        self.logger.info('PROCESAMIENTO', f'Total de filas a procesar: {total_filas}')
        
        # 3. ANÁLISIS IA
        resultados = []
        errores = []
        
        for idx, fila in df.iterrows():
            fila_idx = idx + 1
            texto = str(fila[columna_requerimiento]) if not pd.isna(fila[columna_requerimiento]) else ''
            
            if not texto.strip():
                self.logger.warn('IA', f'Fila {fila_idx}: texto vacío, omitiendo')
                errores.append(fila_idx)
                continue
            
            self.logger.debug('IA', f'Iniciando análisis de fila {fila_idx}/{total_filas}')
            
            try:
                resultado_ia = self.motor_ia.analizar_fila(texto, fila_idx)
                resultados.append({
                    'fila': fila_idx,
                    'texto_original': texto,
                    'resultado_ia': resultado_ia,
                    'datos_base': {
                        'fuente': fila.get(mapeo_columnas.get('fuente', '')),
                        'fecha': fila.get(mapeo_columnas.get('fecha', '')),
                        'hora': fila.get(mapeo_columnas.get('hora', '')),
                        'agente': fila.get(mapeo_columnas.get('agente', '')),
                        'tipo': fila.get(mapeo_columnas.get('tipo', ''))
                    }
                })
            except Exception as e:
                self.logger.error('IA', f'Fila {fila_idx} error: {str(e)}')
                errores.append(fila_idx)
        
        # 4. NORMALIZACIÓN
        campos_detectados = [r['resultado_ia'] for r in resultados]
        campos_unicos = self.normalizador.unificar_campos(campos_detectados)
        
        # 5. ESTRUCTURA FINAL
        salida_final = []
        for resultado in resultados:
            fila_idx = resultado['fila']
            campos = resultado['resultado_ia'].get('campos_detectados', {})
            
            # Normalizar nombres de campos
            campos_normalizados = {}
            for campo, valor in campos.items():
                campo_norm = self.normalizador.normalizar_nombre(campo)
                campos_normalizados[campo_norm] = valor
            
            objeto_final = {
                'id': str(uuid.uuid4()),
                'datos_base': resultado['datos_base'],
                'descripcion_cruda': resultado['texto_original'],
                'campos_dinamicos': campos_normalizados,
                'metadata_procesamiento': {
                    'timestamp_analisis': datetime.now().isoformat(),
                    'modelo_ia_utilizado': 'mock',
                    'confianza_extraccion': resultado['resultado_ia'].get('confianza', 0),
                    'campos_no_parseados': []
                }
            }
            salida_final.append(objeto_final)
        
        # 6. MÉTRICAS
        metricas = {
            'total_filas_procesadas': total_filas,
            'filas_con_error': len(errores),
            'filas_exitosas': len(resultados),
            'campos_dinamicos_unicos': len(campos_unicos),
            'tiempo_procesamiento': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'top_campos': sorted(
                [(campo, info['ocurrencias']) for campo, info in campos_unicos.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
        
        self.logger.info('SISTEMA', f'Proceso completado. Éxitos: {len(resultados)}/{total_filas}. Errores: {len(errores)}')
        
        return {
            'resultados': salida_final,
            'metricas': metricas,
            'campos_unicos': campos_unicos,
            'errores': errores
        }


# Función de conveniencia para uso rápido
def procesar_excel_con_ia(ruta_archivo: str, max_filas: int = 50) -> Dict:
    """
    Función principal para procesar archivo Excel con IA.
    """
    procesador = ProcesadorExcelIA(debug_mode=True)
    return procesador.procesar_archivo(ruta_archivo, max_filas)