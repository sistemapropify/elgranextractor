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
        result.append(entry)

    return JsonResponse({'propiedades': result})


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
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    try:
        matches = _get_matches_by_embedding(prop_id)
        if matches is not None:
            return JsonResponse({'matches': matches, 'total': len(matches)})
    except Exception as e:
        logger.warning(f"Embedding match failed for prop {prop_id}: {e}")

    # Fallback: usar matching estructural
    try:
        from matching.engine import ejecutar_matching_requerimiento
        reqs_con_match = ejecutar_matching_requerimiento(prop_id)
        matches = []
        for req_data in (reqs_con_match or []):
            matches.append({
                'id': str(req_data.get('requerimiento_id', '')),
                'titulo': req_data.get('titulo', req_data.get('cliente', 'Requerimiento')),
                'score_estructural': req_data.get('score', 0),
                'score_semantico': req_data.get('score_semantico', 0),
                'fecha': str(req_data.get('fecha', '')),
                'tipo': 'estructural',
            })
        return JsonResponse({'matches': matches, 'total': len(matches)})
    except Exception as e:
        logger.error(f"Fallback match also failed for prop {prop_id}: {e}")
        return JsonResponse({'matches': [], 'total': 0})


def _get_matches_by_embedding(prop_id: int):
    """
    Busca matches por cosine similarity de embeddings entre
    la propiedad (propiedadespropify) y los requerimientos (requerimientos_enbedados).
    Filtra por tipo de operación: propiedades en venta solo matchean con requerimientos de compra,
    propiedades en alquiler solo con requerimientos de alquiler.
    """
    coleccion_props = IntelligenceCollection.objects.filter(name='propiedadespropify').first()
    coleccion_reqs = IntelligenceCollection.objects.filter(name='requerimientos_enbedados').first()

    if not coleccion_props or not coleccion_reqs:
        return None

    # Obtener embedding de la propiedad y su tipo de operación
    prop_doc = IntelligenceDocument.objects.filter(
        collection=coleccion_props,
        source_id=str(prop_id),
    ).exclude(embedding__isnull=True).first()

    if not prop_doc or not prop_doc.embedding:
        return None

    prop_fv = prop_doc.field_values or {}
    prop_operation = (prop_fv.get('operation_type_name') or '').lower().strip()
    # Mapear: venta/compra → compra, alquiler → alquiler
    if prop_operation in ('venta', 'compra', 'permuta'):
        req_condicion_valida = ('compra', 'venta')
    elif prop_operation in ('alquiler', 'renta', 'anticresis'):
        req_condicion_valida = ('alquiler', 'anticresis', 'renta')
    else:
        req_condicion_valida = None  # sin filtro si no se puede determinar

    import struct
    import math

    prop_vec = struct.unpack('f' * 1024, prop_doc.embedding)

    matches = []
    req_docs = IntelligenceDocument.objects.filter(
        collection=coleccion_reqs,
    ).exclude(embedding__isnull=True).iterator()

    for req_doc in req_docs:
        try:
            req_fv = req_doc.field_values or {}
            
            # Filtrar por tipo de operación (compra vs alquiler)
            if req_condicion_valida:
                req_condicion = (req_fv.get('condicion') or '').lower().strip()
                if req_condicion and req_condicion not in req_condicion_valida:
                    continue
            
            req_vec = struct.unpack('f' * 1024, req_doc.embedding)
            similarity = _cosine_similarity(prop_vec, req_vec)
            if similarity > 0.5:
                matches.append({
                    'id': req_doc.source_id,
                    'titulo': req_fv.get('cliente', req_fv.get('nombre', f'Req #{req_doc.source_id}')),
                    'presupuesto': req_fv.get('presupuesto_monto'),
                    'moneda': req_fv.get('presupuesto_moneda', ''),
                    'distritos': req_fv.get('distritos', ''),
                    'tipo_propiedad': req_fv.get('tipo_propiedad', ''),
                    'score_semantico': round(similarity, 4),
                    'score_estructural': round(similarity * 100),
                    'fecha': str(req_doc.created_at.date()) if hasattr(req_doc.created_at, 'date') else '',
                    'tipo': 'semantico',
                })
        except Exception:
            continue

    matches.sort(key=lambda m: m['score_semantico'], reverse=True)
    return matches[:20]


def _cosine_similarity(a, b):
    """Calcula cosine similarity entre dos vectores."""
    import math
    dot = sum(av * bv for av, bv in zip(a, b))
    na = math.sqrt(sum(av * av for av in a))
    nb = math.sqrt(sum(bv * bv for bv in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


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

