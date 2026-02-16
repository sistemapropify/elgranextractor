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
from .models import CampoDinamico, MapeoFuente, PropiedadRaw, MigracionPendiente


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


# Nueva vista para listar propiedades en tarjetas
class ListaPropiedadesView(ListView):
    model = PropiedadRaw
    template_name = 'ingestas/lista_propiedades.html'
    context_object_name = 'propiedades'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Ordenar por fecha de ingesta descendente
        return queryset.order_by('-fecha_ingesta')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar campos dinámicos para referencia
        context['campos_dinamicos'] = CampoDinamico.objects.all()
        return context


# Helper para extraer imagen de atributos_extras
def extraer_imagen_propiedad(propiedad):
    """
    Extrae la URL de imagen de los atributos_extras de una propiedad.
    Busca campos que contengan 'imagen', 'foto', 'url_imagen', 'image', 'photo', 'img'.
    Retorna la primera URL encontrada o None.
    """
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
    
    # Si no se encuentra, buscar cualquier valor que parezca URL
    for valor in atributos.values():
        if not valor:
            continue
        valor_str = str(valor).strip()
        if valor_str.startswith(('http://', 'https://', 'www.')):
            # Verificar extensiones de imagen comunes
            if any(ext in valor_str.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                return valor_str
    
    return None


# Vista para listar propiedades con filtros avanzados
class PropiedadesFiltradasView(ListView):
    model = PropiedadRaw
    template_name = 'ingestas/propiedades_filtros.html'
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