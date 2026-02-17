import os
import tempfile
import pandas as pd
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.views.generic import FormView, View, TemplateView, ListView, DetailView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse

from .forms import SubirExcelRequerimientoForm, ValidarMapeoRequerimientoFormSet, ProcesarTodoRequerimientoForm
from .models import CampoDinamicoRequerimiento, MapeoFuenteRequerimiento, RequerimientoRaw, MigracionPendienteRequerimiento


# Utilidades de logging
def agregar_log_requerimiento(request, nivel, mensaje, datos=None):
    """Agrega un mensaje de log a la sesión para mostrar en la interfaz."""
    if 'logs_requerimiento' not in request.session:
        request.session['logs_requerimiento'] = []
    
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
    
    request.session['logs_requerimiento'].append({
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
                return pd.DataFrame(data)
        except Exception as e:
            raise ValueError(f"No se pudo cargar DataFrame desde JSON: {e}")
    except Exception as e:
        raise ValueError(f"Error al leer JSON: {e}")


def limpiar_logs_requerimiento(request):
    """Limpia los logs de requerimiento de la sesión."""
    if 'logs_requerimiento' in request.session:
        del request.session['logs_requerimiento']
        request.session.modified = True


class SubirExcelRequerimientoView(LoginRequiredMixin, FormView):
    template_name = 'requerimientos/subir.html'
    form_class = SubirExcelRequerimientoForm
    success_url = '/requerimientos/validar/'

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
            agregar_log_requerimiento(self.request, 'error', f'Archivo temporal no creado: {ruta_archivo}')
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
                        agregar_log_requerimiento(self.request, 'debug', f'CSV leído con codificación: {encoding}')
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
                        agregar_log_requerimiento(self.request, 'error', f'Error al leer CSV con cualquier codificación: {last_error}')
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
                
            agregar_log_requerimiento(self.request, 'error', f'Error al leer archivo: {e}')
            messages.error(self.request, f'Error al leer archivo: {str(e)[:100]}')
            return self.form_invalid(form)
        
        # Guardar datos en sesión
        self.request.session['df_requerimiento'] = df.to_json(orient='split')
        self.request.session['nombre_fuente_requerimiento'] = nombre_fuente
        self.request.session['portal_origen_requerimiento'] = portal_origen
        self.request.session['ruta_archivo_requerimiento'] = ruta_archivo
        
        # Limpiar logs anteriores
        limpiar_logs_requerimiento(self.request)
        
        agregar_log_requerimiento(self.request, 'info', f'Archivo {archivo.name} cargado exitosamente')
        agregar_log_requerimiento(self.request, 'debug', f'DataFrame shape: {df.shape}, columnas: {list(df.columns)}')
        
        messages.success(self.request, 'Archivo cargado exitosamente. Proceda a validar los mapeos.')
        return super().form_valid(form)


class ValidarMapeoRequerimientoView(LoginRequiredMixin, TemplateView):
    template_name = 'requerimientos/validar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recuperar datos de sesión
        df_json = self.request.session.get('df_requerimiento')
        if not df_json:
            messages.error(self.request, 'No hay archivo cargado. Por favor, suba un archivo primero.')
            agregar_log_requerimiento(self.request, 'error', 'Intento de acceder a validar sin archivo cargado')
            return context
        
        # Cargar DataFrame usando función robusta
        try:
            df = cargar_dataframe_desde_json(df_json)
        except Exception as e:
            messages.error(self.request, f'Error al cargar datos: {e}')
            agregar_log_requerimiento(self.request, 'error', f'Error al cargar DataFrame: {e}')
            return context
        
        # Obtener sugerencias de campos
        from .services import SugeridorCamposRequerimiento
        sugerencias = SugeridorCamposRequerimiento.sugerir_campos(df)
        
        # Preparar datos para el template
        preview = df.head(5).to_dict('records')
        columnas = []
        for col in df.columns:
            sugerencia = next((s for s in sugerencias if s['nombre_columna'] == col), None)
            columnas.append({
                'nombre': col,
                'sugerencia_bd': sugerencia['nombre_sugerido'] if sugerencia else col.lower().replace(' ', '_'),
                'sugerencia_titulo': sugerencia['titulo_display'] if sugerencia else col,
                'sugerencia_tipo': sugerencia['tipo_dato'] if sugerencia else 'VARCHAR'
            })
        
        context.update({
            'preview': preview,
            'columnas': columnas,
            'shape': df.shape,
            'formset': ValidarMapeoRequerimientoFormSet(initial=[
                {
                    'columna_origen': col['nombre'],
                    'campo_bd': col['sugerencia_bd'],
                    'titulo_display': col['sugerencia_titulo'],
                    'tipo_dato': col['sugerencia_tipo'],
                    'incluir': True,
                    'crear_campo': False
                }
                for col in columnas
            ])
        })
        return context

    def post(self, request, *args, **kwargs):
        formset = ValidarMapeoRequerimientoFormSet(request.POST)
        
        if formset.is_valid():
            mapeos = {}
            campos_a_crear = []
            
            for form in formset:
                if form.cleaned_data.get('incluir', False):
                    columna_origen = form.cleaned_data['columna_origen']
                    campo_bd = form.cleaned_data['campo_bd']
                    titulo_display = form.cleaned_data['titulo_display']
                    tipo_dato = form.cleaned_data['tipo_dato']
                    crear_campo = form.cleaned_data.get('crear_campo', False)
                    
                    mapeos[columna_origen] = {
                        'campo_bd': campo_bd,
                        'titulo_display': titulo_display,
                        'tipo_dato': tipo_dato
                    }
                    
                    if crear_campo:
                        campos_a_crear.append({
                            'nombre_campo_bd': campo_bd,
                            'titulo_display': titulo_display,
                            'tipo_dato': tipo_dato
                        })
            
            # Guardar mapeos en sesión
            request.session['mapeos_requerimiento'] = mapeos
            request.session['campos_a_crear_requerimiento'] = campos_a_crear
            
            # Crear campos dinámicos si se solicitó
            if campos_a_crear:
                from .services import EjecutorMigracionesRequerimiento
                for campo in campos_a_crear:
                    try:
                        EjecutorMigracionesRequerimiento.ejecutar_migracion(
                            campo['nombre_campo_bd'],
                            campo['titulo_display'],
                            campo['tipo_dato'],
                            request.user
                        )
                        agregar_log_requerimiento(request, 'success', f'Campo dinámico creado: {campo["nombre_campo_bd"]}')
                    except Exception as e:
                        agregar_log_requerimiento(request, 'error', f'Error al crear campo {campo["nombre_campo_bd"]}: {e}')
            
            messages.success(request, 'Mapeos validados exitosamente. Proceda a procesar los datos.')
            return redirect('requerimientos:procesar')
        else:
            messages.error(request, 'Error en el formulario. Revise los datos.')
            return self.get(request, *args, **kwargs)


class ProcesarRequerimientoView(LoginRequiredMixin, TemplateView):
    template_name = 'requerimientos/procesar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recuperar datos de sesión
        df_json = self.request.session.get('df_requerimiento')
        nombre_fuente = self.request.session.get('nombre_fuente_requerimiento')
        portal_origen = self.request.session.get('portal_origen_requerimiento')
        mapeos = self.request.session.get('mapeos_requerimiento', {})
        
        if not df_json or not mapeos:
            messages.error(self.request, 'No hay datos para procesar. Complete la validación primero.')
            return context
        
        # Cargar DataFrame
        try:
            df = cargar_dataframe_desde_json(df_json)
        except Exception as e:
            messages.error(self.request, f'Error al cargar datos: {e}')
            return context
        
        # Preparar vista previa de procesamiento
        preview_rows = []
        for idx, row in df.head(3).iterrows():
            preview_row = {}
            for col_orig, mapeo in mapeos.items():
                if col_orig in df.columns:
                    preview_row[mapeo['campo_bd']] = row[col_orig]
            preview_rows.append(preview_row)
        
        context.update({
            'nombre_fuente': nombre_fuente,
            'portal_origen': portal_origen,
            'total_filas': len(df),
            'total_campos': len(mapeos),
            'preview_rows': preview_rows,
            'form': ProcesarTodoRequerimientoForm()
        })
        return context

    def post(self, request, *args, **kwargs):
        form = ProcesarTodoRequerimientoForm(request.POST)
        
        if form.is_valid() and form.cleaned_data['confirmar']:
            # Importar datos a la base de datos
            from .services import ProcesadorExcelRequerimiento
            
            df_json = request.session.get('df_requerimiento')
            nombre_fuente = request.session.get('nombre_fuente_requerimiento')
            portal_origen = request.session.get('portal_origen_requerimiento')
            mapeos = request.session.get('mapeos_requerimiento', {})
            
            try:
                df = cargar_dataframe_desde_json(df_json)
                resultado = ProcesadorExcelRequerimiento.importar_datos(
                    df, mapeos, nombre_fuente, portal_origen, request.user
                )
                
                messages.success(request, f'Importación completada: {resultado["importados"]} requerimientos importados.')
                agregar_log_requerimiento(request, 'success', f'Importación completada: {resultado}')
                
                # Limpiar sesión
                for key in ['df_requerimiento', 'nombre_fuente_requerimiento', 
                           'portal_origen_requerimiento', 'mapeos_requerimiento',
                           'campos_a_crear_requerimiento']:
                    if key in request.session:
                        del request.session[key]
                
                return redirect('requerimientos:lista')
                
            except Exception as e:
                messages.error(request, f'Error durante la importación: {e}')
                agregar_log_requerimiento(request, 'error', f'Error en importación: {e}')
                return self.get(request, *args, **kwargs)
        else:
            messages.error(request, 'Debe confirmar el procesamiento.')
            return self.get(request, *args, **kwargs)


class ListaRequerimientosView(ListView):
    model = RequerimientoRaw
    template_name = 'requerimientos/lista.html'
    paginate_by = 20
    context_object_name = 'requerimientos'

    def get_queryset(self):
        queryset = super().get_queryset()
        # Aquí se pueden agregar filtros si es necesario
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total'] = RequerimientoRaw.objects.count()
        return context


class DetalleRequerimientoView(DetailView):
    model = RequerimientoRaw
    template_name = 'requerimientos/detalle.html'
    context_object_name = 'requerimiento'


class AnalisisInteligenteView(LoginRequiredMixin, View):
    """Vista para análisis inteligente de columnas de texto usando DeepSeek API."""
    
    def post(self, request, *args, **kwargs):
        import json
        import traceback
        from django.http import JsonResponse
        from .services import ExtractorInteligenteRequerimientos
        
        try:
            # Intentar parsear JSON si existe
            if request.content_type == 'application/json':
                try:
                    data = json.loads(request.body)
                    columna = data.get('columna')
                    datos_muestra = data.get('datos_muestra', [])
                    campo_bd = data.get('campo_bd', '')
                except json.JSONDecodeError:
                    return JsonResponse({'estado': 'error', 'mensaje': 'JSON inválido'}, status=400)
            else:
                # Fallback a POST tradicional
                columna = request.POST.get('columna')
                datos_muestra = request.POST.getlist('datos_muestra[]')
                campo_bd = request.POST.get('campo_bd', '')
            
            if not columna and not datos_muestra:
                return JsonResponse({'estado': 'error', 'mensaje': 'Se requiere columna o datos de muestra'}, status=400)
            
            # Si hay datos de muestra, analizar con IA
            if datos_muestra:
                # Unir muestras para análisis
                texto_ejemplo = ' '.join([str(d) for d in datos_muestra if d])
                if not texto_ejemplo.strip():
                    return JsonResponse({'estado': 'error', 'mensaje': 'Los datos de muestra están vacíos'})
                
                try:
                    datos_extraidos = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto_ejemplo)
                    sugerencia = "Se detectaron los siguientes campos en el texto: " + ", ".join(datos_extraidos.keys()) if datos_extraidos else "No se detectaron campos estructurados."
                    
                    # Generar lista de campos dinámicos sugeridos
                    campos_dinamicos = []
                    for key, value in datos_extraidos.items():
                        tipo = 'texto' if isinstance(value, str) else 'numero' if isinstance(value, (int, float)) else 'booleano' if isinstance(value, bool) else 'texto'
                        campos_dinamicos.append({
                            'nombre': key,
                            'tipo': tipo,
                            'descripcion': f'Extraído del texto: {value[:50]}...' if isinstance(value, str) and len(value) > 50 else f'Valor: {value}'
                        })
                    
                    return JsonResponse({
                        'estado': 'ok',
                        'sugerencia': sugerencia,
                        'datos_extraidos': datos_extraidos,
                        'campos_dinamicos': campos_dinamicos,
                        'columna': columna,
                        'campo_bd': campo_bd
                    })
                except Exception as e:
                    return JsonResponse({'estado': 'error', 'mensaje': f'Error en análisis IA: {str(e)}', 'traceback': traceback.format_exc()}, status=500)
            
            # Si hay columna pero no hay DataFrame en sesión, error
            if 'df_requerimiento' not in request.session:
                return JsonResponse({'estado': 'error', 'mensaje': 'No hay datos cargados para analizar'}, status=400)
            
            # Recuperar DataFrame de la sesión usando la función robusta
            df = cargar_dataframe_desde_json(request.session['df_requerimiento'])
            if df is None:
                return JsonResponse({'estado': 'error', 'mensaje': 'No se pudo cargar los datos desde la sesión'}, status=400)
            
            if columna not in df.columns:
                return JsonResponse({'estado': 'error', 'mensaje': f'Columna "{columna}" no encontrada'}, status=400)
            
            # Procesar la columna
            try:
                resultado = ExtractorInteligenteRequerimientos.procesar_columna_texto(df, columna)
                return JsonResponse({
                    'estado': 'ok',
                    'tipo': 'columna',
                    'columna': columna,
                    'resultado': resultado,
                    'mensaje': 'Análisis de columna completado'
                })
            except Exception as e:
                return JsonResponse({'estado': 'error', 'mensaje': f'Error procesando columna: {str(e)}', 'traceback': traceback.format_exc()}, status=500)
        
        except Exception as e:
            # Capturar cualquier excepción no manejada
            return JsonResponse({
                'estado': 'error',
                'mensaje': f'Error interno del servidor: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)


class AnalisisCompletoView(LoginRequiredMixin, View):
    """Vista para análisis inteligente de TODO el archivo Excel usando DeepSeek API."""
    
    def post(self, request, *args, **kwargs):
        import json
        import traceback
        from django.http import JsonResponse
        from .services import ExtractorInteligenteRequerimientos
        
        try:
            # Verificar que hay DataFrame en sesión
            if 'df_requerimiento' not in request.session:
                return JsonResponse({'estado': 'error', 'mensaje': 'No hay datos cargados para analizar'}, status=400)
            
            # Recuperar DataFrame de la sesión usando la función robusta
            df = cargar_dataframe_desde_json(request.session['df_requerimiento'])
            if df is None:
                return JsonResponse({'estado': 'error', 'mensaje': 'No se pudo cargar los datos desde la sesión'}, status=400)
            
            # Limitar el tamaño para no sobrecargar la API
            if len(df) > 100:
                df = df.head(100)
                mensaje_limit = "Se analizarán solo las primeras 100 filas por rendimiento."
            else:
                mensaje_limit = ""
            
            try:
                # Llamar al método de análisis completo
                resultado = ExtractorInteligenteRequerimientos.analizar_dataframe_completo(df)
                resultado['mensaje_limit'] = mensaje_limit
                resultado['estado'] = 'ok'
                return JsonResponse(resultado)
            except Exception as e:
                return JsonResponse({'estado': 'error', 'mensaje': f'Error en análisis completo: {str(e)}', 'traceback': traceback.format_exc()}, status=500)
        
        except Exception as e:
            # Capturar cualquier excepción no manejada
            return JsonResponse({
                'estado': 'error',
                'mensaje': f'Error interno del servidor: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
