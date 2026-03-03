import os
import tempfile
import pandas as pd
import sys
import json
import time
from datetime import datetime
from django.shortcuts import render, redirect
from django.views.generic import FormView, View, TemplateView, ListView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse

from .forms import SubirExcelForm, ValidarMapeoFormSet, ProcesarTodoForm
from .services import SugeridorCampos, EjecutorMigraciones, ProcesadorExcel
from .services_api import obtener_propiedades_externas
from .models import CampoDinamico, MapeoFuente, PropiedadRaw, MigracionPendiente
from .procesamiento_ia import ProcesadorExcelIA, LoggerDetallado, CargadorArchivo


# Utilidades de logging
def agregar_log(request, nivel, mensaje, datos=None):
    """Agrega un mensaje de log a la sesión para mostrar en la interfaz."""
    if 'logs' not in request.session:
        request.session['logs'] = []
    
    # Convertir datos a formato serializable
    datos_serializable = {}
    if datos:
        if isinstance(datos, dict):
            for key, value in datos.items():
                if hasattr(value, 'pk'):  # Es un objeto de modelo Django
                    datos_serializable[key] = {
                        'model': value.__class__.__name__,
                        'id': value.pk,
                        'str': str(value)
                    }
                elif isinstance(value, (list, tuple)):
                    datos_serializable[key] = [
                        {
                            'model': item.__class__.__name__,
                            'id': item.pk,
                            'str': str(item)
                        } if hasattr(item, 'pk') else item
                        for item in value
                    ]
                else:
                    datos_serializable[key] = value
        else:
            datos_serializable = str(datos)
    
    request.session['logs'].append({
        'nivel': nivel,
        'mensaje': mensaje,
        'datos': datos_serializable,
        'timestamp': datetime.now().isoformat()
    })
    request.session.modified = True


def cargar_dataframe_desde_json(df_json):
    """
    Carga un DataFrame desde JSON string de manera robusta.
    Maneja casos donde pd.read_json falla con FileNotFoundError.
    """
    import json
    import pandas as pd
    
    if not df_json:
        return None
    
    # Si ya es un DataFrame (no debería pasar)
    if isinstance(df_json, pd.DataFrame):
        return df_json
    
    # Si es un dict, convertirlo a JSON string
    if isinstance(df_json, dict):
        df_json = json.dumps(df_json)
    
    # Debug: registrar tipo y primeros caracteres
    import logging
    logger = logging.getLogger(__name__)
    try:
        logger.debug(f"cargar_dataframe_desde_json: tipo={type(df_json)}, len={len(df_json) if isinstance(df_json, str) else 'N/A'}")
        if isinstance(df_json, str) and len(df_json) > 200:
            logger.debug(f"Primeros 200 chars: {df_json[:200]}")
    except:
        pass
    
    # Intentar con pd.read_json primero
    try:
        return pd.read_json(df_json, orient='split')
    except FileNotFoundError as fnf:
        # pandas puede interpretar mal el JSON como ruta de archivo
        # Intentar cargar manualmente
        try:
            data = json.loads(df_json)
            if 'data' in data and 'columns' in data:
                return pd.DataFrame(data['data'], columns=data['columns'])
            else:
                # Intentar otros formatos
                return pd.read_json(df_json)
        except Exception as e:
            raise ValueError(f"No se pudo cargar DataFrame desde JSON (FileNotFoundError): {fnf}, {e}")
    except Exception as e:
        # Otro error, intentar cargar manualmente
        try:
            data = json.loads(df_json)
            if 'data' in data and 'columns' in data:
                return pd.DataFrame(data['data'], columns=data['columns'])
            else:
                raise e
        except:
            raise e


def obtener_logs(request):
    """Obtiene los logs de la sesión."""
    return request.session.get('logs', [])


def limpiar_logs(request):
    """Limpia los logs de la sesión."""
    if 'logs' in request.session:
        del request.session['logs']
        request.session.modified = True


# Vistas principales
class IngestasIndexView(TemplateView):
    template_name = 'ingestas/index.html'


class SubirExcelView(LoginRequiredMixin, FormView):
    template_name = 'ingestas/subir.html'
    form_class = SubirExcelForm
    success_url = '/ingestas/validar/'

    def form_valid(self, form):
        archivo = form.cleaned_data['archivo']
        nombre_fuente = form.cleaned_data['nombre_fuente']
        portal_origen = form.cleaned_data['portal_origen']
        
        # Crear archivo temporal con nombre único
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo.name)[1]) as tmp_file:
            # Escribir contenido del archivo subido
            for chunk in archivo.chunks():
                tmp_file.write(chunk)
            ruta_archivo = tmp_file.name
        
        # Verificar que el archivo existe
        if not os.path.exists(ruta_archivo):
            agregar_log(self.request, 'error', f'Archivo temporal no creado: {ruta_archivo}')
            messages.error(self.request, 'Error al guardar archivo temporal.')
            return self.form_invalid(form)
        
        # Leer archivo con pandas
        try:
            if archivo.name.lower().endswith('.csv'):
                # Intentar diferentes codificaciones comunes
                encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                df = None
                last_error = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(ruta_archivo, encoding=encoding)
                        agregar_log(self.request, 'debug', f'CSV leído con codificación: {encoding}')
                        break
                    except UnicodeDecodeError as e:
                        last_error = e
                        continue
                    except Exception as e:
                        last_error = e
                        continue
                
                if df is None:
                    # Último intento con encoding=None (pandas intentará inferir)
                    try:
                        df = pd.read_csv(ruta_archivo, encoding=None)
                    except Exception as e:
                        agregar_log(self.request, 'error', f'Error al leer CSV con cualquier codificación: {last_error}')
                        raise
            else:
                # Para archivos Excel
                df = pd.read_excel(ruta_archivo, engine='openpyxl')
                
        except Exception as e:
            # Limpiar archivo temporal
            try:
                os.unlink(ruta_archivo)
            except:
                pass
                
            agregar_log(self.request, 'error', f'Error al leer archivo: {e}')
            messages.error(self.request, f'Error al leer archivo: {str(e)[:100]}')
            return self.form_invalid(form)
        
        # Guardar datos en sesión
        self.request.session['df'] = df.to_json(orient='split')
        self.request.session['nombre_fuente'] = nombre_fuente
        self.request.session['portal_origen'] = portal_origen
        self.request.session['ruta_archivo'] = ruta_archivo
        
        # Limpiar logs anteriores
        limpiar_logs(self.request)
        
        agregar_log(self.request, 'info', f'Archivo {archivo.name} cargado exitosamente')
        agregar_log(self.request, 'debug', f'DataFrame shape: {df.shape}, columnas: {list(df.columns)}')
        
        messages.success(self.request, 'Archivo cargado exitosamente. Proceda a validar los mapeos.')
        return super().form_valid(form)


class ValidarMapeoView(LoginRequiredMixin, TemplateView):
    template_name = 'ingestas/validar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recuperar datos de sesión
        df_json = self.request.session.get('df')
        if not df_json:
            messages.error(self.request, 'No hay archivo cargado. Por favor, suba un archivo primero.')
            agregar_log(self.request, 'error', 'Intento de acceder a validar sin archivo cargado')
            return context
        
        # Cargar DataFrame usando función robusta
        try:
            df = cargar_dataframe_desde_json(df_json)
            agregar_log(self.request, 'debug', f'DataFrame cargado: {df.shape[0]} filas, {df.shape[1]} columnas')
        except Exception as e:
            agregar_log(self.request, 'error', f'Error al cargar DataFrame: {e}')
            messages.error(self.request, f'Error al procesar datos del archivo: {str(e)[:100]}')
            # Intentar limpiar la sesión para forzar nueva subida
            if 'df' in self.request.session:
                del self.request.session['df']
            return context
        
        nombre_fuente = self.request.session.get('nombre_fuente', 'Fuente desconocida')
        portal_origen = self.request.session.get('portal_origen', 'Portal desconocido')
        
        # Obtener sugerencias de campos
        try:
            sugeridor = SugeridorCampos()
            sugerencias = sugeridor.sugerir_campos(df)
            agregar_log(self.request, 'debug', f'Sugerencias generadas: {len(sugerencias.get("sugerencias", {}))} columnas')
        except Exception as e:
            agregar_log(self.request, 'error', f'Error al generar sugerencias de campos: {e}')
            sugerencias = {'sugerencias': {}, 'errores': [str(e)]}
        
        # Preparar formsets
        try:
            formset = ValidarMapeoFormSet(
                initial=[
                    {
                        'columna_origen': col,
                        'campo_bd': info['nombre_sugerido_bd'],
                        'titulo_display': info['titulo_display'],
                        'tipo_dato': info['tipo_dato_sugerido'],
                        'incluir': True,
                    }
                    for col, info in sugerencias.get('sugerencias', {}).items()
                ]
            )
            agregar_log(self.request, 'debug', f'Formset creado con {len(sugerencias.get("sugerencias", {}))} formularios')
        except Exception as e:
            agregar_log(self.request, 'error', f'Error al crear formset: {e}')
            formset = ValidarMapeoFormSet()
        
        # Preparar columnas_info para el template (compatibilidad)
        columnas_info = []
        campos_migrados = 0
        campos_pendientes = 0
        for col, info in sugerencias.get('sugerencias', {}).items():
            migrado = info.get('columna_existe_fisica', False)
            if migrado:
                campos_migrados += 1
            else:
                campos_pendientes += 1
            columnas_info.append({
                'nombre_columna_origen': col,
                'nombre_campo_bd': info['nombre_sugerido_bd'],
                'titulo_display': info['titulo_display'],
                'tipo_dato': info['tipo_dato_sugerido'],
                'migrado': migrado,
                'campo_existente': info.get('campo_existente'),
                'valores_muestra': df[col].dropna().head(3).tolist() if col in df.columns else [],
            })
        
        context.update({
            'nombre_fuente': nombre_fuente,
            'portal_origen': portal_origen,
            'formset': formset,
            'df_preview': df.head(10).to_html(classes='table table-striped'),
            'sugerencias': sugerencias,
            'logs': obtener_logs(self.request),
            'df_shape': df.shape,
            'columnas_info': columnas_info,
            'campos_migrados': campos_migrados,
            'campos_pendientes': campos_pendientes,
            'pendientes': campos_pendientes,
            'shape': df.shape,
        })
        return context


# Nueva vista para procesamiento con IA
class ProcesarConIAView(LoginRequiredMixin, View):
    """
    Vista que procesa un archivo Excel/CSV con IA para extraer campos dinámicos.
    """
    template_name = 'ingestas/procesar_ia.html'
    
    def get(self, request, *args, **kwargs):
        """Muestra formulario para subir archivo."""
        form = SubirExcelForm()
        logs = obtener_logs(request)
        return render(request, self.template_name, {'form': form, 'logs': logs})
    
    def post(self, request, *args, **kwargs):
        """Procesa el archivo subido con IA."""
        form = SubirExcelForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'Error en el formulario.')
            return render(request, self.template_name, {'form': form})
        
        archivo = form.cleaned_data['archivo']
        nombre_fuente = form.cleaned_data['nombre_fuente']
        portal_origen = form.cleaned_data['portal_origen']
        
        # Guardar archivo temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo.name)[1]) as tmp_file:
            for chunk in archivo.chunks():
                tmp_file.write(chunk)
            ruta_archivo = tmp_file.name
        
        try:
            # Cargar archivo para diagnóstico
            df_diagnostico = CargadorArchivo.cargar_archivo(ruta_archivo)
            agregar_log(request, 'INFO', f'Archivo cargado para diagnóstico. Filas: {len(df_diagnostico)}, Columnas: {len(df_diagnostico.columns)}')
            agregar_log(request, 'DEBUG', f'Columnas detectadas: {list(df_diagnostico.columns)}')
            
            # Detectar columnas estándar y de texto
            mapeo_columnas = CargadorArchivo.detectar_columnas_estandar(df_diagnostico)
            agregar_log(request, 'INFO', f'Columnas estándar detectadas: {mapeo_columnas}')
            
            columna_texto = CargadorArchivo.detectar_columna_texto_principal(df_diagnostico)
            if columna_texto:
                agregar_log(request, 'INFO', f'Columna de texto principal detectada: {columna_texto}')
            else:
                agregar_log(request, 'WARN', 'No se detectó columna de texto principal. Se intentará procesar con la primera columna de tipo texto.')
                # Listar tipos de columnas
                for col in df_diagnostico.columns:
                    dtype = df_diagnostico[col].dtype
                    agregar_log(request, 'DEBUG', f'Columna "{col}": tipo {dtype}, ejemplos: {df_diagnostico[col].dropna().head(2).tolist()}')
            
            # Inicializar procesador IA
            procesador = ProcesadorExcelIA(debug_mode=True)
            resultado = procesador.procesar_archivo(ruta_archivo, max_filas=50)
            
            # Guardar resultados en sesión para mostrar
            request.session['resultado_ia'] = resultado
            request.session['nombre_fuente'] = nombre_fuente
            request.session['portal_origen'] = portal_origen
            
            # Limpiar archivo temporal
            os.unlink(ruta_archivo)
            
            # Redirigir a página de resultados
            return redirect('ingestas:resultado_ia')
            
        except Exception as e:
            LoggerDetallado.error('VISTA_IA', f'Error procesando archivo: {str(e)}')
            agregar_log(request, 'ERROR', f'Error en procesamiento con IA: {str(e)}')
            messages.error(request, f'Error en procesamiento con IA: {str(e)}')
            # Limpiar archivo temporal si existe
            if os.path.exists(ruta_archivo):
                os.unlink(ruta_archivo)
            # Obtener logs para mostrar en template
            logs = obtener_logs(request)
            return render(request, self.template_name, {'form': form, 'logs': logs})


class ResultadoIAView(LoginRequiredMixin, TemplateView):
    """Muestra resultados del procesamiento con IA."""
    template_name = 'ingestas/resultado_ia.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resultado = self.request.session.get('resultado_ia')
        if not resultado:
            raise Http404('No hay resultados de procesamiento con IA.')
        
        context['resultado'] = resultado
        context['nombre_fuente'] = self.request.session.get('nombre_fuente')
        context['portal_origen'] = self.request.session.get('portal_origen')
        return context

    def post(self, request, *args, **kwargs):
        # Determinar qué acción se solicitó
        if 'importar_registros' in request.POST:
            # Importar registros directamente (sin validar formset)
            mapeos = request.session.get('mapeos')
            if not mapeos:
                agregar_log(request, 'error', 'No hay mapeos guardados en sesión. Valide los mapeos primero.')
                messages.error(request, 'No hay mapeos guardados. Valide los mapeos primero.')
                return self.get(request, *args, **kwargs)
            
            # Redirigir a ResultadoView para procesar la importación
            agregar_log(request, 'info', 'Redirigiendo a importación de registros con mapeos existentes.')
            return redirect('ingestas:resultado_ingesta')
        
        # Si se presionó "crear_campo", ignorar validación del formset (por ahora)
        if 'crear_campo' in request.POST:
            agregar_log(request, 'warning', 'Botón "Crear Campo" presionado, pero funcionalidad no implementada.')
            messages.warning(request, 'La creación individual de campos no está implementada. Use "Confirmar Mapeos".')
            return self.get(request, *args, **kwargs)
        
        # Validar formset (para confirmar_mapeos o cualquier otro submit dentro del formulario)
        formset = ValidarMapeoFormSet(request.POST)
        
        # Debug: verificar estado del formset
        agregar_log(request, 'debug', f'Formset total forms: {formset.total_form_count()}')
        agregar_log(request, 'debug', f'Formset initial forms: {formset.initial_form_count()}')
        agregar_log(request, 'debug', f'Formset management form: {formset.management_form}')
        if formset.management_form.errors:
            agregar_log(request, 'error', f'Management form errors: {formset.management_form.errors}')
        
        if formset.is_valid():
            mapeos = {}
            for form in formset:
                if form.cleaned_data.get('incluir'):
                    columna_origen = form.cleaned_data['columna_origen']
                    mapeos[columna_origen] = {
                        'campo_bd': form.cleaned_data['campo_bd'],
                        'titulo_display': form.cleaned_data['titulo_display'],
                        'tipo_dato': form.cleaned_data['tipo_dato'],
                    }
            
            request.session['mapeos'] = mapeos
            agregar_log(request, 'info', f'Mapeos confirmados: {len(mapeos)} columnas')
            messages.success(request, 'Mapeos validados exitosamente. Ahora puede importar los registros.')
            # No redirigimos, mostramos la misma página con mensaje de éxito
            return self.get(request, *args, **kwargs)
        
        # Log detallado de errores de validación
        errores = []
        for i, form in enumerate(formset):
            if not form.is_valid():
                errores.append(f'Formulario {i}: {form.errors}')
        
        # Agregar non_form_errors
        non_form_errors = formset.non_form_errors()
        if non_form_errors:
            errores.append(f'Non form errors: {non_form_errors}')
        
        agregar_log(request, 'error', f'Formset no válido. Errores: {errores}')
        agregar_log(request, 'debug', f'Datos POST recibidos: {dict(request.POST)}')
        messages.error(request, 'Error en la validación de mapeos. Revise los logs para más detalles.')
        return self.get(request, *args, **kwargs)


class ResultadoView(LoginRequiredMixin, TemplateView):
    template_name = 'ingestas/resultado.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recuperar datos de sesión
        df_json = self.request.session.get('df')
        mapeos = self.request.session.get('mapeos', {})
        nombre_fuente = self.request.session.get('nombre_fuente', 'Fuente desconocida')
        portal_origen = self.request.session.get('portal_origen', 'Portal desconocido')
        
        agregar_log(self.request, 'debug', f'ResultadoView: df_json tipo={type(df_json)}, mapeos={len(mapeos)}')
        
        if not df_json:
            agregar_log(self.request, 'error', 'ResultadoView: No hay df_json en sesión')
            messages.error(self.request, 'No hay datos suficientes para procesar (df_json faltante).')
            return context
        if not mapeos:
            agregar_log(self.request, 'error', 'ResultadoView: No hay mapeos en sesión')
            messages.error(self.request, 'No hay mapeos confirmados. Valide los mapeos primero.')
            return context
        
        try:
            df = cargar_dataframe_desde_json(df_json)
            agregar_log(self.request, 'debug', f'DataFrame cargado: {df.shape if df is not None else "None"}')
        except Exception as e:
            agregar_log(self.request, 'error', f'Error al cargar DataFrame en ResultadoView: {e}')
            messages.error(self.request, f'Error al cargar datos del archivo: {str(e)[:100]}')
            return context
        
        # Procesar Excel
        procesador = ProcesadorExcel()
        resultado = procesador.importar_datos(
            df=df,
            mapeos=mapeos,
            nombre_fuente=nombre_fuente,
            portal_origen=portal_origen,
            user=self.request.user
        )
        
        context.update({
            'resultado': resultado,
            'nombre_fuente': nombre_fuente,
            'portal_origen': portal_origen,
            'logs': obtener_logs(self.request),
        })
        return context


# Vista simple HTML para propiedades Propify (funciona sin reiniciar servidor)
def vista_propiedades_propify_directa(request):
    """Vista que genera HTML directamente para mostrar propiedades Propify."""
    from django.http import HttpResponse
    from propifai.models import PropifaiProperty
    from datetime import datetime
    
    try:
        # Obtener propiedades de Propifai
        propiedades = PropifaiProperty.objects.all()
        
        # Construir HTML directamente
        html = f'''
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Propiedades Propify - Vista Directa</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px; }}
                .propify-badge {{ background: #28a745; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }}
                .property-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }}
                .property-card {{ border: 1px solid #ddd; border-radius: 8px; padding: 15px; background: white; border-left: 4px solid #28a745; }}
                .property-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
                .property-type {{ font-weight: bold; font-size: 1.1rem; }}
                .property-price {{ color: #28a745; font-weight: bold; font-size: 1.2rem; }}
                .property-location {{ color: #666; margin-bottom: 10px; font-size: 0.9rem; }}
                .stats {{ background: #e9f7ef; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                .stat-item {{ display: inline-block; margin-right: 20px; font-size: 0.9rem; }}
                .stat-value {{ font-weight: bold; color: #28a745; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Propiedades Propify <span class="propify-badge">BASE DE DATOS PROPIFY</span></h1>
                
                <div class="stats">
                    <div class="stat-item">Total propiedades: <span class="stat-value">{propiedades.count()}</span></div>
                    <div class="stat-item">Con coordenadas: <span class="stat-value">{sum(1 for p in propiedades if p.latitude and p.longitude)}</span></div>
                    <div class="stat-item">Fecha: <span class="stat-value">{datetime.now().strftime("%d/%m/%Y %H:%M")}</span></div>
                </div>
        '''
        
        if propiedades.count() == 0:
            html += '''
                <div style="text-align: center; padding: 40px; color: #666;">
                    <h3>No se encontraron propiedades Propify</h3>
                    <p>La base de datos Propify está vacía o hay un error de conexión.</p>
                </div>
            '''
        else:
            html += '<div class="property-list">'
            for i, propiedad in enumerate(propiedades[:50]):  # Limitar a 50 para rendimiento
                lat = propiedad.latitude
                lng = propiedad.longitude
                precio = float(propiedad.price) if propiedad.price else None
                
                html += f'''
                    <div class="property-card">
                        <div class="property-header">
                            <div class="property-type">
                                {propiedad.tipo_propiedad or "Propiedad"}
                                {f"({propiedad.code})" if propiedad.code else ""}
                            </div>
                            <div class="property-price">
                                {f"${precio:,.0f}" if precio else "Consultar"}
                            </div>
                        </div>
                        <div class="property-location">
                            {propiedad.real_address or propiedad.exact_address or propiedad.department or "Ubicación no especificada"}
                        </div>
                        <div style="font-size: 0.9rem; color: #555;">
                            {f"{propiedad.bedrooms} hab." if propiedad.bedrooms else ""}
                            {f" • {propiedad.bathrooms} baños" if propiedad.bathrooms else ""}
                            {f" • {propiedad.built_area} m² const." if propiedad.built_area else ""}
                            {f" • {propiedad.land_area} m² terreno" if propiedad.land_area else ""}
                        </div>
                        <div style="font-size: 0.8rem; color: #888; margin-top: 10px;">
                            {f"Coordenadas: {lat}, {lng}" if lat and lng else "Sin coordenadas"}
                        </div>
                    </div>
                '''
            html += '</div>'
        
        html += f'''
                <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 8px; font-size: 0.9rem;">
                    <h3>Información técnica:</h3>
                    <p>Esta página muestra {propiedades.count()} propiedades directamente desde la base de datos Propify.</p>
                    <p><strong>URL de prueba:</strong> <a href="/ingestas/propiedades/?fuente_propify=propify">/ingestas/propiedades/?fuente_propify=propify</a></p>
                    <p><strong>Vista en el sistema principal:</strong> <a href="/ingestas/propiedades/">/ingestas/propiedades/</a> (deberían aparecer con badge verde "Propify")</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        return HttpResponse(html)
        
    except Exception as e:
        # Si hay error, mostrar página de error
        html = f'''
        <!DOCTYPE html>
        <html>
        <head><title>Error Propify</title></head>
        <body style="font-family: Arial; margin: 20px;">
            <h1 style="color: #dc3545;">Error cargando propiedades Propify</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p>Posibles causas:</p>
            <ul>
                <li>La base de datos Propify no está configurada correctamente</li>
                <li>El modelo PropifaiProperty no existe o tiene errores</li>
                <li>La conexión a la base de datos falló</li>
            </ul>
            <p>Verifique ejecutando: <code>python verificar_propify_directo.py</code></p>
        </body>
        </html>
        '''
        return HttpResponse(html, status=500)


# Vista temporal para mostrar solo propiedades Propify
def vista_propiedades_propify(request):
    """Vista temporal para mostrar propiedades de la base de datos Propify."""
    from propifai.models import PropifaiProperty
    
    # Obtener todas las propiedades Propify
    propiedades = PropifaiProperty.objects.all()
    
    # Convertir a formato compatible
    propiedades_compatibles = []
    propiedades_con_coordenadas = 0
    
    for propiedad in propiedades:
        # Extraer coordenadas
        lat = propiedad.latitude
        lng = propiedad.longitude
        
        if lat is not None and lng is not None:
            propiedades_con_coordenadas += 1
        
        # Crear diccionario compatible
        propiedad_dict = {
            'id': propiedad.id,
            'id_externo': propiedad.id,
            'es_externo': True,
            'es_propify': True,
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,
            'provincia': propiedad.province,
            'distrito': propiedad.district,
            'lat': lat,
            'lng': lng,
            'habitaciones': propiedad.bedrooms,
            'banios': propiedad.bathrooms,
            'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
            'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
            'primera_imagen': None,
            'imagen_principal': None,
            'url_propiedad': None,
            'fuente': 'Propify DB',
            'fecha_publicacion': propiedad.created_at,
            'fecha_ingesta': propiedad.created_at,
            'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
            'precio': float(propiedad.price) if propiedad.price else None,
            'titulo': f"{propiedad.title or 'Propiedad'} en {propiedad.department or ''}",
            'codigo': propiedad.code,
            'direccion': propiedad.real_address or propiedad.exact_address,
            'descripcion': propiedad.description,
        }
        propiedades_compatibles.append(propiedad_dict)
    
    context = {
        'propiedades_compatibles': propiedades_compatibles,
        'total_propiedades': len(propiedades_compatibles),
        'propiedades_con_coordenadas': propiedades_con_coordenadas,
        'titulo': 'Propiedades Propify - Vista Temporal',
    }
    
    return render(request, 'propifai/lista_propiedades_propify_clonado.html', context)


class LimpiarSesionView(View):
    def get(self, request, *args, **kwargs):
        # Eliminar archivo temporal si existe
        ruta_archivo = request.session.get('ruta_archivo')
        if ruta_archivo and os.path.exists(ruta_archivo):
            try:
                os.unlink(ruta_archivo)
                agregar_log(request, 'info', f'Archivo temporal eliminado: {ruta_archivo}')
            except Exception as e:
                agregar_log(request, 'warning', f'No se pudo eliminar archivo temporal: {e}')
        
        keys_to_remove = ['df', 'nombre_fuente', 'portal_origen', 'ruta_archivo', 'mapeos']
        for key in keys_to_remove:
            if key in request.session:
                del request.session[key]
        
        limpiar_logs(request)
        messages.success(request, 'Sesión limpiada exitosamente.')
        return redirect('ingestas:index')


class LimpiarLogsView(View):
    def get(self, request, *args, **kwargs):
        limpiar_logs(request)
        messages.success(request, 'Logs limpiados exitosamente.')
        return redirect(request.META.get('HTTP_REFERER', 'ingestas:index'))


# Helper para extraer imagen de atributos_extras
def extraer_imagen_propiedad(propiedad):
    """
    Extrae la URL de imagen de una propiedad.
    Busca en:
    1. Campo imagenes_propiedad (texto con URLs separadas por comas)
    2. Atributos extras (JSON) con campos que contengan 'imagen', 'foto', etc.
    Retorna la primera URL encontrada o None.
    """
    # 1. Buscar en imagenes_propiedad (campo de texto con URLs separadas por comas)
    if propiedad.imagenes_propiedad:
        imagenes = propiedad.imagenes_propiedad.split(',')
        for img in imagenes:
            img = img.strip()
            if img.startswith(('http://', 'https://', 'www.')):
                # Verificar extensiones de imagen comunes
                if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                    return img
                # Si no tiene extensión pero es URL, igual devolverla
                return img
            elif img:  # Si no es URL pero tiene texto, podría ser una ruta relativa
                return img
    
    # 2. Buscar en atributos_extras (JSON)
    atributos = propiedad.atributos_extras
    if not isinstance(atributos, dict):
        return None
    
    # Patrones de nombres de campo que podrían contener URLs de imagen
    patrones = ['imagen', 'foto', 'url_imagen', 'image', 'photo', 'img', 'url_foto', 'foto_url']
    
    for clave, valor in atributos.items():
        if not valor:
            continue
        # Verificar si la clave coincide con algún patrón
        clave_lower = clave.lower()
        for patron in patrones:
            if patron in clave_lower:
                # Verificar si el valor parece una URL
                valor_str = str(valor).strip()
                if valor_str.startswith(('http://', 'https://', 'www.')):
                    return valor_str
                # Si no es URL pero es texto, podría ser una ruta o nombre de archivo
                # En ese caso retornamos el valor para que el template decida
                return valor_str
    
    # 3. Si no se encuentra, buscar cualquier valor que parezca URL en atributos_extras
    for valor in atributos.values():
        if not valor:
            continue
        valor_str = str(valor).strip()
        if valor_str.startswith(('http://', 'https://', 'www.')):
            # Verificar extensiones de imagen comunes
            if any(ext in valor_str.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                return valor_str
    
    return None


# Nueva vista para listar propiedades en tarjetas
class ListaPropiedadesView(ListView):
    model = PropiedadRaw
    template_name = 'ingestas/lista_propiedades_rediseno.html'
    context_object_name = 'propiedades'
    paginate_by = 12
    
    def get_queryset(self):
        from django.db.models import Q
        queryset = super().get_queryset()
        
        # Obtener parámetros de filtro de la URL
        tipo_propiedad = self.request.GET.get('tipo_propiedad')
        precio_min = self.request.GET.get('precio_min')
        precio_max = self.request.GET.get('precio_max')
        departamento = self.request.GET.get('departamento')
        habitaciones = self.request.GET.get('habitaciones')
        banios = self.request.GET.get('banios')
        
        # Aplicar filtros con soporte para atributos_extras
        if tipo_propiedad:
            queryset = queryset.filter(
                Q(tipo_propiedad__icontains=tipo_propiedad) |
                Q(atributos_extras__tipo_propiedad__icontains=tipo_propiedad) |
                Q(atributos_extras__tipo__icontains=tipo_propiedad) |
                Q(atributos_extras__property_type__icontains=tipo_propiedad)
            )
        if precio_min:
            # Intentar convertir a número
            try:
                precio_min_float = float(precio_min)
                queryset = queryset.filter(
                    Q(precio_usd__gte=precio_min_float) |
                    Q(atributos_extras__precio_usd__gte=precio_min_float) |
                    Q(atributos_extras__precio__gte=precio_min_float) |
                    Q(atributos_extras__price__gte=precio_min_float)
                )
            except ValueError:
                pass
        if precio_max:
            try:
                precio_max_float = float(precio_max)
                queryset = queryset.filter(
                    Q(precio_usd__lte=precio_max_float) |
                    Q(atributos_extras__precio_usd__lte=precio_max_float) |
                    Q(atributos_extras__precio__lte=precio_max_float) |
                    Q(atributos_extras__price__lte=precio_max_float)
                )
            except ValueError:
                pass
        if departamento:
            queryset = queryset.filter(
                Q(departamento__icontains=departamento) |
                Q(atributos_extras__departamento__icontains=departamento) |
                Q(atributos_extras__department__icontains=departamento) |
                Q(atributos_extras__location__icontains=departamento)
            )
        if habitaciones:
            try:
                habitaciones_int = int(habitaciones)
                queryset = queryset.filter(
                    Q(numero_habitaciones__gte=habitaciones_int) |
                    Q(atributos_extras__numero_habitaciones__gte=habitaciones_int) |
                    Q(atributos_extras__habitaciones__gte=habitaciones_int) |
                    Q(atributos_extras__bedrooms__gte=habitaciones_int)
                )
            except ValueError:
                pass
        if banios:
            try:
                banios_int = int(banios)
                queryset = queryset.filter(
                    Q(numero_banos__gte=banios_int) |
                    Q(atributos_extras__numero_banos__gte=banios_int) |
                    Q(atributos_extras__banos__gte=banios_int) |
                    Q(atributos_extras__bathrooms__gte=banios_int)
                )
            except ValueError:
                pass
        
        # Ordenar por fecha de ingesta descendente
        return queryset.order_by('-fecha_ingesta')
    
    def paginate_queryset(self, queryset, page_size):
        """
        Sobrescribir la paginación para manejar todas_propiedades en lugar del queryset original.
        """
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        
        # Obtener propiedades de todas las fuentes
        todas_propiedades = self._obtener_todas_propiedades()
        
        # Crear paginador para todas_propiedades
        paginator = Paginator(todas_propiedades, page_size)
        page_number = self.request.GET.get('page') or 1
        
        try:
            page = paginator.page(page_number)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)
        
        # Guardar el paginador, la página y object_list en la instancia para usar en get_context_data
        self.paginator = paginator
        self.page = page
        self.object_list = list(page)  # ¡IMPORTANTE! Establecer object_list
        
        # Retornar la tupla requerida por Django: (paginator, page, object_list, is_paginated)
        return (paginator, page, self.object_list, page.has_other_pages())
    
    def _calcular_checkboxes(self):
        """
        Calcula los valores de los checkboxes basados en los parámetros GET.
        Devuelve una tupla (fuente_local, fuente_externa, fuente_propify)
        """
        # Obtener parámetros de filtro de checkboxes
        has_any_checkbox_param = any(
            key in self.request.GET
            for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
        )
        
        if not has_any_checkbox_param:
            # No hay parámetros de checkbox - mostrar todos por defecto
            fuente_local = True
            fuente_externa = True
            fuente_propify = True
        else:
            # Hay al menos un parámetro de checkbox - respetar solo los presentes
            fuente_local = 'fuente_local' in self.request.GET
            fuente_externa = 'fuente_externa' in self.request.GET
            fuente_propify = 'fuente_propify' in self.request.GET
        
        # FORZAR SIEMPRE mostrar Propify para debugging
        fuente_propify = True
        
        # DEBUG
        print(f"DEBUG _calcular_checkboxes:")
        print(f"  Parámetros GET: {dict(self.request.GET)}")
        print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
        print(f"  Resultado - Local: {fuente_local}, Externa: {fuente_externa}, Propify: {fuente_propify} (FORZADO)")
        
        return fuente_local, fuente_externa, fuente_propify
    
    def _obtener_todas_propiedades(self):
        """
        Obtiene todas las propiedades de todas las fuentes según los filtros de checkbox.
        OPTIMIZADO: Solo obtiene las fuentes necesarias basadas en los checkboxes seleccionados.
        Aplica filtros de tipo, departamento, precio, habitaciones, baños, etc.
        """
        # Calcular checkboxes PRIMERO para saber qué fuentes necesitamos
        fuente_local, fuente_externa, fuente_propify = self._calcular_checkboxes()
        
        print(f"DEBUG _obtener_todas_propiedades: Checkboxes - Local: {fuente_local}, Externa: {fuente_externa}, Propify: {fuente_propify}")
        
        # Obtener parámetros de filtro
        tipo_propiedad = self.request.GET.get('tipo_propiedad', '').strip()
        departamento = self.request.GET.get('departamento', '').strip()
        distrito = self.request.GET.get('distrito', '').strip()
        precio_min = self.request.GET.get('precio_min', '').strip()
        precio_max = self.request.GET.get('precio_max', '').strip()
        habitaciones = self.request.GET.get('habitaciones', '').strip()
        banios = self.request.GET.get('banios', '').strip()
        
        print(f"DEBUG _obtener_todas_propiedades: Filtros - tipo: '{tipo_propiedad}', depto: '{departamento}', distrito: '{distrito}', precio_min: '{precio_min}', precio_max: '{precio_max}', hab: '{habitaciones}', baños: '{banios}'")
        
        # Función para aplicar filtros a una lista de propiedades (diccionarios)
        def _aplicar_filtros(propiedades):
            if not propiedades:
                return propiedades
            
            filtradas = []
            for prop in propiedades:
                # Filtro por tipo de propiedad
                if tipo_propiedad:
                    prop_tipo = prop.get('tipo_propiedad', '')
                    if not prop_tipo or tipo_propiedad.lower() not in prop_tipo.lower():
                        continue
                
                # Filtro por departamento - busca tanto en índice como en nombre mapeado
                if departamento:
                    prop_depto = prop.get('departamento', '')
                    prop_depto_nombre = prop.get('departamento_nombre', '')
                    
                    # Verificar si el filtro coincide con el índice o con el nombre
                    depto_coincide = False
                    if prop_depto and departamento.lower() in str(prop_depto).lower():
                        depto_coincide = True
                    elif prop_depto_nombre and departamento.lower() in str(prop_depto_nombre).lower():
                        depto_coincide = True
                    
                    if not depto_coincide:
                        continue
                
                # Filtro por distrito - busca tanto en índice como en nombre mapeado
                if distrito:
                    prop_distrito = prop.get('distrito', '')
                    prop_distrito_nombre = prop.get('distrito_nombre', '')
                    
                    # Verificar si el filtro coincide con el índice o con el nombre
                    distrito_coincide = False
                    if prop_distrito and distrito.lower() in str(prop_distrito).lower():
                        distrito_coincide = True
                    elif prop_distrito_nombre and distrito.lower() in str(prop_distrito_nombre).lower():
                        distrito_coincide = True
                    
                    if not distrito_coincide:
                        continue
                
                # Filtro por precio mínimo
                if precio_min:
                    try:
                        precio_min_val = float(precio_min)
                        prop_precio = prop.get('precio_usd') or prop.get('precio')
                        if prop_precio is None or float(prop_precio) < precio_min_val:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                # Filtro por precio máximo
                if precio_max:
                    try:
                        precio_max_val = float(precio_max)
                        prop_precio = prop.get('precio_usd') or prop.get('precio')
                        if prop_precio is None or float(prop_precio) > precio_max_val:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                # Filtro por habitaciones (mínimo)
                if habitaciones:
                    try:
                        hab_min = int(habitaciones)
                        prop_hab = prop.get('habitaciones')
                        if prop_hab is None or int(prop_hab) < hab_min:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                # Filtro por baños (mínimo)
                if banios:
                    try:
                        banios_min = int(banios)
                        prop_banios = prop.get('banios')
                        if prop_banios is None or int(prop_banios) < banios_min:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                filtradas.append(prop)
            
            return filtradas
        
        # Inicializar listas vacías
        propiedades_externas = []
        propiedades_propifai_dict = []
        propiedades_locales_dict = []
        
        # Obtener solo las fuentes necesarias
        if fuente_externa:
            # Obtener propiedades externas de la API
            from ingestas.services_api import obtener_propiedades_externas
            propiedades_externas = obtener_propiedades_externas()
            print(f"DEBUG _obtener_todas_propiedades: Obtenidas {len(propiedades_externas)} propiedades externas")
            # Aplicar filtros
            propiedades_externas = _aplicar_filtros(propiedades_externas)
            print(f"DEBUG _obtener_todas_propiedades: Después de filtros externas: {len(propiedades_externas)}")
        
        if fuente_propify:
            # Obtener propiedades de Propifai (segunda base de datos)
            try:
                from propifai.models import PropifaiProperty
                print(f"DEBUG _obtener_todas_propiedades: Obteniendo propiedades de Propifai...")
                
                # Usar la base de datos 'propifai' explícitamente
                propiedades_propifai = list(PropifaiProperty.objects.using('propifai').all()[:100])  # Limitar a 100 para rendimiento
                print(f"DEBUG _obtener_todas_propiedades: Obtenidas {len(propiedades_propifai)} propiedades de la BD propifai")
                
                # Convertir a diccionarios
                for i, prop in enumerate(propiedades_propifai):
                    try:
                        prop_dict = self._convertir_propiedad_propifai_a_dict(prop)
                        propiedades_propifai_dict.append(prop_dict)
                        if i < 3:  # Log solo para las primeras 3
                            print(f"DEBUG _obtener_todas_propiedades: Propiedad {i+1} convertida - es_propify: {prop_dict.get('es_propify')}")
                    except Exception as e2:
                        print(f"DEBUG _obtener_todas_propiedades: Error convirtiendo propiedad {i+1}: {e2}")
                
                print(f"DEBUG _obtener_todas_propiedades: Total convertidas Propify: {len(propiedades_propifai_dict)}")
                # Aplicar filtros
                propiedades_propifai_dict = _aplicar_filtros(propiedades_propifai_dict)
                print(f"DEBUG _obtener_todas_propiedades: Después de filtros Propify: {len(propiedades_propifai_dict)}")
                
            except Exception as e:
                print(f"Error obteniendo propiedades de Propifai: {e}")
                import traceback
                traceback.print_exc()
        
        if fuente_local:
            # Obtener propiedades locales con filtros aplicados al queryset
            propiedades_locales = list(self.get_queryset())
            propiedades_locales_dict = [self._convertir_propiedad_local_a_dict(prop) for prop in propiedades_locales]
            print(f"DEBUG _obtener_todas_propiedades: Obtenidas {len(propiedades_locales_dict)} propiedades locales")
            # Aplicar filtros
            propiedades_locales_dict = _aplicar_filtros(propiedades_locales_dict)
            print(f"DEBUG _obtener_todas_propiedades: Después de filtros locales: {len(propiedades_locales_dict)}")
        
        # Preparar listas para intercalar
        listas_propiedades = []
        
        if fuente_local and propiedades_locales_dict:
            listas_propiedades.append(('local', propiedades_locales_dict))
        
        if fuente_externa and propiedades_externas:
            listas_propiedades.append(('externa', propiedades_externas))
        
        if fuente_propify and propiedades_propifai_dict:
            listas_propiedades.append(('propify', propiedades_propifai_dict))
        
        # Si solo hay una fuente, devolverla directamente (sin intercalar)
        if len(listas_propiedades) == 1:
            fuente, propiedades = listas_propiedades[0]
            print(f"DEBUG _obtener_todas_propiedades: Solo una fuente ({fuente}), devolviendo {len(propiedades)} propiedades directamente")
            
            # Agregar indicador de fuente
            todas_propiedades = []
            for prop in propiedades:
                prop_copy = prop.copy() if hasattr(prop, 'copy') else dict(prop)
                prop_copy['_fuente_original'] = fuente
                todas_propiedades.append(prop_copy)
            
            return todas_propiedades
        
        # Intercalar propiedades de diferentes fuentes (si hay más de una)
        todas_propiedades = []
        
        if listas_propiedades:
            # Encontrar la lista más larga
            max_len = max(len(propiedades) for _, propiedades in listas_propiedades)
            
            print(f"DEBUG _obtener_todas_propiedades: Intercalando {len(listas_propiedades)} fuentes, max_len: {max_len}")
            print(f"DEBUG _obtener_todas_propiedades: Listas a intercalar: {[(fuente, len(props)) for fuente, props in listas_propiedades]}")
            
            # Intercalar propiedades
            for i in range(max_len):
                for fuente, propiedades in listas_propiedades:
                    if i < len(propiedades):
                        # Agregar un indicador de fuente para debugging
                        prop = propiedades[i].copy() if hasattr(propiedades[i], 'copy') else dict(propiedades[i])
                        prop['_fuente_original'] = fuente
                        todas_propiedades.append(prop)
        
        print(f"DEBUG _obtener_todas_propiedades: Total propiedades a devolver: {len(todas_propiedades)}")
        return todas_propiedades
    
    def _convertir_propiedad_local_a_dict(self, propiedad):
        """Convierte una instancia de PropiedadRaw a diccionario con campos compatibles."""
        # Extraer imagen principal usando la función helper
        primera_imagen = extraer_imagen_propiedad(propiedad)
        
        # Si no hay imagen de la función helper, usar el campo imagenes_propiedad
        if not primera_imagen and propiedad.imagenes_propiedad:
            # El campo imagenes_propiedad es un texto con URLs separadas por comas
            imagenes = propiedad.imagenes_propiedad.split(',')
            if imagenes:
                primera_imagen = imagenes[0].strip()
        
        # Extraer coordenadas del campo coordenadas (formato "lat,lng")
        lat = None
        lng = None
        if propiedad.coordenadas:
            try:
                coords = propiedad.coordenadas.split(',')
                if len(coords) >= 2:
                    lat = float(coords[0].strip())
                    lng = float(coords[1].strip())
            except (ValueError, AttributeError):
                pass
        
        # Determinar si es una propiedad Remax (tiene oficina_remax o fuente_excel contiene "remax")
        es_remax = (
            (propiedad.oficina_remax and propiedad.oficina_remax.strip()) or
            (propiedad.fuente_excel and 'remax' in propiedad.fuente_excel.lower())
        )
        
        # Crear diccionario con todos los campos necesarios para la plantilla
        propiedad_dict = {
            'id': propiedad.id,
            'id_externo': propiedad.id,  # Para compatibilidad con propiedades externas
            'es_externo': False,
            'es_remax': es_remax,  # Nuevo campo para identificar propiedades Remax
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio_usd': propiedad.precio_usd,
            'departamento': propiedad.departamento,
            'provincia': propiedad.provincia,
            'distrito': propiedad.distrito,
            'lat': lat,
            'lng': lng,
            'habitaciones': propiedad.numero_habitaciones,  # Mapear a numero_habitaciones
            'banios': propiedad.numero_banos,  # Mapear a numero_banos
            'area_construida': propiedad.area_construida,
            'area_terreno': propiedad.area_terreno,
            'primera_imagen': primera_imagen,
            'imagen_principal': primera_imagen,
            'url_propiedad': propiedad.url_propiedad,
            'fuente': propiedad.fuente_excel or 'Local',  # Usar fuente_excel en lugar de fuente
            'fecha_publicacion': propiedad.fecha_publicacion,
            'fecha_ingesta': propiedad.fecha_ingesta,
            # Campos adicionales para compatibilidad
            'area': propiedad.area_construida or propiedad.area_terreno,
            'precio': propiedad.precio_usd,
            'titulo': f"{propiedad.tipo_propiedad or 'Propiedad'} en {propiedad.departamento or ''}",
        }
        return propiedad_dict
    
    def _convertir_propiedad_propifai_a_dict(self, propiedad):
        """Convierte una instancia de PropifaiProperty a diccionario con campos compatibles."""
        # Extraer coordenadas
        lat = propiedad.latitude
        lng = propiedad.longitude
        
        # Obtener nombres mapeados de ubicación
        departamento_nombre = propiedad.departamento_nombre if hasattr(propiedad, 'departamento_nombre') else propiedad.department
        provincia_nombre = propiedad.provincia_nombre if hasattr(propiedad, 'provincia_nombre') else propiedad.province
        distrito_nombre = propiedad.distrito_nombre if hasattr(propiedad, 'distrito_nombre') else propiedad.district
        
        # Crear diccionario con todos los campos necesarios para la plantilla
        propiedad_dict = {
            'id': propiedad.id,
            'id_externo': propiedad.id,
            'es_externo': True,
            'es_propify': True,  # Nueva bandera para identificar propiedades de Propifai
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,  # Índice original
            'departamento_nombre': departamento_nombre,  # Nombre mapeado
            'provincia': propiedad.province,  # Índice original
            'provincia_nombre': provincia_nombre,  # Nombre mapeado
            'distrito': propiedad.district,  # Índice original
            'distrito_nombre': distrito_nombre,  # Nombre mapeado
            'lat': lat,
            'lng': lng,
            'habitaciones': propiedad.bedrooms,
            'banios': propiedad.bathrooms,
            'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
            'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
            'primera_imagen': None,  # Propifai no tiene imágenes en este modelo básico
            'imagen_principal': None,
            'url_propiedad': None,
            'fuente': 'Propify DB',
            'fecha_publicacion': propiedad.created_at,
            'fecha_ingesta': propiedad.created_at,
            # Campos adicionales para compatibilidad
            'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
            'precio': float(propiedad.price) if propiedad.price else None,
            'titulo': f"{propiedad.title or 'Propiedad'} en {departamento_nombre or propiedad.department or ''}",
            'codigo': propiedad.code,
            'direccion': propiedad.real_address or propiedad.exact_address,
            'descripcion': propiedad.description,
            'ubicacion_completa': propiedad.ubicacion_completa if hasattr(propiedad, 'ubicacion_completa') else f"{distrito_nombre}, {provincia_nombre}, {departamento_nombre}",
        }
        return propiedad_dict
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar campos dinámicos para referencia
        context['campos_dinamicos'] = CampoDinamico.objects.all()
        
        # Obtener todas las propiedades según los filtros
        todas_propiedades = self._obtener_todas_propiedades()
        
        # Obtener propiedades externas y Propifai para los filtros
        from ingestas.services_api import obtener_propiedades_externas
        propiedades_externas = obtener_propiedades_externas()
        
        try:
            from propifai.models import PropifaiProperty
            propiedades_propifai = list(PropifaiProperty.objects.all()[:100])
            propiedades_propifai_dict = [self._convertir_propiedad_propifai_a_dict(prop) for prop in propiedades_propifai]
        except Exception as e:
            print(f"Error obteniendo propiedades de Propifai: {e}")
            propiedades_propifai_dict = []
        
        # Calcular conteos
        conteo_locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
        conteo_externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
        conteo_propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
        
        # Obtener valores de checkboxes usando el método común
        fuente_local, fuente_externa, fuente_propify = self._calcular_checkboxes()
        
        # DEBUG: Imprimir valores para diagnóstico (directo a consola)
        print(f"\n=== DEBUG get_context_data ===")
        print(f"  Parámetros GET: {dict(self.request.GET)}")
        print(f"  Checkboxes calculados - Local: {fuente_local}, Externa: {fuente_externa}, Propify: {fuente_propify}")
        print(f"  Conteos - Locales: {conteo_locales}, Externas: {conteo_externas}, Propify: {conteo_propify}")
        
        # Usar object_list (que ya está paginado) en lugar de todas_propiedades
        # object_list contiene la página actual de todas_propiedades gracias a paginate_queryset
        context['todas_propiedades'] = self.object_list  # Ya paginado
        context['todas_propiedades_completas'] = todas_propiedades  # Todas sin paginar
        context['total_propiedades'] = len(todas_propiedades)  # Total sin paginar
        context['conteo_locales'] = conteo_locales
        context['conteo_externas'] = conteo_externas
        context['conteo_propify'] = conteo_propify
        
        # Pasar todas las propiedades (sin serializar) para que json_script las serialice correctamente
        context['todas_propiedades_json'] = todas_propiedades
        
        # DEBUG: Verificar que las propiedades Propify estén en object_list
        propify_in_object_list = sum(1 for p in self.object_list if isinstance(p, dict) and p.get('es_propify'))
        print(f"  Propify en object_list: {propify_in_object_list} de {len(self.object_list)}")
        print(f"=== FIN DEBUG ===\n")
        
        # Agregar opciones para filtros (combinando fuentes)
        queryset = self.get_queryset()
        
        # Tipos de propiedad (locales + externas + propifai)
        tipos_locales = queryset.exclude(tipo_propiedad__isnull=True).exclude(tipo_propiedad='').values_list('tipo_propiedad', flat=True).distinct()
        tipos_externos = {prop.get('tipo_propiedad') for prop in propiedades_externas if prop.get('tipo_propiedad')}
        tipos_propifai = {prop.get('tipo_propiedad') for prop in propiedades_propifai_dict if prop.get('tipo_propiedad')}
        todos_tipos = sorted(set(list(tipos_locales) + list(tipos_externos) + list(tipos_propifai)))
        context['tipos_propiedad'] = todos_tipos
        
        # Departamentos (locales + externas + propifai)
        deptos_locales = queryset.exclude(departamento__isnull=True).exclude(departamento='').values_list('departamento', flat=True).distinct()
        deptos_externos = {prop.get('departamento') for prop in propiedades_externas if prop.get('departamento')}
        
        # Para Propifai, usar nombres mapeados en lugar de índices
        deptos_propifai = set()
        for prop in propiedades_propifai_dict:
            depto = prop.get('departamento')
            depto_nombre = prop.get('departamento_nombre')
            # Preferir el nombre mapeado, pero si no existe, usar el índice
            if depto_nombre and depto_nombre != str(depto):
                deptos_propifai.add(depto_nombre)
            elif depto:
                deptos_propifai.add(str(depto))
        
        todos_deptos = sorted(set(list(deptos_locales) + list(deptos_externos) + list(deptos_propifai)))
        context['departamentos'] = todos_deptos
        
        # Distritos (locales + externas + propifai)
        distritos_locales = queryset.exclude(distrito__isnull=True).exclude(distrito='').values_list('distrito', flat=True).distinct()
        distritos_externos = {prop.get('distrito') for prop in propiedades_externas if prop.get('distrito')}
        
        # Para Propifai, usar nombres mapeados en lugar de índices
        distritos_propifai = set()
        for prop in propiedades_propifai_dict:
            distrito = prop.get('distrito')
            distrito_nombre = prop.get('distrito_nombre')
            # Preferir el nombre mapeado, pero si no existe, usar el índice
            if distrito_nombre and distrito_nombre != str(distrito):
                distritos_propifai.add(distrito_nombre)
            elif distrito:
                distritos_propifai.add(str(distrito))
        
        todos_distritos = sorted(set(list(distritos_locales) + list(distritos_externos) + list(distritos_propifai)))
        context['distritos'] = todos_distritos
        
        # Fuentes disponibles para filtro
        context['fuentes_disponibles'] = ['Local', 'Externa', 'Propify']
        context['fuente_local_checked'] = fuente_local
        context['fuente_externa_checked'] = fuente_externa
        context['fuente_propify_checked'] = fuente_propify
        
        # DEBUG: Verificar que las variables se están agregando al contexto
        print(f"  Contexto DEBUG - fuente_local_checked: {context.get('fuente_local_checked')}")
        print(f"  Contexto DEBUG - fuente_externa_checked: {context.get('fuente_externa_checked')}")
        print(f"  Contexto DEBUG - fuente_propify_checked: {context.get('fuente_propify_checked')}")
        
        return context


# Vista para listar propiedades con filtros avanzados
class PropiedadesFiltradasView(ListView):
    model = PropiedadRaw
    template_name = 'ingestas/lista_propiedades_rediseno.html'
    context_object_name = 'propiedades'
    paginate_by = 12
    
    def get_queryset(self):
        from django.db.models import Q
        queryset = super().get_queryset()
        
        # Obtener parámetros de filtro de la URL
        tipo_propiedad = self.request.GET.get('tipo_propiedad')
        precio_min = self.request.GET.get('precio_min')
        precio_max = self.request.GET.get('precio_max')
        ubicacion = self.request.GET.get('ubicacion')
        metros_min = self.request.GET.get('metros_min')
        metros_max = self.request.GET.get('metros_max')
        habitaciones = self.request.GET.get('habitaciones')
        banos = self.request.GET.get('banos')
        fuente_excel = self.request.GET.get('fuente_excel')
        
        # Aplicar filtros con soporte para atributos_extras
        if tipo_propiedad:
            queryset = queryset.filter(
                Q(tipo_propiedad__icontains=tipo_propiedad) |
                Q(atributos_extras__tipo_propiedad__icontains=tipo_propiedad) |
                Q(atributos_extras__tipo__icontains=tipo_propiedad) |
                Q(atributos_extras__property_type__icontains=tipo_propiedad)
            )
        if precio_min:
            # Intentar convertir a número
            try:
                precio_min_float = float(precio_min)
                queryset = queryset.filter(
                    Q(precio_usd__gte=precio_min_float) |
                    Q(atributos_extras__precio_usd__gte=precio_min_float) |
                    Q(atributos_extras__precio__gte=precio_min_float) |
                    Q(atributos_extras__price__gte=precio_min_float)
                )
            except ValueError:
                pass
        if precio_max:
            try:
                precio_max_float = float(precio_max)
                queryset = queryset.filter(
                    Q(precio_usd__lte=precio_max_float) |
                    Q(atributos_extras__precio_usd__lte=precio_max_float) |
                    Q(atributos_extras__precio__lte=precio_max_float) |
                    Q(atributos_extras__price__lte=precio_max_float)
                )
            except ValueError:
                pass
        if ubicacion:
            queryset = queryset.filter(
                Q(ubicacion__icontains=ubicacion) |
                Q(atributos_extras__ubicacion__icontains=ubicacion) |
                Q(atributos_extras__location__icontains=ubicacion) |
                Q(atributos_extras__direccion__icontains=ubicacion)
            )
        if metros_min:
            try:
                metros_min_float = float(metros_min)
                queryset = queryset.filter(
                    Q(metros_cuadrados__gte=metros_min_float) |
                    Q(atributos_extras__metros_cuadrados__gte=metros_min_float) |
                    Q(atributos_extras__metros__gte=metros_min_float) |
                    Q(atributos_extras__area__gte=metros_min_float)
                )
            except ValueError:
                pass
        if metros_max:
            try:
                metros_max_float = float(metros_max)
                queryset = queryset.filter(
                    Q(metros_cuadrados__lte=metros_max_float) |
                    Q(atributos_extras__metros_cuadrados__lte=metros_max_float) |
                    Q(atributos_extras__metros__lte=metros_max_float) |
                    Q(atributos_extras__area__lte=metros_max_float)
                )
            except ValueError:
                pass
        if habitaciones:
            try:
                habitaciones_int = int(habitaciones)
                queryset = queryset.filter(
                    Q(habitaciones=habitaciones_int) |
                    Q(atributos_extras__habitaciones=habitaciones_int) |
                    Q(atributos_extras__rooms=habitaciones_int) |
                    Q(atributos_extras__bedrooms=habitaciones_int)
                )
            except ValueError:
                pass
        if banos:
            try:
                banos_int = int(banos)
                queryset = queryset.filter(
                    Q(banos=banos_int) |
                    Q(atributos_extras__banos=banos_int) |
                    Q(atributos_extras__bathrooms=banos_int) |
                    Q(atributos_extras__banios=banos_int)
                )
            except ValueError:
                pass
        if fuente_excel:
            queryset = queryset.filter(fuente_excel__icontains=fuente_excel)
        
        # Ordenar por fecha de ingesta descendente
        queryset = queryset.order_by('-fecha_ingesta')
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar campos dinámicos para referencia
        context['campos_dinamicos'] = CampoDinamico.objects.all()
        # Obtener valores únicos para los dropdowns de filtros
        context['tipos_propiedad'] = PropiedadRaw.objects.values_list('tipo_propiedad', flat=True).distinct().exclude(tipo_propiedad__isnull=True).exclude(tipo_propiedad='')
        context['fuentes'] = PropiedadRaw.objects.values_list('fuente_excel', flat=True).distinct().exclude(fuente_excel__isnull=True).exclude(fuente_excel='')
        # Pasar parámetros actuales para mantener filtros en la paginación
        context['parametros_filtro'] = self.request.GET.copy()
        if 'page' in context['parametros_filtro']:
            del context['parametros_filtro']['page']
        return context


# Vista para detalle de propiedad
class DetallePropiedadView(DetailView):
    model = PropiedadRaw
    template_name = 'ingestas/detalle_propiedad.html'
    context_object_name = 'propiedad'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        propiedad = self.object
        
        # Extraer imagen
        context['imagen_url'] = extraer_imagen_propiedad(propiedad)
        
        # Separar atributos extras para mostrar mejor
        atributos = propiedad.atributos_extras
        if isinstance(atributos, dict):
            # Ordenar alfabéticamente
            context['atributos_ordenados'] = sorted(atributos.items())
        else:
            context['atributos_ordenados'] = []
        
        return context


# Vista para editar propiedad
from django.views.generic.edit import UpdateView
from .forms import PropiedadRawForm

class EditarPropiedadView(UpdateView):
    model = PropiedadRaw
    form_class = PropiedadRawForm
    template_name = 'ingestas/editar_propiedad.html'
    context_object_name = 'propiedad'
    
    def get_success_url(self):
        from django.urls import reverse
        return reverse('ingestas:detalle_propiedad', kwargs={'pk': self.object.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        propiedad = self.object
        # Extraer imagen para mostrar en el template
        context['imagen_url'] = extraer_imagen_propiedad(propiedad)
        return context


# API para crear propiedad desde el formulario modal
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json

@method_decorator(csrf_exempt, name='dispatch')
class CrearPropiedadAPIView(View):
    """API para crear una nueva propiedad desde el formulario modal."""
    
    def _parse_decimal(self, value):
        """Convierte un valor a Decimal o None si está vacío."""
        if value is None or value == '':
            return None
        try:
            from decimal import Decimal
            return Decimal(str(value))
        except:
            return None
    
    def _parse_int(self, value):
        """Convierte un valor a entero o None si está vacío."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except:
            return None
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Mapear campos del formulario al modelo PropiedadRaw
            propiedad = PropiedadRaw()
            
            # Campos básicos
            propiedad.tipo_propiedad = data.get('tipo_propiedad')
            propiedad.descripcion = data.get('descripcion')
            propiedad.precio_usd = self._parse_decimal(data.get('precio_usd'))
            propiedad.coordenadas = f"{data.get('lat')}, {data.get('lng')}" if data.get('lat') and data.get('lng') else None
            propiedad.departamento = data.get('departamento')
            propiedad.provincia = data.get('provincia')
            propiedad.distrito = data.get('distrito')
            propiedad.area_construida = self._parse_decimal(data.get('area_construida'))
            propiedad.area_terreno = self._parse_decimal(data.get('area_terreno'))
            propiedad.numero_pisos = self._parse_int(data.get('numero_pisos'))
            propiedad.numero_habitaciones = self._parse_int(data.get('numero_habitaciones'))
            propiedad.numero_banos = self._parse_int(data.get('numero_banos'))
            propiedad.numero_cocheras = self._parse_int(data.get('numero_cocheras'))
            propiedad.agente_inmobiliario = data.get('agente_inmobiliario')
            propiedad.imagenes_propiedad = data.get('imagenes_propiedad')
            propiedad.id_propiedad = data.get('id_propiedad')
            propiedad.fecha_publicacion = data.get('fecha_publicacion') or None
            propiedad.antiguedad = data.get('antiguedad')
            propiedad.servicio_agua = 'Sí' if data.get('servicio_agua') else 'No'
            propiedad.energia_electrica = 'Sí' if data.get('energia_electrica') else 'No'
            propiedad.servicio_drenaje = 'Sí' if data.get('servicio_drenaje') else 'No'
            propiedad.servicio_gas = 'Sí' if data.get('servicio_gas') else 'No'
            propiedad.email_agente = data.get('email_agente')
            propiedad.telefono_agente = data.get('telefono_agente')
            propiedad.oficina_remax = data.get('oficina_remax')
            propiedad.estado_propiedad = data.get('estado_propiedad')
            propiedad.fecha_venta = data.get('fecha_venta') or None
            propiedad.precio_final_venta = self._parse_decimal(data.get('precio_final_venta'))
            propiedad.portal = data.get('portal')
            propiedad.fuente_excel = 'manual'  # Fuente manual desde formulario
            
            # Guardar la propiedad
            propiedad.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Propiedad creada exitosamente',
                'id': propiedad.id
            }, status=201)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)