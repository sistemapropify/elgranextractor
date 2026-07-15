"""
Views del módulo canvas (PropFlow Visual Canvas).

Vistas principales HTML:
- lienzo_list: listado de lienzos del usuario
- lienzo_nuevo: formulario para crear nuevo lienzo
- lienzo_editor: pizarra interactiva del lienzo

API JSON:
- api_lienzo_save/api_lienzo_load: guardar/cargar snapshot
- api_propiedades: propiedades desde colección propiedadespropify
- api_agentes: lista de agentes inmobiliarios
- api_reqs_match: requerimientos que matchean con una propiedad
- api_template_save/api_template_list: CRUD de plantillas

NOTA: No se usa @login_required porque el middleware
AuthenticationMiddleware ya redirige a /login/ para usuarios no autenticados.
Usar @login_required crea un bucle de redirección. En su lugar se usa
request.current_user (establecido por el middleware).
"""

import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

from .models import Lienzo, CardTemplate, NotaLienzo, ArchivoLienzo
from intelligence.models import IntelligenceCollection, IntelligenceDocument
from agentes.models import Agente

logger = logging.getLogger(__name__)


def _get_current_user(request):
    """Obtiene el usuario actual desde request.current_user (middleware) o request.user."""
    user = getattr(request, 'current_user', None)
    if user is None and hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user
    return user


# ── VISTAS HTML ────────────────────────────────────────────────


def lienzo_list(request):
    user = _get_current_user(request)
    if not user:
        return redirect(f"{reverse('login')}?next={request.path}")
    lienzos = Lienzo.objects.filter(user=user)
    enriquecidos = []
    for lienzo in lienzos:
        nodos = (lienzo.snapshot or {}).get('nodos', []) if isinstance(lienzo.snapshot, dict) else []
        enriquecidos.append({
            'lienzo': lienzo,
            'num_props': sum(1 for n in nodos if n.get('tipo') == 'propiedad'),
            'num_reqs': sum(1 for n in nodos if n.get('tipo') == 'requerimiento'),
        })
    return render(request, 'canvas/list.html', {'lienzos': enriquecidos})


def lienzo_nuevo(request):
    user = _get_current_user(request)
    if not user:
        return redirect(f"{reverse('login')}?next={request.path}")
    if request.method == 'POST':
        nombre = request.POST.get('nombre', 'Lienzo sin título')
        tpl_id = request.POST.get('template_id')
        tpl = None
        if tpl_id:
            try:
                tpl = CardTemplate.objects.get(pk=int(tpl_id), user=user)
            except (ValueError, CardTemplate.DoesNotExist):
                tpl = None
        lienzo = Lienzo.objects.create(
            user=user,
            nombre=nombre,
            card_template=tpl,
        )
        return redirect('canvas:editor', pk=lienzo.pk)
    templates = CardTemplate.objects.filter(user=user)
    return render(request, 'canvas/nuevo.html', {'templates': templates})


def lienzo_editor(request, pk):
    user = _get_current_user(request)
    if not user:
        return redirect(f"{reverse('login')}?next={request.path}")
    lienzo = get_object_or_404(Lienzo, pk=pk, user=user)
    templates = CardTemplate.objects.filter(user=user)

    # ── Descubrir campos disponibles desde la colección propiedadespropify ──
    coleccion = IntelligenceCollection.objects.filter(name='propiedadespropify').first()
    campos_disponibles = []
    if coleccion:
        # Tomar varios documentos para cubrir todos los campos posibles
        # (diferentes propiedades pueden tener diferentes conjuntos de campos)
        EXCLUIR = {'id', 'created_at', 'updated_at', 'content_hash', 'embedding'}
        docs_muestra = IntelligenceDocument.objects.filter(
            collection=coleccion
        ).values_list('field_values', flat=True)[:50]
        campos_set = set()
        for fv in docs_muestra:
            if fv:
                campos_set.update(k for k in fv.keys() if k not in EXCLUIR)
        campos_disponibles = sorted(campos_set)

    # Serializar snapshot como JSON válido para JavaScript
    # (Django str() de dicts convierte True/False/None a mayúsculas, JS necesita minúsculas)
    import json as json_lib
    snapshot_json = json_lib.dumps(lienzo.snapshot or {})

    ctx = {
        'lienzo':             lienzo,
        'templates':          templates,
        'campos_disponibles': campos_disponibles,
        'snapshot_json':      snapshot_json,
        'user_id':            str(user.id) if hasattr(user, 'id') and user.id else '',
        'user_email':         user.email if hasattr(user, 'email') else '',
    }
    return render(request, 'canvas/editor.html', ctx)


# ── API: LIENZO ────────────────────────────────────────────────


@require_POST
@csrf_exempt
def api_lienzo_save(request, pk):
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    lienzo = get_object_or_404(Lienzo, pk=pk, user=user)
    data = json.loads(request.body)
    lienzo.snapshot = data.get('snapshot', {})
    lienzo.nombre = data.get('nombre', lienzo.nombre)
    lienzo.save()

    # Sincronizar notas standalone si vienen
    for nota_data in data.get('notas', []):
        nota_pk = nota_data.get('db_id')
        if nota_pk:
            NotaLienzo.objects.filter(pk=nota_pk, lienzo=lienzo).update(
                contenido=nota_data['contenido'],
                color=nota_data.get('color', '#2a2a2a'),
                x=nota_data.get('x', 100),
                y=nota_data.get('y', 100),
            )
        else:
            NotaLienzo.objects.create(
                lienzo=lienzo,
                contenido=nota_data['contenido'],
                color=nota_data.get('color', '#2a2a2a'),
                x=nota_data.get('x', 100),
                y=nota_data.get('y', 100),
            )

    return JsonResponse({'ok': True, 'actualizado_en': str(lienzo.actualizado_en)})


def api_lienzo_load(request, pk):
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    lienzo = get_object_or_404(Lienzo, pk=pk, user=user)
    notas_qs = NotaLienzo.objects.filter(lienzo=lienzo).values(
        'id', 'contenido', 'color', 'x', 'y'
    )

    # Refrescar SAS tokens para nodos de archivo (imágenes, excels, etc.)
    snapshot = lienzo.snapshot or {}
    nodos = snapshot.get('nodos', [])
    if nodos and isinstance(nodos, list):
        from .models import ArchivoLienzo
        from datetime import datetime, timedelta
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas
        from django.conf import settings
        account_key = getattr(settings, 'AZURE_STORAGE_ACCOUNT_KEY', '') or ''
        
        for nodo in nodos:
            if nodo.get('tipo') != 'archivo':
                continue
            ref_id = nodo.get('ref_id')
            if not ref_id:
                continue
            archivo = ArchivoLienzo.objects.filter(pk=ref_id).first()
            if not archivo or not archivo.blob_name:
                continue
            if not account_key:
                continue
            try:
                from captura.azure_storage import get_blob_service_client
                bsc = get_blob_service_client()
                container_client = bsc.get_container_client(settings.LIENZO_STORAGE_CONTAINER)
                blob_client = container_client.get_blob_client(archivo.blob_name)
                sas = generate_blob_sas(
                    account_name=blob_client.account_name,
                    container_name=blob_client.container_name,
                    blob_name=blob_client.blob_name,
                    account_key=account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(hours=24),
                )
                new_url = f"{blob_client.url}?{sas}"
                nodo['field_data'] = nodo.get('field_data', {})
                nodo['field_data']['file_url'] = new_url
            except Exception as e:
                logger.warning(f"Error refrescando SAS para archivo {ref_id}: {e}")

    return JsonResponse({
        'snapshot': snapshot,
        'nombre':   lienzo.nombre,
        'template': lienzo.card_template_id,
        'notas':    list(notas_qs),
    })


# ── API: PROPIEDADES ───────────────────────────────────────────


def api_propiedades(request):
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    agente_id = request.GET.get('agente_id')  # nombre del agente (responsible_name)
    campos_raw = request.GET.getlist('campos')

    coleccion = get_object_or_404(IntelligenceCollection, name='propiedadespropify')
    qs = IntelligenceDocument.objects.filter(
        collection=coleccion,
        field_values__property_status_id=3,
        field_values__is_visible=True,
    )

    if agente_id:
        qs = qs.filter(
            field_values__responsible_name=agente_id
        )

    # Construir URL de imagen para cada propiedad
    # Usamos la misma lógica que en matching/engine.py:
    # 1. Primera imagen desde property_media
    # 2. Fallback: {code}.jpg en Azure Storage
    MEDIA_BASE = "https://propifymedia01.blob.core.windows.net/media"
    
    # Recopilar source_ids para consulta batch a property_media
    source_ids_int = []
    doc_map = {}  # source_id -> doc
    for doc in qs.only('source_id', 'field_values').iterator():
        sid = doc.source_id
        doc_map[sid] = doc
        try:
            source_ids_int.append(int(sid))
        except (ValueError, TypeError):
            pass
    
    # Consulta batch: obtener primera imagen (file) por property_id
    image_map = {}  # property_id -> file_path
    if source_ids_int:
        from django.db import connections
        try:
            with connections['propifai'].cursor() as cursor:
                # Usar STRING_AGG o TOP 1 con subquery para obtener primera imagen
                ids_str = ','.join(str(sid) for sid in source_ids_int)
                img_query = f"""
                    SELECT pm.property_id, MIN(pm.[file]) AS [file]
                    FROM property_media pm
                    WHERE pm.property_id IN ({ids_str})
                      AND pm.media_type = 'image'
                    GROUP BY pm.property_id
                """
                cursor.execute(img_query)
                for row in cursor.fetchall():
                    prop_id, file_path = row
                    image_map[int(prop_id)] = file_path
        except Exception as e:
            logger.warning(f"Error querying property_media: {e}")

    # Consulta batch: contar leads por propiedad desde lead_properties
    lead_count_map = {}  # property_id -> count
    if source_ids_int:
        try:
            with connections['propifai'].cursor() as cursor:
                ids_str = ','.join(str(sid) for sid in source_ids_int)
                lead_query = f"""
                    SELECT lpp.property_id, COUNT(DISTINCT lpp.lead_id) AS lead_count
                    FROM lead_properties lpp
                    WHERE lpp.property_id IN ({ids_str})
                    GROUP BY lpp.property_id
                """
                cursor.execute(lead_query)
                for row in cursor.fetchall():
                    prop_id, count = row
                    lead_count_map[int(prop_id)] = count
        except Exception as e:
            logger.warning(f"Error querying lead_properties: {e}")

    result = []
    for doc in qs.iterator():
        fv = doc.field_values or {}
        if campos_raw:
            entry = {}
            for c in campos_raw:
                entry[c] = fv.get(c)
        else:
            entry = dict(fv)
        entry['_tipo'] = 'propiedad'
        entry['_source_id'] = doc.source_id
        
        # Asegurar que 'title' tenga un valor significativo para el sidebar
        if not entry.get('title'):
            entry['title'] = (
                fv.get('title')
                or fv.get('name')
                or ''
            )
        
        # El sidebar espera 'direction' pero field_values usa nombres reales de columna
        # Mapear desde los campos de dirección disponibles
        if 'direction' not in entry or not entry.get('direction'):
            entry['direction'] = (
                fv.get('map_address')
                or fv.get('display_address')
                or fv.get('real_address')
                or fv.get('address')
                or ''
            )
        
        # Construir URL de imagen
        img_url = None
        try:
            prop_id = int(doc.source_id)
            file_path = image_map.get(prop_id)
            if file_path:
                if file_path.startswith('/'):
                    file_path = file_path[1:]
                img_url = f"{MEDIA_BASE}/{file_path}"
        except (ValueError, TypeError):
            pass
        
        # Fallback: construir desde code
        if not img_url:
            code = fv.get('code')
            if code:
                code_str = str(code)
                if any(code_str.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    img_url = f"{MEDIA_BASE}/{code_str}"
                else:
                    img_url = f"{MEDIA_BASE}/{code_str}.jpg"
        
        entry['_imagen_url'] = img_url
        # Conteo de leads desde lead_properties
        try:
            prop_id = int(doc.source_id)
            entry['_lead_count'] = lead_count_map.get(prop_id, 0)
        except (ValueError, TypeError):
            entry['_lead_count'] = 0
        result.append(entry)

    return JsonResponse({'propiedades': result})


# ── API: IMÁGENES DE PROPIEDAD ─────────────────────────────────


def api_propiedad_imagenes(request, prop_id):
    """
    GET /canvas/api/propiedad-imagenes/<prop_id>/
    Retorna todas las imágenes de una propiedad desde property_media.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    MEDIA_BASE = "https://propifymedia01.blob.core.windows.net/media"
    imagenes = []

    try:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            cursor.execute("""
                SELECT pm.[file], pm.media_type
                FROM property_media pm
                WHERE pm.property_id = %s
                  AND pm.media_type = 'image'
                ORDER BY pm.[file]
            """, [prop_id])
            
            for row in cursor.fetchall():
                file_path, media_type = row
                if file_path:
                    if file_path.startswith('/'):
                        file_path = file_path[1:]
                    url = f"{MEDIA_BASE}/{file_path}"
                    imagenes.append({
                        'url': url,
                        'file': file_path,
                        'type': media_type or 'image',
                    })
    except Exception as e:
        logger.warning(f"Error obteniendo imágenes para propiedad {prop_id}: {e}")

    # Fallback: si no hay imágenes en property_media, intentar con code
    if not imagenes:
        try:
            col = IntelligenceCollection.objects.get(name='propiedadespropify')
            doc = IntelligenceDocument.objects.filter(
                collection=col, source_id=str(prop_id)
            ).first()
            if doc and doc.field_values:
                code = doc.field_values.get('code')
                if code:
                    code_str = str(code)
                    # Asegurar extensión de archivo
                    if not any(code_str.lower().endswith(ext) for ext in ['.jpg','.jpeg','.png','.webp','.gif']):
                        code_str += '.jpg'
                    imagenes.append({
                        'url': f"{MEDIA_BASE}/{code_str}",
                        'file': code_str,
                        'type': 'image',
                    })
        except Exception:
            pass

    return JsonResponse({'imagenes': imagenes, 'total': len(imagenes), 'prop_id': prop_id})


# ── API: LEAD ANALYSIS ─────────────────────────────────────────


def api_lead_analysis(request, prop_id):
    """
    GET /canvas/api/lead-analysis/<prop_id>/?granularity=day|week|month
    Retorna el conteo de leads agregado por día, semana o mes.

    NOTA: El agrupamiento por semana/mes se hace en Python para evitar
    problemas con DATEADD/DATEDIFF en columnas datetimeoffset de Azure SQL.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    granularity = request.GET.get('granularity', 'day')
    from datetime import date, timedelta

    counts = []
    total_leads = 0
    first_lead_date = None

    try:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            # Siempre traer datos por día (CAST a DATE evita problemas de datetimeoffset)
            cursor.execute("""
                SELECT CAST(SWITCHOFFSET(l.created_at, '-05:00') AS DATE) AS bucket_date,
                       COUNT(DISTINCT l.id) AS count
                FROM lead_properties lp
                INNER JOIN lead l ON l.id = lp.lead_id
                WHERE lp.property_id = %s
                GROUP BY CAST(SWITCHOFFSET(l.created_at, '-05:00') AS DATE)
                ORDER BY bucket_date
            """, [prop_id])

            # Cargar todos los días en un dict
            day_counts = {}
            for row in cursor.fetchall():
                d, cnt = row
                if hasattr(d, 'isoformat'):
                    day_counts[d] = cnt
                else:
                    day_counts[str(d)] = cnt
                total_leads += cnt

            if granularity == 'day':
                # Devolver tal cual, ordenado por fecha
                for d in sorted(day_counts.keys()):
                    date_str = d.isoformat() if hasattr(d, 'isoformat') else str(d)
                    counts.append({'date': date_str, 'count': day_counts[d]})
                    if first_lead_date is None:
                        first_lead_date = date_str

            elif granularity == 'week':
                # Agrupar por semana (lunes=0, domingo=6)
                week_buckets = {}
                for d in sorted(day_counts.keys()):
                    # Calcular el lunes de la semana
                    if isinstance(d, date):
                        days_since_monday = d.weekday()  # 0=lunes
                        monday = d - timedelta(days=days_since_monday)
                        week_buckets[monday] = week_buckets.get(monday, 0) + day_counts[d]
                    else:
                        # Si es string, mantener raw
                        week_buckets[d] = week_buckets.get(d, 0) + day_counts[d]

                for d in sorted(week_buckets.keys()):
                    date_str = d.isoformat() if hasattr(d, 'isoformat') else str(d)
                    counts.append({'date': date_str, 'count': week_buckets[d]})
                    if first_lead_date is None:
                        first_lead_date = date_str

            elif granularity == 'month':
                # Agrupar por mes
                month_buckets = {}
                for d in sorted(day_counts.keys()):
                    if isinstance(d, date):
                        month_key = date(d.year, d.month, 1)
                        month_buckets[month_key] = month_buckets.get(month_key, 0) + day_counts[d]
                    else:
                        month_buckets[d] = month_buckets.get(d, 0) + day_counts[d]

                for d in sorted(month_buckets.keys()):
                    date_str = d.isoformat() if hasattr(d, 'isoformat') else str(d)
                    counts.append({'date': date_str, 'count': month_buckets[d]})
                    if first_lead_date is None:
                        first_lead_date = date_str

    except Exception as e:
        logger.warning(f"Error en lead analysis for property {prop_id}: {e}")
        return JsonResponse({'error': str(e)}, status=500)

    logger.info(f"LEAD_ANALYSIS prop={prop_id} granularity={granularity} total={total_leads} buckets={len(counts)} first={first_lead_date}")
    if counts:
        logger.info(f"LEAD_ANALYSIS sample buckets: {[c['date'][:10] + ':' + str(c['count']) for c in counts[:5]]}")

    return JsonResponse({
        'prop_id': prop_id,
        'total_leads': total_leads,
        'first_lead_date': first_lead_date,
        'granularity': granularity,
        'daily_counts': counts,
    })


# ── API: LEADS POR FECHA ───────────────────────────────────────


def api_lead_analysis_global(request):
    """
    GET /canvas/api/lead-analysis-global/?granularity=day|week|month
    Retorna el conteo de TODOS los leads agrupados por fecha de creacion.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    granularity = request.GET.get('granularity', 'day')
    from datetime import date, timedelta

    counts = []
    total_leads = 0
    first_lead_date = None

    try:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            cursor.execute("""
                SELECT CAST(SWITCHOFFSET(created_at, '-05:00') AS DATE) AS bucket_date,
                       COUNT(DISTINCT id) AS count
                FROM lead
                GROUP BY CAST(SWITCHOFFSET(created_at, '-05:00') AS DATE)
                ORDER BY bucket_date
            """)

            day_counts = {}
            for row in cursor.fetchall():
                d, cnt = row
                if hasattr(d, 'isoformat'):
                    day_counts[d] = cnt
                else:
                    day_counts[str(d)] = cnt
                total_leads += cnt

            if granularity == 'day':
                for d in sorted(day_counts.keys()):
                    date_str = d.isoformat() if hasattr(d, 'isoformat') else str(d)
                    counts.append({'date': date_str, 'count': day_counts[d]})
                    if first_lead_date is None:
                        first_lead_date = date_str

            elif granularity == 'week':
                week_buckets = {}
                for d in sorted(day_counts.keys()):
                    if isinstance(d, date):
                        days_since_monday = d.weekday()
                        monday = d - timedelta(days=days_since_monday)
                        week_buckets[monday] = week_buckets.get(monday, 0) + day_counts[d]
                    else:
                        week_buckets[d] = week_buckets.get(d, 0) + day_counts[d]
                for d in sorted(week_buckets.keys()):
                    date_str = d.isoformat() if hasattr(d, 'isoformat') else str(d)
                    counts.append({'date': date_str, 'count': week_buckets[d]})
                    if first_lead_date is None:
                        first_lead_date = date_str

            elif granularity == 'month':
                month_buckets = {}
                for d in sorted(day_counts.keys()):
                    if isinstance(d, date):
                        month_key = date(d.year, d.month, 1)
                        month_buckets[month_key] = month_buckets.get(month_key, 0) + day_counts[d]
                    else:
                        month_buckets[d] = month_buckets.get(d, 0) + day_counts[d]
                for d in sorted(month_buckets.keys()):
                    date_str = d.isoformat() if hasattr(d, 'isoformat') else str(d)
                    counts.append({'date': date_str, 'count': month_buckets[d]})
                    if first_lead_date is None:
                        first_lead_date = date_str

    except Exception as e:
        logger.warning(f"Error en lead analysis global: {e}")
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({
        'total_leads': total_leads,
        'first_lead_date': first_lead_date,
        'granularity': granularity,
        'daily_counts': counts,
    })


def api_leads_by_date(request):
    """
    GET /canvas/api/leads-by-date/?date=YYYY-MM-DD
    Retorna TODOS los leads creados en una fecha especifica (sin filtro por propiedad).
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    date_str = request.GET.get('date', '')
    if not date_str:
        return JsonResponse({'error': 'Parámetro date requerido (YYYY-MM-DD)'}, status=400)

    try:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            cursor.execute("""
                SELECT l.id, l.username, l.source, l.source_detail,
                       l.notes, l.score, l.last_message_text, l.created_at,
                       c.first_name, c.last_name, c.phone, c.email
                FROM lead l
                LEFT JOIN contact c ON c.id = l.contact_id
                WHERE CAST(SWITCHOFFSET(l.created_at, '-05:00') AS DATE) = %s
                ORDER BY l.created_at DESC
            """, [date_str])

            leads = []
            from datetime import timedelta
            for row in cursor.fetchall():
                lead_id, username, source, source_detail, notes, score, last_msg, created_at, first_name, last_name, phone, email = row
                # Convertir UTC a Peru (UTC-5)
                if hasattr(created_at, 'isoformat'):
                    peru_time = created_at - timedelta(hours=5)
                    created_str = peru_time.isoformat()
                else:
                    created_str = str(created_at)
                contact_name = (first_name or '') + (' ' + last_name if last_name else '')
                contact_name = contact_name.strip() or username or ''
                leads.append({
                    'id': lead_id,
                    'username': username or '',
                    'contact_name': contact_name,
                    'phone': phone or '',
                    'email': email or '',
                    'source': source or '',
                    'source_detail': source_detail or '',
                    'notes': notes or '',
                    'score': score,
                    'last_message_text': (last_msg or ''),
                    'created_at': created_str,
                })
    except Exception as e:
        logger.warning(f"Error en leads by date {date_str}: {e}")
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'date': date_str, 'leads': leads})


def api_lead_analysis_leads(request, prop_id):
    """
    GET /canvas/api/lead-analysis/<prop_id>/leads/?date=YYYY-MM-DD
    Retorna los leads individuales para una propiedad en una fecha específica.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    date_str = request.GET.get('date', '')
    if not date_str:
        return JsonResponse({'error': 'Parámetro date requerido (YYYY-MM-DD)'}, status=400)

    try:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            cursor.execute("""
                SELECT l.id, l.username, l.source, l.source_detail,
                       l.notes, l.score, l.last_message_text,
                       l.created_at,
                       c.first_name, c.last_name, c.phone, c.email
                FROM lead_properties lp
                INNER JOIN lead l ON l.id = lp.lead_id
                LEFT JOIN contact c ON c.id = l.contact_id
                WHERE lp.property_id = %s
                  AND CAST(SWITCHOFFSET(l.created_at, '-05:00') AS DATE) = %s
                ORDER BY l.created_at DESC
            """, [prop_id, date_str])

            leads = []
            from datetime import timedelta
            for row in cursor.fetchall():
                lead_id, username, source, source_detail, notes, score, last_msg, created_at, first_name, last_name, phone, email = row
                if hasattr(created_at, 'isoformat'):
                    peru_time = created_at - timedelta(hours=5)
                    created_str = peru_time.isoformat()
                else:
                    created_str = str(created_at)
                contact_name = (first_name or '') + (' ' + last_name if last_name else '')
                contact_name = contact_name.strip() or username or ''
                leads.append({
                    'id': lead_id,
                    'username': username or '',
                    'contact_name': contact_name,
                    'phone': phone or '',
                    'email': email or '',
                    'source': source or '',
                    'source_detail': source_detail or '',
                    'notes': notes or '',
                    'score': score,
                    'last_message_text': (last_msg or ''),
                    'created_at': created_str,
                })
    except Exception as e:
        logger.warning(f"Error en lead analysis leads for property {prop_id}, date {date_str}: {e}")
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'prop_id': prop_id, 'date': date_str, 'leads': leads})


# ── API: AGENTES ───────────────────────────────────────────────


def api_agentes(request):
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    # Los agentes son los responsible_name únicos en las propiedades
    coleccion = IntelligenceCollection.objects.filter(name='propiedadespropify').first()
    if not coleccion:
        return JsonResponse({'agentes': []})

    from django.db.models import Q
    agentes_set = set()
    agentes_list = []
    for doc in IntelligenceDocument.objects.filter(collection=coleccion).only('field_values').iterator():
        fv = doc.field_values or {}
        rname = fv.get('responsible_name')
        if rname and rname not in agentes_set:
            agentes_set.add(rname)
            agentes_list.append({
                'id': rname,  # usamos el nombre como ID para filtrar después
                'nombre': rname,
            })
    agentes_list.sort(key=lambda x: x['nombre'])
    return JsonResponse({'agentes': agentes_list})


# ── API: MATCHES ────────────────────────────────────────────────


def api_reqs_match(request, prop_id):
    """
    Retorna los requerimientos que tienen match REAL con una propiedad.
    En lugar de calcular matches nuevos con embeddings (impreciso),
    consulta los resultados ya ejecutados por el motor de matching en MatchResult.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    try:
        from matching.models import MatchResult

        # Buscar matches REALES ya calculados para esta propiedad
        # Solo matches compatibles (fase_eliminada IS NULL = pasaron filtros duros)
        match_results = MatchResult.objects.filter(
            propiedad_id=prop_id,
            fase_eliminada__isnull=True,
        ).select_related('requerimiento').order_by('-score_total')[:20]

        matches = []
        for mr in match_results:
            req = mr.requerimiento
            # Formatear hora como HH:MM si existe
            hora_str = ''
            if hasattr(req, 'hora') and req.hora:
                try:
                    hora_str = req.hora.strftime('%H:%M')
                except Exception:
                    hora_str = str(req.hora)

            # Formatear presupuesto
            presupuesto_monto = None
            if hasattr(req, 'presupuesto_monto') and req.presupuesto_monto is not None:
                try:
                    presupuesto_monto = float(req.presupuesto_monto)
                except Exception:
                    presupuesto_monto = None

            # Formatear fecha de ejecución del match
            ejecutado_str = ''
            if mr.ejecutado_en:
                try:
                    ejecutado_str = mr.ejecutado_en.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    ejecutado_str = str(mr.ejecutado_en)

            matches.append({
                'id': str(req.id),
                'match_id': mr.id,
                'ejecutado_en': ejecutado_str,
                # Dueño / Agente
                'agente': getattr(req, 'agente', '') or '',
                'agente_telefono': getattr(req, 'agente_telefono', '') or '',
                # Fecha y hora
                'fecha': str(req.fecha) if hasattr(req, 'fecha') and req.fecha else '',
                'hora': hora_str,
                # Tipo de requerimiento
                'tipo_original': getattr(req, 'tipo_original', '') or '',
                'condicion': getattr(req, 'condicion', '') or '',
                # Requerimiento original (texto completo)
                'requerimiento': getattr(req, 'requerimiento', '') or '',
                # Presupuesto
                'presupuesto': presupuesto_monto,
                'presupuesto_monto': presupuesto_monto,
                'presupuesto_moneda': getattr(req, 'presupuesto_moneda', '') or '',
                'presupuesto_forma_pago': getattr(req, 'presupuesto_forma_pago', '') or '',
                # Propiedad buscada
                'tipo_propiedad': getattr(req, 'tipo_propiedad', '') or '',
                'distritos': getattr(req, 'distritos', '') or '',
                'urbanizacion': getattr(req, 'urbanizacion', '') or '',
                'zona': getattr(req, 'zona', '') or '',
                # Scores
                'score_semantico': 0,
                'score_estructural': float(mr.score_total) if mr.score_total else 0,
                'score_total': float(mr.score_total) if mr.score_total else 0,
                'score_detalle': mr.score_detalle or {},
                'fase_eliminada': mr.fase_eliminada,
                'tipo': 'estructural',
            })

        return JsonResponse({'matches': matches, 'total': len(matches)})

    except Exception as e:
        logger.error(f"Error fetching MatchResult for prop {prop_id}: {e}")
        return JsonResponse({'matches': [], 'total': 0})


def api_match_detail(request, match_id):
    """
    GET /canvas/api/match-detail/<match_id>/

    Retorna detalle comparativo de un match: propiedad vs requerimiento
    con los 11 campos ordenados por peso/importancia.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    try:
        from matching.models import MatchResult
        from requerimientos.models import Requerimiento

        mr = MatchResult.objects.select_related('requerimiento').get(id=match_id)
        req = mr.requerimiento

        # Obtener datos de la propiedad desde la BD propifai
        prop_data = {}
        try:
            from django.db import connections
            with connections['propifai'].cursor() as cursor:
                cursor.execute("""
                    SELECT p.id, p.code, p.title, p.price, p.currency_id,
                           p.bedrooms, p.bathrooms, p.built_area,
                           p.has_elevator, p.garage_spaces,
                           p.operation_type_name, p.property_type_name,
                           p.district_name, p.year_built,
                           p.description, p.map_address
                    FROM propiedadespropify p
                    WHERE p.id = %s
                """, [mr.propiedad_id])
                row = cursor.fetchone()
                if row:
                    col_names = [
                        'id','code','title','price','currency_id',
                        'bedrooms','bathrooms','built_area',
                        'has_elevator','garage_spaces',
                        'operation_type_name','property_type_name',
                        'district_name','year_built',
                        'description','map_address'
                    ]
                    for i, name in enumerate(col_names):
                        prop_data[name] = row[i]
        except Exception as e:
            logger.warning(f"No se pudo obtener propiedad {mr.propiedad_id}: {e}")

        # Helper para formatear valores
        def _val(v, default='—'):
            if v is None or v == '':
                return default
            return str(v)

        def _bool(v, yes='Sí', no='No'):
            if v is True or str(v).lower() in ('1', 'true', 'si', 'sí'):
                return yes
            if v is False or str(v).lower() in ('0', 'false', 'no'):
                return no
            return _val(v)

        def _is_compatible(score_val, peso_maximo):
            """Determina si un campo es compatible basado en su score."""
            if score_val is None:
                return None
            try:
                return float(score_val) >= (float(peso_maximo) * 0.5)
            except (ValueError, TypeError):
                return None

        sd = mr.score_detalle or {}
        ejecutado_str = ''
        if mr.ejecutado_en:
            try:
                ejecutado_str = mr.ejecutado_en.strftime('%Y-%m-%d %H:%M')
            except Exception:
                ejecutado_str = str(mr.ejecutado_en)

        # Los 11 campos ordenados por peso/importancia
        # Cada campo: nombre, label, valor_propiedad, valor_requerimiento, compatible
        campos = []

        # 1. PRECIO (20pts)
        s = sd.get('precio', {})
        campos.append({
            'nombre': 'precio', 'label': '💰 Presupuesto', 'peso': 20,
            'propiedad': _val(prop_data.get('price')),
            'requerimiento': _val(req.presupuesto_monto) + ' ' + _val(req.get_presupuesto_moneda_display() if hasattr(req, 'get_presupuesto_moneda_display') else req.presupuesto_moneda, ''),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 20)),
            'detalle': s.get('detalle', ''),
        })

        # 2. DISTRITO (15pts)
        s = sd.get('distrito', {})
        campos.append({
            'nombre': 'distrito', 'label': '📍 Distrito', 'peso': 15,
            'propiedad': _val(prop_data.get('district_name')),
            'requerimiento': _val(req.distritos),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 15)),
            'detalle': s.get('detalle', ''),
        })

        # 3. HABITACIONES (15pts)
        s = sd.get('habitaciones', {})
        campos.append({
            'nombre': 'habitaciones', 'label': '🛏️ Habitaciones', 'peso': 15,
            'propiedad': _val(prop_data.get('bedrooms')),
            'requerimiento': _val(req.habitaciones),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 15)),
            'detalle': s.get('detalle', ''),
        })

        # 4. SEMÁNTICO (15pts)
        s = sd.get('semantico', {})
        campos.append({
            'nombre': 'semantico', 'label': '🧠 Coincidencia', 'peso': 15,
            'propiedad': _val(prop_data.get('description', '')[:80]),
            'requerimiento': _val(req.requerimiento[:80]),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 15)),
            'detalle': s.get('detalle', ''),
        })

        # 5. CONDICIÓN (filtro duro)
        compatible_cond = mr.fase_eliminada != 'condicion'
        campos.append({
            'nombre': 'condicion', 'label': '🔴 Condición', 'peso': -1,
            'propiedad': _val(prop_data.get('operation_type_name')),
            'requerimiento': _val(req.get_condicion_display() if hasattr(req, 'get_condicion_display') else req.condicion),
            'compatible': compatible_cond,
            'detalle': 'Filtro duro' if not compatible_cond else '',
        })

        # 6. TIPO PROPIEDAD (filtro duro)
        compatible_tipo = mr.fase_eliminada != 'tipo_propiedad'
        campos.append({
            'nombre': 'tipo_propiedad', 'label': '🏠 Tipo Propiedad', 'peso': -1,
            'propiedad': _val(prop_data.get('property_type_name')),
            'requerimiento': _val(req.get_tipo_propiedad_display() if hasattr(req, 'get_tipo_propiedad_display') else req.tipo_propiedad),
            'compatible': compatible_tipo,
            'detalle': 'Filtro duro' if not compatible_tipo else '',
        })

        # 7. BAÑOS (10pts)
        s = sd.get('banos', {})
        campos.append({
            'nombre': 'banos', 'label': '🚿 Baños', 'peso': 10,
            'propiedad': _val(prop_data.get('bathrooms')),
            'requerimiento': _val(req.banos),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 10)),
            'detalle': s.get('detalle', ''),
        })

        # 8. ÁREA (10pts)
        s = sd.get('area', {})
        campos.append({
            'nombre': 'area', 'label': '📐 Área m²', 'peso': 10,
            'propiedad': _val(prop_data.get('built_area')),
            'requerimiento': _val(req.area_m2),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 10)),
            'detalle': s.get('detalle', ''),
        })

        # 9. AMENITIES - Ascensor + Cochera (10pts)
        s = sd.get('amenities', {})
        ascensor_str = _bool(prop_data.get('has_elevator'))
        cochera_str = _val(prop_data.get('garage_spaces'))
        campos.append({
            'nombre': 'amenities', 'label': '🛗 Ascensor + 🚗 Cochera', 'peso': 10,
            'propiedad': f"Asc:{ascensor_str} / Cochera:{cochera_str}",
            'requerimiento': f"Asc:{_val(req.ascensor)} / Cochera:{_val(req.cochera)}",
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 10)),
            'detalle': s.get('detalle', ''),
        })

        # 10. ANTIGÜEDAD (5pts)
        s = sd.get('antiguedad', {})
        anio = prop_data.get('year_built')
        antiguedad_str = str(anio) if anio else '—'
        campos.append({
            'nombre': 'antiguedad', 'label': '📅 Antigüedad', 'peso': 5,
            'propiedad': antiguedad_str,
            'requerimiento': _val(getattr(req, 'antiguedad_max', None)),
            'compatible': _is_compatible(s.get('score'), s.get('peso_maximo', 5)),
            'detalle': s.get('detalle', ''),
        })

        # 11. FORMA DE PAGO (filtro duro)
        compatible_pago = mr.fase_eliminada != 'forma_pago'
        campos.append({
            'nombre': 'forma_pago', 'label': '💳 Forma Pago', 'peso': -1,
            'propiedad': _val(prop_data.get('forma_pago')),
            'requerimiento': _val(req.get_presupuesto_forma_pago_display() if hasattr(req, 'get_presupuesto_forma_pago_display') else req.presupuesto_forma_pago),
            'compatible': compatible_pago,
            'detalle': 'Filtro duro' if not compatible_pago else '',
        })

        return JsonResponse({
            'match_id': mr.id,
            'score_total': float(mr.score_total),
            'ejecutado_en': ejecutado_str,
            'fase_eliminada': mr.fase_eliminada,
            'score_detalle': sd,
            'campos': campos,
        })

    except MatchResult.DoesNotExist:
        return JsonResponse({'error': 'Match no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error en api_match_detail({match_id}): {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ── API: TEMPLATES ─────────────────────────────────────────────


@require_POST
def api_template_save(request):
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    data = json.loads(request.body)
    nombre = data.get('nombre', 'Plantilla')
    campos = data.get('campos', [])
    pk = data.get('id')

    if pk:
        tpl = get_object_or_404(CardTemplate, pk=pk, user=user)
        tpl.nombre = nombre
        tpl.campos = campos
        tpl.save()
    else:
        tpl = CardTemplate.objects.create(
            user=user,
            nombre=nombre,
            campos=campos,
        )
    return JsonResponse({'ok': True, 'id': tpl.pk, 'nombre': tpl.nombre})


def api_template_list(request):
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    tpls = CardTemplate.objects.filter(user=user).values('id', 'nombre', 'campos')
    return JsonResponse({'templates': list(tpls)})


# ── API: UPLOAD FILES ────────────────────────────────────────────


@require_POST
@csrf_exempt
def api_upload(request):
    """
    Sube un archivo al lienzo (Excel, Word, PDF, Imagen).
    El archivo se almacena en Azure Blob Storage (contenedor 'lienzostorage').
    Se crea un registro ArchivoLienzo y se devuelven los metadatos.
    La URL se genera con SAS token para acceso seguro sin necesidad de contenedor público.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    lienzo_id = request.POST.get('lienzo_id')
    if not lienzo_id:
        return JsonResponse({'error': 'Se requiere lienzo_id'}, status=400)

    try:
        lienzo = Lienzo.objects.get(pk=lienzo_id, user=user)
    except Lienzo.DoesNotExist:
        return JsonResponse({'error': 'Lienzo no encontrado'}, status=404)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'No se envió ningún archivo'}, status=400)

    # Validar tamaño (max 20 MB)
    MAX_SIZE = 20 * 1024 * 1024
    if uploaded_file.size > MAX_SIZE:
        return JsonResponse({'error': 'El archivo excede el límite de 20 MB'}, status=413)

    # Detectar tipo según extensión
    import os
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    tipo_map = {
        '.xlsx': 'excel', '.xls': 'excel', '.csv': 'excel',
        '.docx': 'word', '.doc': 'word',
        '.pdf': 'pdf',
        '.jpg': 'image', '.jpeg': 'image', '.png': 'image',
        '.gif': 'image', '.webp': 'image', '.bmp': 'image', '.svg': 'image',
    }
    tipo = tipo_map.get(ext, 'other')

    # Subir a Azure Blob Storage
    from django.conf import settings
    from captura.azure_storage import ensure_container_exists, get_blob_service_client
    from azure.storage.blob import ContentSettings
    from datetime import datetime, timedelta
    import uuid

    try:
        container_client = ensure_container_exists(settings.LIENZO_STORAGE_CONTAINER)
    except Exception:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(settings.LIENZO_STORAGE_CONTAINER)
        if not container_client.exists():
            container_client.create_container()

    # Nombre único para el blob: canvas/{lienzo_id}/{timestamp}_{uuid}.{ext}
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    blob_name = f"canvas/{lienzo_id}/{timestamp}_{unique_id}{ext}"

    # MIME type
    mime_map = {
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.svg': 'image/svg+xml',
    }
    content_type = mime_map.get(ext, 'application/octet-stream')

    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        uploaded_file.read(),
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )

    # Generar SAS token para acceso seguro (válido 24h)
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas
    account_key = getattr(settings, 'AZURE_STORAGE_ACCOUNT_KEY', '') or ''
    if account_key:
        sas_token = generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=blob_client.container_name,
            blob_name=blob_client.blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=24),
        )
        blob_url = f"{blob_client.url}?{sas_token}"
    else:
        blob_url = blob_client.url

    # Crear registro en BD
    archivo = ArchivoLienzo.objects.create(
        lienzo=lienzo,
        nombre=uploaded_file.name,
        tipo=tipo,
        blob_url=blob_url,
        blob_name=blob_name,
        tamano=uploaded_file.size,
    )

    return JsonResponse({
        'ok': True,
        'archivo': {
            'id': archivo.pk,
            'nombre': archivo.nombre,
            'tipo': archivo.tipo,
            'blob_url': archivo.blob_url,
            'tamano': archivo.tamano,
        }
    })


# ── PROXY: Servir imágenes/archivos del lienzo ─────────────────


def api_lienzo_media(request, archivo_id):
    """
    GET /canvas/api/media/<archivo_id>/
    Sirve un archivo del lienzo directamente desde Azure Blob Storage
    usando autenticación del servidor (no requiere SAS ni acceso público).
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    from .models import ArchivoLienzo
    archivo = get_object_or_404(ArchivoLienzo, pk=archivo_id, lienzo__user=user)

    from django.http import HttpResponse
    from django.conf import settings
    from captura.azure_storage import get_blob_service_client

    try:
        bsc = get_blob_service_client()
        container_client = bsc.get_container_client(settings.LIENZO_STORAGE_CONTAINER)
        blob_client = container_client.get_blob_client(archivo.blob_name)
        stream = blob_client.download_blob()
        props = blob_client.get_blob_properties()
        ct = props.content_settings.content_type if props.content_settings else 'application/octet-stream'
        data = stream.readall()
        resp = HttpResponse(data, content_type=ct)
        resp['Content-Disposition'] = f'inline; filename="{archivo.nombre}"'
        resp['Cache-Control'] = 'public, max-age=3600'
        return resp
    except Exception as e:
        logger.error(f"Error sirviendo archivo {archivo_id}: {e}")
        return HttpResponse(status=502)


# ── API: CREATE LINK ─────────────────────────────────────────────


@require_POST
@csrf_exempt
def api_link(request):
    """
    Valida y registra un enlace URL en el lienzo.
    (No se persiste en BD, solo se valida y devuelve para el nodo frontal)
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    data = json.loads(request.body)
    url = data.get('url', '').strip()
    titulo = data.get('titulo', '').strip()

    if not url:
        return JsonResponse({'error': 'Se requiere una URL'}, status=400)

    # Validar URL básica
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    if not titulo:
        titulo = url

    return JsonResponse({
        'ok': True,
        'enlace': {
            'url': url,
            'titulo': titulo,
        }
    })


# ── API: LIST ARCHIVOS ───────────────────────────────────────────


def api_archivos_list(request, lienzo_pk):
    """Lista los archivos subidos a un lienzo (para restauración)."""
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    try:
        lienzo = Lienzo.objects.get(pk=lienzo_pk, user=user)
    except Lienzo.DoesNotExist:
        return JsonResponse({'error': 'Lienzo no encontrado'}, status=404)

    archivos = ArchivoLienzo.objects.filter(lienzo=lienzo).values(
        'id', 'nombre', 'tipo', 'blob_url', 'blob_name', 'tamano', 'x', 'y'
    )
    return JsonResponse({'archivos': list(archivos)})


def api_lienzo_eliminar(request, pk):
    """
    POST /canvas/api/eliminar/<pk>/
    Elimina un lienzo con confirmación.
    """
    user = _get_current_user(request)
    lienzo = get_object_or_404(Lienzo, pk=pk)
    if user and lienzo.user != user:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    nombre = lienzo.nombre
    lienzo.delete()
    from django.shortcuts import redirect
    return redirect('canvas:list')

