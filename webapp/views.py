from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Sum, Q
import json

from semillas.models import FuenteWeb
from captura.models import CapturaCruda, EventoDeteccion
from colas.tasks import revisar_fuentes_activas, actualizar_frecuencias_automaticas
from colas.tareas_descubrimiento import ejecutar_descubrimiento_automatico


def home(request):
    """Vista principal del dashboard"""
    # Obtener estadísticas básicas
    total_fuentes = FuenteWeb.objects.filter(estado='activa').count()
    total_capturas = CapturaCruda.objects.count()
    cambios_detectados = EventoDeteccion.objects.count()
    
    # Obtener fuentes activas recientes
    fuentes_activas = FuenteWeb.objects.filter(estado='activa').order_by('-fecha_ultima_revision')[:10]
    
    # Obtener cambios recientes
    cambios_recientes = EventoDeteccion.objects.select_related('captura', 'captura__fuente').order_by('-fecha_deteccion')[:5]
    
    context = {
        'total_fuentes': total_fuentes,
        'total_capturas': total_capturas,
        'cambios_detectados': cambios_detectados,
        'fuentes_activas': fuentes_activas,
        'cambios_recientes': cambios_recientes,
    }
    
    return render(request, 'index.html', context)


def fuentes_web(request):
    """Vista para la gestión de fuentes web"""
    # Obtener estadísticas por categoría
    categorias_data = []
    
    # Verificar si el modelo tiene CATEGORIA_CHOICES
    if hasattr(FuenteWeb, 'CATEGORIA_CHOICES'):
        for cat in FuenteWeb.CATEGORIA_CHOICES:
            categoria_val = cat[0]
            total = FuenteWeb.objects.filter(categoria=categoria_val).count()
            activas = FuenteWeb.objects.filter(categoria=categoria_val, estado='activa').count()
            capturas = FuenteWeb.objects.filter(categoria=categoria_val).aggregate(
                total_capturas=Sum('total_capturas')
            )['total_capturas'] or 0
            
            categorias_data.append({
                'categoria': categoria_val,
                'total': total,
                'activas': activas,
                'capturas': capturas
            })
    else:
        # Si no hay CATEGORIA_CHOICES, usar valores por defecto
        categorias_default = ['oferta', 'legal', 'infraestructura', 'inteligencia', 'riesgo', 'actores']
        for cat in categorias_default:
            total = FuenteWeb.objects.filter(categoria=cat).count()
            categorias_data.append({
                'categoria': cat,
                'total': total,
                'activas': 0,
                'capturas': 0
            })
    
    # Obtener todas las fuentes para la tabla
    fuentes = FuenteWeb.objects.all().order_by('-fecha_creacion')[:50]
    
    # Preparar datos para JavaScript
    fuentes_json = []
    for fuente in fuentes:
        fuentes_json.append({
            'id': fuente.id,
            'nombre': fuente.nombre,
            'url': fuente.url,
            'categoria': fuente.categoria if hasattr(fuente, 'categoria') else 'oferta',
            'estado': fuente.estado,
            'prioridad': fuente.prioridad,
            'frecuencia_revision_horas': fuente.frecuencia_revision_horas,
            'fecha_ultima_revision': fuente.fecha_ultima_revision.isoformat() if fuente.fecha_ultima_revision else None,
            'total_capturas': fuente.total_capturas or 0,
            'total_cambios_detectados': fuente.total_cambios_detectados or 0,
            'tasa_cambio_porcentaje': fuente.tasa_cambio_porcentaje or 0,
            'tipo': fuente.tipo or 'sitio_web',
            'descripcion': fuente.descripcion or '',
            'respetar_robots_txt': fuente.respetar_robots_txt,
            'delay_entre_requests': fuente.delay_entre_requests or 2,
            'fecha_creacion': fuente.fecha_creacion.isoformat() if fuente.fecha_creacion else None,
            'fecha_proxima_revision': fuente.fecha_proxima_revision.isoformat() if fuente.fecha_proxima_revision else None
        })
    
    context = {
        'categorias': categorias_data,
        'total_fuentes': FuenteWeb.objects.count(),
        'fuentes_activas': FuenteWeb.objects.filter(estado='activa').count(),
        'fuentes': fuentes,
        'fuentes_json': json.dumps(fuentes_json),  # Datos serializados para JavaScript
    }
    
    return render(request, 'fuentes_web.html', context)


@csrf_exempt
def agregar_fuente_api(request):
    """API para agregar nueva fuente desde el dashboard"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url', '').strip()
            frecuencia = data.get('frecuencia', 60)
            categoria = data.get('categoria', 'venta')
            prioridad_str = data.get('prioridad', 'media')
            
            if not url:
                return JsonResponse({'error': 'URL es requerida'}, status=400)
            
            # Convertir prioridad de string a número
            prioridad_map = {'alta': 3, 'media': 2, 'baja': 1}
            prioridad = prioridad_map.get(prioridad_str.lower(), 2)
            
            # Crear nueva fuente con campos correctos
            fuente = FuenteWeb.objects.create(
                url=url,
                nombre=url[:100],  # Nombre temporal
                estado='activa',
                prioridad=prioridad,
                frecuencia_revision_horas=frecuencia / 60,  # Convertir minutos a horas
                tipo=categoria,
                descripcion=f'Fuente agregada manualmente desde dashboard'
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Fuente agregada: {url}',
                'fuente_id': fuente.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def ejecutar_sistema_api(request):
    """API para ejecutar el sistema manualmente"""
    if request.method == 'POST':
        try:
            # Ejecutar tarea de revisión de fuentes activas
            task = revisar_fuentes_activas.delay()
            
            return JsonResponse({
                'success': True,
                'message': 'Sistema ejecutado. Revisando todas las fuentes activas.',
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def descubrir_urls_api(request):
    """API para descubrir nuevas URLs"""
    if request.method == 'POST':
        try:
            # Ejecutar tarea de descubrimiento
            task = ejecutar_descubrimiento_automatico.delay()
            
            return JsonResponse({
                'success': True,
                'message': 'Buscando nuevos portales inmobiliarios en Arequipa...',
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def actualizar_frecuencias_api(request):
    """API para actualizar frecuencias automáticamente"""
    if request.method == 'POST':
        try:
            # Ejecutar tarea de actualización de frecuencias
            task = actualizar_frecuencias_automaticas.delay()
            
            return JsonResponse({
                'success': True,
                'message': 'Actualizando frecuencias basadas en tasa de cambios...',
                'task_id': task.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def estadisticas_api(request):
    """API para obtener estadísticas en formato JSON"""
    total_fuentes = FuenteWeb.objects.filter(estado='activa').count()
    total_capturas = CapturaCruda.objects.count()
    cambios_detectados = EventoDeteccion.objects.count()
    
    # Contar URLs descubiertas (fuentes con estado 'descubierta')
    urls_descubiertas = FuenteWeb.objects.filter(estado='descubierta').count()
    
    return JsonResponse({
        'total_fuentes': total_fuentes,
        'total_capturas': total_capturas,
        'cambios_detectados': cambios_detectados,
        'urls_descubiertas': urls_descubiertas,
    })


def fuentes_api(request):
    """API para obtener lista de fuentes activas"""
    # Obtener todas las fuentes, no solo activas
    fuentes = FuenteWeb.objects.all().order_by('-fecha_creacion')[:50]
    
    fuentes_data = []
    for fuente in fuentes:
        # Determinar categoría (usar campo categoria si existe, sino 'oferta')
        categoria = getattr(fuente, 'categoria', 'oferta')
        
        fuentes_data.append({
            'id': fuente.id,
            'nombre': fuente.nombre or fuente.url,
            'url': fuente.url,
            'estado': fuente.estado,
            'categoria': categoria,
            'prioridad': fuente.prioridad,
            'frecuencia': fuente.frecuencia_revision_horas or 24,
            'ultima_captura': fuente.fecha_ultima_revision.strftime('%Y-%m-%d %H:%M') if fuente.fecha_ultima_revision else 'Nunca',
            'total_capturas': fuente.total_capturas or 0,
            'total_cambios_detectados': fuente.total_cambios_detectados or 0,
            'tasa_cambio_porcentaje': fuente.tasa_cambio_porcentaje or 0,
            'tipo': fuente.tipo or 'sitio_web',
            'descripcion': fuente.descripcion or '',
            'respetar_robots_txt': fuente.respetar_robots_txt,
            'delay_entre_requests': fuente.delay_entre_requests or 2,
            'fecha_creacion': fuente.fecha_creacion.strftime('%Y-%m-%d %H:%M') if fuente.fecha_creacion else '',
            'fecha_proxima_revision': fuente.fecha_proxima_revision.strftime('%Y-%m-%d %H:%M') if fuente.fecha_proxima_revision else ''
        })
    
    return JsonResponse(fuentes_data, safe=False)


def capturas_view(request):
    """Vista para visualizar capturas"""
    return render(request, 'capturas.html')


def capturas_api(request):
    """API para obtener lista de capturas"""
    # Filtros opcionales
    fuente_id = request.GET.get('fuente_id')
    estado = request.GET.get('estado')
    limite = int(request.GET.get('limite', 50))
    
    # Query base
    capturas = CapturaCruda.objects.select_related('fuente').all()
    
    # Aplicar filtros
    if fuente_id:
        capturas = capturas.filter(fuente_id=fuente_id)
    if estado:
        capturas = capturas.filter(estado_procesamiento=estado)
    
    # Ordenar y limitar
    capturas = capturas.order_by('-fecha_captura')[:limite]
    
    capturas_data = []
    for captura in capturas:
        capturas_data.append({
            'id': captura.id,
            'fuente_id': captura.fuente.id,
            'fuente_nombre': captura.fuente.nombre or captura.fuente.url[:50],
            'fuente_url': captura.fuente.url,
            'fecha_captura': captura.fecha_captura.strftime('%Y-%m-%d %H:%M:%S'),
            'estado': captura.estado_procesamiento or 'capturado',
            'tipo_documento': captura.tipo_documento or 'html',
            'tamaño_kb': round((captura.tamaño_bytes or 0) / 1024, 2),
            'hash': captura.hash_sha256[:16] if captura.hash_sha256 else '',
            'content_type': captura.content_type or 'text/html',
            'tiene_texto': bool(captura.texto_extraido),
            'longitud_texto': len(captura.texto_extraido or ''),
            'azure_blob_name': captura.azure_blob_name or '',
        })
    
    return JsonResponse({
        'total': capturas.count(),
        'capturas': capturas_data
    })


def captura_detalle_api(request, captura_id):
    """API para obtener detalle de una captura específica"""
    try:
        captura = CapturaCruda.objects.select_related('fuente').get(id=captura_id)
        
        # Obtener eventos relacionados
        eventos = EventoDeteccion.objects.filter(
            Q(captura_nueva=captura) | Q(captura_anterior=captura)
        ).order_by('-fecha_deteccion')[:10]
        
        eventos_data = []
        for evento in eventos:
            eventos_data.append({
                'id': evento.id,
                'tipo_cambio': evento.tipo_cambio or 'desconocido',
                'similitud': evento.similitud_porcentaje or 0,
                'fecha': evento.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S'),
                'resumen': evento.resumen_cambio or 'Sin resumen',
            })
        
        # Determinar si es PDF
        es_pdf = captura.tipo_documento in ('pdf_nativo', 'pdf_escaneado') or \
                 'pdf' in (captura.content_type or '').lower()
        
        # Texto extraído: para PDFs, no usar contenido_html (puede ser binario)
        if es_pdf and not captura.texto_extraido:
            texto_extraido = '[PDF sin texto extraído]'
            longitud_texto_completo = 0
        else:
            texto_extraido = captura.texto_extraido or captura.contenido_html or ''
            longitud_texto_completo = len(texto_extraido)
        
        data = {
            'id': captura.id,
            'fuente': {
                'id': captura.fuente.id,
                'nombre': captura.fuente.nombre or captura.fuente.url[:50],
                'url': captura.fuente.url,
                'categoria': getattr(captura.fuente, 'categoria', 'oferta'),
            },
            'fecha_captura': captura.fecha_captura.strftime('%Y-%m-%d %H:%M:%S'),
            'estado': captura.estado_procesamiento or 'capturado',
            'tipo_documento': captura.tipo_documento or 'html',
            'tamaño_bytes': captura.tamaño_bytes or 0,
            'hash': captura.hash_sha256 or '',
            'content_type': captura.content_type or 'text/html',
            'status_code': captura.status_code or 200,
            'tiempo_respuesta_ms': captura.tiempo_respuesta_ms or 0,
            'azure_blob_name': captura.azure_blob_name or '',
            'texto_extraido': texto_extraido,
            'longitud_texto_completo': longitud_texto_completo,
            'contenido_html': (captura.contenido_html or '')[:10000] if request.GET.get('incluir_html') else None,
            'metadatos': captura.metadata_tecnica if hasattr(captura, 'metadata_tecnica') else {},
            'eventos': eventos_data,
            'es_pdf': es_pdf,
        }
        
        return JsonResponse(data)
        
    except CapturaCruda.DoesNotExist:
        return JsonResponse({'error': 'Captura no encontrada'}, status=404)


@csrf_exempt
def procesar_fuente_api(request, fuente_id):
    """API para procesar una fuente específica manualmente"""
    if request.method == 'POST':
        try:
            from colas.tareas_captura import procesar_fuente_completa
            
            fuente = FuenteWeb.objects.get(id=fuente_id)
            
            # Ejecutar tarea de procesamiento
            task = procesar_fuente_completa.delay(fuente_id)
            
            return JsonResponse({
                'success': True,
                'message': f'Procesando fuente: {fuente.nombre or fuente.url}',
                'task_id': task.id,
                'fuente_id': fuente_id
            })
            
        except FuenteWeb.DoesNotExist:
            return JsonResponse({'error': 'Fuente no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def estadisticas_capturas_api(request):
    """API para obtener estadísticas de capturas"""
    from django.db.models import Count, Avg
    from datetime import timedelta
    from django.utils import timezone
    
    # Últimos 7 días
    fecha_limite = timezone.now() - timedelta(days=7)
    
    # Estadísticas generales
    total_capturas = CapturaCruda.objects.count()
    capturas_recientes = CapturaCruda.objects.filter(fecha_captura__gte=fecha_limite).count()
    
    # Por estado
    por_estado = CapturaCruda.objects.values('estado_procesamiento').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Por tipo de documento
    por_tipo = CapturaCruda.objects.values('tipo_documento').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Tamaño promedio
    tamaño_promedio = CapturaCruda.objects.filter(
        tamaño_bytes__isnull=False
    ).aggregate(Avg('tamaño_bytes'))['tamaño_bytes__avg'] or 0
    
    return JsonResponse({
        'total_capturas': total_capturas,
        'capturas_ultimos_7_dias': capturas_recientes,
        'tamaño_promedio_kb': round(tamaño_promedio / 1024, 2),
        'por_estado': list(por_estado),
        'por_tipo': list(por_tipo),
    })


@csrf_exempt
def captura_manual_api(request):
    """API para realizar una captura manual de cualquier URL"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url', '').strip()
            
            if not url:
                return JsonResponse({'error': 'URL es requerida'}, status=400)
            
            # Validar URL básica
            if not url.startswith('http'):
                url = 'https://' + url
            
            # Buscar si ya existe una fuente con esta URL
            fuente = FuenteWeb.objects.filter(url=url).first()
            
            # Si no existe, crear una temporal
            if not fuente:
                fuente = FuenteWeb.objects.create(
                    url=url,
                    nombre=f'Captura manual: {url[:80]}',
                    tipo='captura_manual',
                    categoria='temporal',
                    estado='activa',
                    prioridad=2,
                    frecuencia_revision_horas=24,
                    descripcion='Creada automáticamente desde captura manual'
                )
                es_nueva = True
            else:
                es_nueva = False
            
            # CAPTURAR DIRECTAMENTE SIN CELERY
            import requests
            import hashlib
            from django.utils import timezone
            
            try:
                # Descargar contenido
                response = requests.get(url, timeout=30)
                content_type = response.headers.get('Content-Type', '')
                
                # Detectar si es PDF
                es_pdf = 'pdf' in content_type.lower() or url.lower().endswith('.pdf')
                
                if es_pdf:
                    # Para PDFs - guardar binario y extraer texto
                    contenido_bytes = response.content
                    hash_sha256 = hashlib.sha256(contenido_bytes).hexdigest()
                    hash_simple = hash_sha256  # Para PDFs, hash simple es igual
                    
                    # Extraer texto del PDF
                    try:
                        from captura.extractor_pdf import ExtractionPDF
                        extractor = ExtractionPDF()
                        resultado = extractor.extraer_texto(contenido_bytes)
                        texto_extraido = resultado.get('texto', '')
                        tipo_doc = resultado.get('tipo', 'pdf_nativo')
                    except Exception as e:
                        texto_extraido = f'Error extrayendo texto PDF: {str(e)}'
                        tipo_doc = 'pdf_nativo'
                    
                    contenido = f'[PDF - {len(contenido_bytes)} bytes]'
                else:
                    # Para HTML/texto
                    contenido = response.text
                    hash_sha256 = hashlib.sha256(contenido.encode('utf-8')).hexdigest()
                    hash_simple = hashlib.sha256(contenido.replace(' ', '').replace('\n', '').encode('utf-8')).hexdigest()
                    texto_extraido = contenido[:5000]
                    tipo_doc = 'html'
                
                # Insertar con TODOS los campos requeridos
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO captura_capturacruda
                        (fuente_id, fecha_captura, estado, contenido_html, texto_extraido, hash_sha256, hash_simplificado,
                         status_code, content_type, content_length, encoding, tamaño_bytes,
                         estado_http, estado_procesamiento, tipo_documento, num_palabras, num_lineas, num_links, mensaje_error, stack_trace)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, [
                        fuente.id,
                        timezone.now(),
                        'exito',  # estado
                        contenido[:100000] if len(contenido) < 100000 else contenido[:100000],  # contenido_html
                        texto_extraido[:50000] if len(texto_extraido or '') < 50000 else (texto_extraido or '')[:50000],  # texto_extraido
                        hash_sha256,
                        hash_simple,
                        response.status_code,
                        response.headers.get('Content-Type', 'text/html'),
                        len(response.content) if es_pdf else len(contenido),  # content_length
                        response.encoding or 'utf-8',  # encoding
                        len(response.content) if es_pdf else len(contenido.encode('utf-8')),  # tamaño_bytes
                        'exito',  # estado_http
                        'texto_extraido_ok',  # estado_procesamiento
                        tipo_doc,  # tipo_documento
                        len(texto_extraido.split()) if texto_extraido else 0,  # num_palabras
                        len(texto_extraido.split('\n')) if texto_extraido else 0,  # num_lineas
                        texto_extraido.count('http') if texto_extraido else 0,  # num_links
                        '',  # mensaje_error
                        ''  # stack_trace
                    ])
                    # Obtener el ID insertado
                    cursor.execute("SELECT @@IDENTITY")
                    captura_id = int(cursor.fetchone()[0])
                
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Captura guardada! ID: {captura_id}',
                    'captura_id': captura_id,
                    'fuente_id': fuente.id,
                    'fuente_nueva': es_nueva,
                    'url': url,
                    'bytes': len(contenido)
                })
                
            except requests.RequestException as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error al descargar: {str(e)}'
                }, status=500)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)
