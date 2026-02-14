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
        
        # Guardar archivo temporalmente
        fs = FileSystemStorage(location=tempfile.gettempdir())
        nombre_archivo = fs.save(archivo.name, archivo)
        ruta_archivo = fs.path(nombre_archivo)
        
        # Leer archivo con pandas
        try:
            if archivo.name.endswith('.csv'):
                df = pd.read_csv(ruta_archivo, encoding='utf-8')
            else:
                df = pd.read_excel(ruta_archivo, engine='openpyxl')
        except Exception as e:
            agregar_log(self.request, 'error', f'Error al leer archivo: {e}')
            messages.error(self.request, f'Error al leer archivo: {e}')
            return self.form_invalid(form)
        
        # Guardar datos en sesión
        self.request.session['df'] = df.to_json(orient='split')
        self.request.session['nombre_fuente'] = nombre_fuente
        self.request.session['portal_origen'] = portal_origen
        self.request.session['ruta_archivo'] = ruta_archivo
        
        # Limpiar logs anteriores
        limpiar_logs(self.request)
        
        agregar_log(self.request, 'info', f'Archivo {archivo.name} cargado exitosamente')
        agregar_log(self.request, 'debug', f'DataFrame shape: {df.shape}')
        
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
            return context
        
        df = pd.read_json(df_json, orient='split')
        nombre_fuente = self.request.session.get('nombre_fuente', 'Fuente desconocida')
        portal_origen = self.request.session.get('portal_origen', 'Portal desconocido')
        
        # Obtener sugerencias de campos
        sugeridor = SugeridorCampos()
        sugerencias = sugeridor.sugerir_campos(df)
        
        # Preparar formsets
        formset = ValidarMapeoFormSet(
            initial=[
                {
                    'columna_origen': col,
                    'campo_bd': info['nombre_sugerido_bd'],
                    'titulo_display': info['titulo_display'],
                    'tipo_dato': info['tipo_dato_sugerido'],
                    'es_campo_fijo': info.get('es_campo_fijo', False),
                    'campo_existente': info.get('campo_existente'),
                    'columna_existe_fisica': info.get('columna_existe_fisica', False),
                }
                for col, info in sugerencias['sugerencias'].items()
            ]
        )
        
        context.update({
            'nombre_fuente': nombre_fuente,
            'portal_origen': portal_origen,
            'formset': formset,
            'df_preview': df.head(10).to_html(classes='table table-striped'),
            'sugerencias': sugerencias,
            'logs': obtener_logs(self.request),
        })
        return context

    def post(self, request, *args, **kwargs):
        formset = ValidarMapeoFormSet(request.POST)
        
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
            messages.success(request, 'Mapeos validados exitosamente. Proceda a procesar.')
            return redirect('ingestas:resultado_ingesta')
        
        messages.error(request, 'Error en la validación de mapeos.')
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
        
        if not df_json or not mapeos:
            messages.error(self.request, 'No hay datos suficientes para procesar.')
            return context
        
        df = pd.read_json(df_json, orient='split')
        
        # Procesar Excel
        procesador = ProcesadorExcel()
        resultado = procesador.importar_excel(
            df=df,
            nombre_fuente=nombre_fuente,
            portal_origen=portal_origen,
            mapeos=mapeos
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