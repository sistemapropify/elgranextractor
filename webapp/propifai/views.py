from django.shortcuts import render
from django.views.generic import ListView
from django.db.models import Count, Avg, Sum, F, Q
from django.db.models.functions import Coalesce
from django.db.models import FloatField, ExpressionWrapper
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
import json
from datetime import date, datetime
from .models import PropifaiProperty
from .mapeo_ubicaciones import (
    obtener_nombre_departamento,
    obtener_nombre_provincia,
    obtener_nombre_distrito,
    DEPARTAMENTOS, PROVINCIAS, DISTRITOS
)


class ListaPropiedadesPropifyView(ListView):
    """Vista para mostrar solo propiedades de la base de datos Propify."""
    model = PropifaiProperty
    template_name = 'propifai/lista_propiedades_propify_rediseno.html'
    context_object_name = 'propiedades'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Obtener parámetros de filtro de la URL
        tipo_propiedad = self.request.GET.get('tipo_propiedad')
        departamento = self.request.GET.get('departamento')
        precio_min = self.request.GET.get('precio_min')
        precio_max = self.request.GET.get('precio_max')
        habitaciones = self.request.GET.get('habitaciones')
        banos = self.request.GET.get('banos')

        # Aplicar filtros si existen
        if tipo_propiedad:
            queryset = queryset.filter(tipo_propiedad__icontains=tipo_propiedad)

        if departamento:
            queryset = queryset.filter(department__icontains=departamento)

        if precio_min:
            try:
                precio_min_val = float(precio_min)
                queryset = queryset.filter(price__gte=precio_min_val)
            except ValueError:
                pass

        if precio_max:
            try:
                precio_max_val = float(precio_max)
                queryset = queryset.filter(price__lte=precio_max_val)
            except ValueError:
                pass

        if habitaciones:
            try:
                habitaciones_val = int(habitaciones)
                queryset = queryset.filter(bedrooms=habitaciones_val)
            except ValueError:
                pass

        if banos:
            try:
                banos_val = int(banos)
                queryset = queryset.filter(bathrooms=banos_val)
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener valores únicos para los filtros
        context['departamentos'] = PropifaiProperty.objects.values_list('department', flat=True).distinct().order_by('department')
        
        # Agregar información adicional para cada propiedad
        propiedades_con_info = []
        for propiedad in context['propiedades']:
            # Obtener nombres mapeados de ubicación
            departamento_nombre = propiedad.departamento_nombre if hasattr(propiedad, 'departamento_nombre') else propiedad.department
            provincia_nombre = propiedad.provincia_nombre if hasattr(propiedad, 'provincia_nombre') else propiedad.province
            distrito_nombre = propiedad.distrito_nombre if hasattr(propiedad, 'distrito_nombre') else propiedad.district
            ubicacion_completa = propiedad.ubicacion_completa if hasattr(propiedad, 'ubicacion_completa') else f"{distrito_nombre}, {provincia_nombre}, {departamento_nombre}"
            
            propiedades_con_info.append({
                'id': propiedad.id,
                'code': propiedad.code,
                'title': propiedad.title,
                'description': propiedad.description,
                'tipo': 'Propiedad',  # Valor por defecto
                'tipo_propiedad': 'Propiedad',  # Para filtros
                'precio': float(propiedad.price) if propiedad.price else None,
                'precio_usd': float(propiedad.price) if propiedad.price else None,
                'departamento': propiedad.department,  # Índice original
                'departamento_nombre': departamento_nombre,  # Nombre mapeado
                'provincia': propiedad.province,  # Índice original
                'provincia_nombre': provincia_nombre,  # Nombre mapeado
                'distrito': propiedad.district,  # Índice original
                'distrito_nombre': distrito_nombre,  # Nombre mapeado
                'ubicacion_completa': ubicacion_completa,
                'bedrooms': propiedad.bedrooms,
                'bathrooms': propiedad.bathrooms,
                'built_area': float(propiedad.built_area) if propiedad.built_area else None,
                'land_area': float(propiedad.land_area) if propiedad.land_area else None,
                'imagen_url': propiedad.imagen_url,
                'availability_status': propiedad.availability_status,
                'is_draft': propiedad.is_draft,
                'is_active': propiedad.is_active,
                'created_at': propiedad.created_at,
                'updated_at': propiedad.updated_at,
                # Campos adicionales para compatibilidad
                'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
                'titulo': f"{propiedad.title or 'Propiedad'} en {departamento_nombre or propiedad.department or ''}",
                'codigo': propiedad.code,
                'descripcion': propiedad.description,
            })
        
        context['propiedades'] = propiedades_con_info
        
        return context


def lista_propiedades_propify_simple(request):
    """Vista simple para listar propiedades Propify en formato JSON."""
    propiedades = PropifaiProperty.objects.all()[:50]  # Limitar a 50 para pruebas
    
    propiedades_list = []
    for propiedad in propiedades:
        # Obtener nombres mapeados de ubicación
        departamento_nombre = propiedad.departamento_nombre if hasattr(propiedad, 'departamento_nombre') else propiedad.department
        provincia_nombre = propiedad.provincia_nombre if hasattr(propiedad, 'provincia_nombre') else propiedad.province
        distrito_nombre = propiedad.distrito_nombre if hasattr(propiedad, 'distrito_nombre') else propiedad.district
        ubicacion_completa = propiedad.ubicacion_completa if hasattr(propiedad, 'ubicacion_completa') else f"{distrito_nombre}, {provincia_nombre}, {departamento_nombre}"
        
        propiedades_list.append({
            'id': propiedad.id,
            'code': propiedad.code,
            'title': propiedad.title,
            'tipo': 'Propiedad',
            'tipo_propiedad': 'Propiedad',
            'precio': float(propiedad.price) if propiedad.price else None,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,  # Índice original
            'departamento_nombre': departamento_nombre,  # Nombre mapeado
            'provincia': propiedad.province,  # Índice original
            'provincia_nombre': provincia_nombre,  # Nombre mapeado
            'distrito': propiedad.district,  # Índice original
            'distrito_nombre': distrito_nombre,  # Nombre mapeado
            'ubicacion_completa': ubicacion_completa,
            'bedrooms': propiedad.bedrooms,
            'bathrooms': propiedad.bathrooms,
            'built_area': float(propiedad.built_area) if propiedad.built_area else None,
            'land_area': float(propiedad.land_area) if propiedad.land_area else None,
            'imagen_url': propiedad.imagen_url,
            'availability_status': propiedad.availability_status,
            'is_draft': propiedad.is_draft,
            'is_active': propiedad.is_active,
            'created_at': propiedad.created_at.isoformat() if propiedad.created_at else None,
            'updated_at': propiedad.updated_at.isoformat() if propiedad.updated_at else None,
            'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
            'titulo': f"{propiedad.title or 'Propiedad'} en {departamento_nombre or propiedad.department or ''}",
            'codigo': propiedad.code,
            'descripcion': propiedad.description,
        })
    
    return JsonResponse({'propiedades': propiedades_list})


def vista_propiedades_simple_html(request):
    """Vista simple para mostrar propiedades en HTML."""
    propiedades = PropifaiProperty.objects.all()[:20]
    
    propiedades_list = []
    for propiedad in propiedades:
        propiedades_list.append({
            'id': propiedad.id,
            'code': propiedad.code,
            'title': propiedad.title,
            'price': propiedad.price,
            'department': propiedad.department,
            'district': propiedad.district,
            'bedrooms': propiedad.bedrooms,
            'bathrooms': propiedad.bathrooms,
            'built_area': propiedad.built_area,
            'land_area': propiedad.land_area,
            'availability_status': propiedad.availability_status,
            'is_draft': propiedad.is_draft,
        })
    
    context = {
        'propiedades': propiedades_list,
        'total': len(propiedades_list)
    }
    
    return render(request, 'propifai/propiedades_simple.html', context)


def api_propiedades_json(request):
    """API para obtener propiedades en formato JSON."""
    propiedades = PropifaiProperty.objects.all()[:100]
    
    propiedades_list = []
    for propiedad in propiedades:
        propiedades_list.append({
            'id': propiedad.id,
            'es_propify': True,
            'tipo': propiedad.tipo_propiedad,
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio': float(propiedad.price) if propiedad.price else None,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,
            'provincia': propiedad.province,
            'distrito': propiedad.district,
            'bedrooms': propiedad.bedrooms,
            'bathrooms': propiedad.bathrooms,
            'built_area': float(propiedad.built_area) if propiedad.built_area else None,
            'land_area': float(propiedad.land_area) if propiedad.land_area else None,
            'imagen_url': propiedad.imagen_url,  # Usar la propiedad imagen_url del modelo
            'availability_status': propiedad.availability_status,
            'is_draft': propiedad.is_draft,
            'is_active': propiedad.is_active,
            'created_at': propiedad.created_at.isoformat() if propiedad.created_at else None,
            'updated_at': propiedad.updated_at.isoformat() if propiedad.updated_at else None,
            'code': propiedad.code,
            'title': propiedad.title,
            'description': propiedad.description,
        })
    
    return JsonResponse({'propiedades': propiedades_list})


def dashboard_calidad_cartera(request):
    """
    Dashboard de calidad de cartera de propiedades Propifai.
    Muestra matriz de completitud de datos y análisis agregados.
    """
    # Obtener todas las propiedades, ordenadas por fecha de creación descendente (más recientes primero)
    # Anotar con conteo de eventos y fechas de visitas
    from django.db.models import Count, Min, Max, Case, When, Value, BooleanField
    propiedades = PropifaiProperty.objects.all().order_by('-created_at')
    propiedades = propiedades.annotate(
        total_eventos=Count('event', distinct=True),
        primera_visita=Min('event__fecha_evento'),
        ultima_visita=Max('event__fecha_evento'),
        tiene_lead=Case(
            When(event__lead_id__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ),
        tiene_propuesta=Case(
            When(event__proposal_id__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).distinct()
    
    # Filtros desde parámetros GET
    tipo_filtro = request.GET.get('tipo', '').strip()
    distrito_filtro = request.GET.get('distrito', '').strip()
    agente_filtro = request.GET.get('agente', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    
    print(f"[DEBUG FILTROS] tipo='{tipo_filtro}', distrito='{distrito_filtro}', agente='{agente_filtro}', estado='{estado_filtro}'")
    
    if tipo_filtro:
        # Filtrar por tipo de propiedad (property_type_id)
        # Necesitamos obtener property_type_id desde property_types donde name coincida
        from django.db import connections
        conn_temp = connections['propifai']
        with conn_temp.cursor() as cursor:
            cursor.execute("SELECT id FROM property_types WHERE name LIKE %s", [f'%{tipo_filtro}%'])
            tipo_ids = [row[0] for row in cursor.fetchall()]
            if tipo_ids:
                # Obtener IDs de propiedades que tengan esos property_type_id
                # Construir placeholders para IN
                placeholders = ','.join(['%s'] * len(tipo_ids))
                query = f"SELECT id FROM properties WHERE property_type_id IN ({placeholders})"
                cursor.execute(query, tipo_ids)
                prop_ids = [row[0] for row in cursor.fetchall()]
                if prop_ids:
                    propiedades = propiedades.filter(id__in=prop_ids)
    
    if distrito_filtro:
        # Filtrar por nombre de distrito (usando district_map)
        # Primero obtener district_id desde properties_district donde name coincida
        from django.db import connections
        conn_temp = connections['propifai']
        with conn_temp.cursor() as cursor:
            cursor.execute("SELECT id FROM properties_district WHERE name LIKE %s", [f'%{distrito_filtro}%'])
            distrito_ids = [row[0] for row in cursor.fetchall()]
            if distrito_ids:
                propiedades = propiedades.filter(district__in=distrito_ids)
    
    if agente_filtro:
        # Filtrar por agente (responsible_id)
        # Primero obtener user_id desde users donde username coincida
        from django.db import connections
        conn_temp = connections['propifai']
        with conn_temp.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username LIKE %s", [f'%{agente_filtro}%'])
            user_ids = [row[0] for row in cursor.fetchall()]
            if user_ids:
                # Obtener IDs de propiedades que tengan esos responsible_id
                # Construir placeholders para IN
                placeholders = ','.join(['%s'] * len(user_ids))
                query = f"SELECT id FROM properties WHERE responsible_id IN ({placeholders})"
                cursor.execute(query, user_ids)
                prop_ids = [row[0] for row in cursor.fetchall()]
                if prop_ids:
                    propiedades = propiedades.filter(id__in=prop_ids)

    # Filtro por estado (availability_status o borrador)
    if estado_filtro:
        # Mapeo inverso de español a inglés (y borrador)
        estado_a_ingles = {
            'disponible': 'available',
            'vendido': 'sold',
            'reservado': 'reserved',
            'catchment': 'catchment',
            'pausado': 'paused',
            'nodisponible': 'unavailable',
            'borrador': 'borrador',
            'sinestado': 'sinestado',
        }
        estado_ingles = estado_a_ingles.get(estado_filtro, estado_filtro)
        
        if estado_ingles == 'borrador':
            propiedades = propiedades.filter(is_draft=True)
        elif estado_ingles == 'sinestado':
            propiedades = propiedades.filter(availability_status__isnull=True)
        else:
            propiedades = propiedades.filter(availability_status=estado_ingles)

    total_db = propiedades.count()
    print(f"[DEBUG] Total propiedades en DB después de filtros: {total_db}")
    print(f"[DEBUG] Filtros aplicados: tipo={tipo_filtro}, distrito={distrito_filtro}, agente={agente_filtro}, estado={estado_filtro}")

    # Obtener mapeos de property_types, users y distritos desde la base de datos propifai
    from django.db import connections
    conn = connections['propifai']
    property_type_map = {}
    user_map = {}
    district_map = {}
    with conn.cursor() as cursor:
        # Mapeo property_type_id -> name
        cursor.execute("SELECT id, name FROM property_types")
        for row in cursor.fetchall():
            property_type_map[row[0]] = row[1]
        # Mapeo user id -> username
        cursor.execute("SELECT id, username FROM users")
        for row in cursor.fetchall():
            user_map[row[0]] = row[1]
        # Mapeo district id -> name
        cursor.execute("SELECT id, name FROM properties_district")
        for row in cursor.fetchall():
            district_map[str(row[0])] = row[1]  # district es string en properties
    
    print(f"[DEBUG] user_map size: {len(user_map)}")
    # Buscar usuarios específicos
    for uid, uname in user_map.items():
        if 'francisco' in uname.lower() or 'jpastor' in uname.lower():
            print(f"[DEBUG] Usuario encontrado: {uid} -> {uname}")
    
    # Obtener property_type_id, created_by_id y responsible_id para cada propiedad mediante consulta raw
    # Usaremos una consulta que obtenga todos los IDs necesarios
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, property_type_id, created_by_id, responsible_id, wp_post_id, wp_last_sync FROM properties")
        prop_extras = {}
        for row in cursor.fetchall():
            prop_id, pt_id, cb_id, resp_id, wp_post_id, wp_last_sync = row
            prop_extras[prop_id] = {
                'property_type_id': pt_id,
                'created_by_id': cb_id,
                'responsible_id': resp_id,
                'wp_post_id': wp_post_id,
                'wp_last_sync': wp_last_sync,
            }
    
    # Obtener información financiera (initial_commission_percentage) desde property_financial_info
    financial_info = {}
    with conn.cursor() as cursor:
        cursor.execute("SELECT property_id, initial_commission_percentage FROM property_financial_info")
        for row in cursor.fetchall():
            prop_id, commission = row
            financial_info[prop_id] = commission
    
    # Calcular completitud para cada propiedad
    campos_clave = [
        'exact_address', 'coordinates', 'land_area', 'built_area', 'price',
        'bedrooms', 'bathrooms', 'description', 'district', 'title'
    ]
    
    propiedades_con_score = []
    print(f"[DEBUG] Total propiedades a procesar: {propiedades.count()}")
    for i, prop in enumerate(propiedades):
        completos = 0
        faltantes = []
        for campo in campos_clave:
            valor = getattr(prop, campo, None)
            if valor not in (None, '', 0):
                completos += 1
            else:
                faltantes.append(campo)
        score = int((completos / len(campos_clave)) * 100) if campos_clave else 0
        prop.completitud_score = score
        prop.campos_faltantes = faltantes
        # Determinar filtro de estado para el frontend
        if prop.is_draft:
            status_filter = 'borrador'
        else:
            # Mapear availability_status a español
            mapping = {
                'available': 'disponible',
                'sold': 'vendido',
                'reserved': 'reservado',
                'catchment': 'catchment',
                'paused': 'pausado',
                'unavailable': 'nodisponible',
            }
            status_filter = mapping.get(prop.availability_status, prop.availability_status or 'sinestado')
        prop.status_filter = status_filter
        # Atributos adicionales para las columnas del template
        prop.real_address = getattr(prop, 'real_address', None) or prop.exact_address
        
        # Determinar tipo de propiedad real desde property_types
        tipo_propiedad_valor = '—'
        prop_extras_data = prop_extras.get(prop.id)
        if prop_extras_data:
            pt_id = prop_extras_data['property_type_id']
            if pt_id and pt_id in property_type_map:
                tipo_propiedad_valor = property_type_map[pt_id]
        prop.property_type = tipo_propiedad_valor
        
        # Determinar agente (responsible_id) y usuario (created_by_id)
        agent_name = '—'
        user_name = '—'
        if prop_extras_data:
            cb_id = prop_extras_data['created_by_id']
            if cb_id and cb_id in user_map:
                user_name = user_map[cb_id]
            # Obtener responsible_id para agente
            resp_id = prop_extras_data.get('responsible_id')
            if resp_id and resp_id in user_map:
                agent_name = user_map[resp_id]
        prop.agent = agent_name
        prop.user = user_name
        
        # Determinar nombre del distrito
        district_id = prop.district
        district_name = district_map.get(str(district_id), district_id) if district_id else '—'
        prop.district_name = district_name
        
        # Obtener comisión inicial desde financial_info
        commission = financial_info.get(prop.id)
        prop.initial_commission_percentage = commission
        
        # Obtener wp_post_id y wp_last_sync desde prop_extras
        wp_post_id = None
        wp_last_sync = None
        if prop_extras_data:
            wp_post_id = prop_extras_data.get('wp_post_id')
            wp_last_sync = prop_extras_data.get('wp_last_sync')
        prop.wp_post_id = wp_post_id
        prop.wp_last_sync = wp_last_sync
        
        # Calcular días en publicación (diferencia entre hoy y created_at)
        if prop.created_at:
            hoy = date.today()
            dias = (hoy - prop.created_at.date()).days
            prop.dias_publicacion = max(dias, 0)  # evitar negativos
        else:
            prop.dias_publicacion = None
        
        # Atributos de visitas (ya anotados en el queryset)
        prop.total_eventos = prop.total_eventos
        prop.primera_visita = prop.primera_visita
        prop.ultima_visita = prop.ultima_visita
        prop.tiene_lead = prop.tiene_lead
        prop.tiene_propuesta = prop.tiene_propuesta
        
        propiedades_con_score.append(prop)
        if i % 20 == 0:
            print(f"[DEBUG] Procesada propiedad {i}: {prop.code} - Eventos: {prop.total_eventos}")

    print(f"[DEBUG] Propiedades con score calculado: {len(propiedades_con_score)}")
    
    # Conteo por availability_status
    from collections import Counter
    status_counts = Counter(p.availability_status for p in propiedades)
    print(f"\n[DEBUG] ********** CONTEOS POR ESTADO **********")
    for status, count in sorted(status_counts.items()):
        print(f"[DEBUG]   {status}: {count}")
    print(f"[DEBUG] ****************************************\n")
    
    # Mapear conteos a español para los botones de filtro
    estado_a_espanol = {
        'available': 'disponible',
        'sold': 'vendido',
        'reserved': 'reservado',
        'catchment': 'catchment',
        'paused': 'pausado',
        'unavailable': 'nodisponible',
    }
    # Estadísticas generales
    total_real = total_db  # 73
    props_disponibles = propiedades.filter(is_draft=False).count()  # no borradores (69)
    props_borradores = propiedades.filter(is_draft=True).count()    # 4
    props_sin_gps = propiedades.filter(coordinates__isnull=True).count()
    
    conteo_estados = {}
    for eng, count in status_counts.items():
        esp = estado_a_espanol.get(eng, eng)
        conteo_estados[esp] = count
    # Agregar borradores (is_draft=True)
    conteo_estados['borrador'] = props_borradores
    completitud_promedio = sum(p.completitud_score for p in propiedades_con_score) / total_real if total_real else 0
    print(f"[DEBUG] total_real: {total_real}")
    print(f"[DEBUG] props_disponibles: {props_disponibles}")
    
    # Precio/m² mediano (solo propiedades con built_area > 0)
    propiedades_con_precio_m2 = propiedades.filter(
        price__isnull=False,
        built_area__isnull=False,
        built_area__gt=0
    ).annotate(
        precio_m2=ExpressionWrapper(F('price') / F('built_area'), output_field=FloatField())
    )
    precios_m2 = [p.precio_m2 for p in propiedades_con_precio_m2 if p.precio_m2]
    precio_mediano_general = sorted(precios_m2)[len(precios_m2)//2] if precios_m2 else 0

    # Agregados por agente (usando responsible_id)
    stats_por_agente = []
    agent_stats = {}
    
    # Inicializar estadísticas por agente
    for prop in propiedades_con_score:
        prop_extras_data = prop_extras.get(prop.id)
        if prop_extras_data:
            resp_id = prop_extras_data.get('responsible_id')
            agent_key = resp_id if resp_id else 'sin_asignar'
        else:
            agent_key = 'sin_asignar'
        
        if agent_key not in agent_stats:
            agent_stats[agent_key] = {
                'responsible_id': resp_id if resp_id else None,
                'num_props': 0,
                'sum_completitud': 0,
                'props_sin_gps': 0,
                'precios': []
            }
        
        stats = agent_stats[agent_key]
        stats['num_props'] += 1
        stats['sum_completitud'] += prop.completitud_score
        if not prop.coordinates:
            stats['props_sin_gps'] += 1
        if prop.price:
            stats['precios'].append(prop.price)
    
    # Convertir a lista para el template
    for agent_key, stats in agent_stats.items():
        if agent_key == 'sin_asignar':
            agente_nombre = 'Sin asignar'
        else:
            # Buscar nombre en user_map
            agente_nombre = user_map.get(stats['responsible_id'], f"Agente {stats['responsible_id']}")
        
        num_props = stats['num_props']
        completitud_prom = stats['sum_completitud'] / num_props if num_props else 0
        
        # Calcular precio mediano para este agente
        precios_agente = sorted(stats['precios'])
        precio_mediano = precios_agente[len(precios_agente)//2] if precios_agente else 0
        
        stats_por_agente.append({
            'agente': agente_nombre,
            'num_props': num_props,
            'completitud_promedio': completitud_prom,
            'props_sin_gps': stats['props_sin_gps'],
            'precio_mediano': precio_mediano
        })
    
    # Ordenar por número de propiedades (descendente)
    stats_por_agente.sort(key=lambda x: x['num_props'], reverse=True)
    
    # Depuración: imprimir todos los agentes
    print("[DEBUG] === AGENTES CALCULADOS ===")
    for stat in stats_por_agente:
        print(f"  {stat['agente']}: {stat['num_props']} propiedades")
    
    # Buscar específicamente Francisco2026 y JPastor0
    for stat in stats_por_agente:
        if 'francisco2026' in stat['agente'].lower() or 'jpastor0' in stat['agente'].lower():
            print(f"[DEBUG] Encontrado agente especial: {stat['agente']}")
    
    # Mostrar todos los agentes (no limitar a top 10)
    # stats_por_agente = stats_por_agente  # sin límite
    total_agentes = len(stats_por_agente)
    print(f"[DEBUG] Total agentes: {total_agentes}")

    # Agregados por distrito (usando nombre desde properties_district)
    stats_por_distrito = []
    
    # Calcular completitud por distrito usando propiedades_con_score
    distrito_scores = {}
    for prop in propiedades_con_score:
        district_id = prop.district
        if district_id not in distrito_scores:
            distrito_scores[district_id] = {
                'num_props': 0,
                'sum_completitud': 0,
                'precios': [],
                'activas': 0
            }
        stats = distrito_scores[district_id]
        stats['num_props'] += 1
        stats['sum_completitud'] += prop.completitud_score
        if prop.price:
            stats['precios'].append(prop.price)
        if prop.is_active:
            stats['activas'] += 1
    
    # Convertir a lista ordenada por número de propiedades
    distrito_items = []
    for district_id, stats in distrito_scores.items():
        district_name = district_map.get(str(district_id), district_id) if district_id else 'Sin distrito'
        completitud_prom = stats['sum_completitud'] / stats['num_props'] if stats['num_props'] else 0
        
        # Calcular precio mediano
        precios_sorted = sorted(stats['precios'])
        precio_mediano = precios_sorted[len(precios_sorted)//2] if precios_sorted else 0
        
        distrito_items.append({
            'district_id': district_id,
            'district_name': district_name,
            'num_props': stats['num_props'],
            'precio_mediano': precio_mediano,
            'props_activas': stats['activas'],
            'completitud_promedio': completitud_prom
        })
    
    # Ordenar por número de propiedades (descendente)
    distrito_items.sort(key=lambda x: x['num_props'], reverse=True)
    
    # Calcular total de propiedades en todos los distritos
    total_props_distritos = sum(item['num_props'] for item in distrito_items)
    
    # Tomar top 10 para mostrar
    distrito_items_top10 = distrito_items[:10]
    
    # Calcular propiedades en "Otros" (distritos fuera del top 10)
    props_en_top10 = sum(item['num_props'] for item in distrito_items_top10)
    props_en_otros = total_props_distritos - props_en_top10
    
    print(f"[DEBUG] === DISTRITOS CALCULADOS (total: {len(distrito_scores)}, mostrando: {len(distrito_items_top10)}) ===")
    print(f"[DEBUG] Total propiedades en distritos: {total_props_distritos}")
    print(f"[DEBUG] Propiedades en top 10: {props_en_top10}")
    print(f"[DEBUG] Propiedades en otros distritos: {props_en_otros}")
    
    for item in distrito_items_top10:
        print(f"[DEBUG] Distrito ID {item['district_id']} -> {item['district_name']}: {item['num_props']} propiedades, completitud: {item['completitud_promedio']:.1f}%")
        stats_por_distrito.append({
            'distrito': item['district_name'],
            'num_props': item['num_props'],
            'precio_mediano': item['precio_mediano'],
            'props_activas': item['props_activas'],
            'completitud_promedio': item['completitud_promedio']
        })
    
    # Agregar fila "Otros" si hay propiedades fuera del top 10
    if props_en_otros > 0:
        # Calcular promedio de completitud para "Otros"
        otros_items = distrito_items[10:]
        completitud_prom_otros = 0
        precio_mediano_otros = 0
        props_activas_otros = 0
        
        if otros_items:
            # Calcular completitud promedio ponderada
            sum_completitud = sum(item['num_props'] * item['completitud_promedio'] for item in otros_items)
            completitud_prom_otros = sum_completitud / props_en_otros if props_en_otros else 0
            
            # Calcular precio mediano combinado
            todos_precios = []
            for item in otros_items:
                # Obtener precios del distrito (necesitaríamos almacenarlos)
                # Por simplicidad, usamos el precio mediano del distrito
                if item['precio_mediano'] > 0:
                    todos_precios.extend([item['precio_mediano']] * item['num_props'])
            
            if todos_precios:
                precio_mediano_otros = sorted(todos_precios)[len(todos_precios)//2]
            
            # Calcular propiedades activas
            props_activas_otros = sum(item['props_activas'] for item in otros_items)
        
        stats_por_distrito.append({
            'distrito': 'Otros distritos',
            'num_props': props_en_otros,
            'precio_mediano': precio_mediano_otros,
            'props_activas': props_activas_otros,
            'completitud_promedio': completitud_prom_otros
        })
        print(f"[DEBUG] Agregado 'Otros distritos': {props_en_otros} propiedades, completitud: {completitud_prom_otros:.1f}%")

    # Agregados por tipo (availability_status) - mostrando siempre en español
    stats_por_tipo = []
    
    # Mapeo de estados inglés a español
    estado_a_espanol = {
        'available': 'disponible',
        'sold': 'vendido',
        'reserved': 'reservado',
        'catchment': 'catchment',
        'paused': 'pausado',
        'unavailable': 'nodisponible',
        'sinestado': 'sin estado'
    }
    
    # Calcular completitud por tipo usando propiedades_con_score
    tipo_scores = {}
    for prop in propiedades_con_score:
        tipo_ingles = prop.availability_status or 'sinestado'
        # Convertir a español para consistencia
        tipo = estado_a_espanol.get(tipo_ingles, tipo_ingles)
        
        if tipo not in tipo_scores:
            tipo_scores[tipo] = {
                'num_props': 0,
                'sum_completitud': 0,
                'tipo_original': tipo_ingles  # Guardar para debug
            }
        stats = tipo_scores[tipo]
        stats['num_props'] += 1
        stats['sum_completitud'] += prop.completitud_score
    
    # Convertir a lista ordenada por número de propiedades
    tipo_items = []
    for tipo, stats in tipo_scores.items():
        completitud_prom = stats['sum_completitud'] / stats['num_props'] if stats['num_props'] else 0
        tipo_items.append({
            'tipo': tipo,
            'num_props': stats['num_props'],
            'completitud_promedio': completitud_prom,
            'tipo_original': stats.get('tipo_original', tipo)
        })
    
    # Ordenar por número de propiedades (descendente)
    tipo_items.sort(key=lambda x: x['num_props'], reverse=True)
    
    print(f"[DEBUG] === TIPOS (availability_status) CALCULADOS ===")
    for item in tipo_items:
        print(f"[DEBUG] Tipo '{item['tipo_original']}' -> '{item['tipo']}': {item['num_props']} propiedades, completitud: {item['completitud_promedio']:.1f}%")
        stats_por_tipo.append({
            'tipo': item['tipo'],
            'num_props': item['num_props'],
            'completitud_promedio': item['completitud_promedio']
        })
    
    # Agregar fila para "Disponibles (no borradores)"
    stats_por_tipo.append({
        'tipo': 'Disponibles (no borradores)',
        'num_props': props_disponibles,
        'completitud_promedio': completitud_promedio
    })
    print(f"[DEBUG] Disponibles (no borradores): {props_disponibles} propiedades, completitud: {completitud_promedio:.1f}%")

    # Agregados por rango de valor (calculado dinámicamente)
    stats_por_valor = []
    rangos = [
        (0, 100000, '0-100k'),
        (100000, 300000, '100k-300k'),
        (300000, 600000, '300k-600k'),
        (600000, float('inf'), '600k+')
    ]
    
    for min_precio, max_precio, etiqueta in rangos:
        if max_precio == float('inf'):
            props_en_rango = propiedades.filter(price__gte=min_precio)
        else:
            props_en_rango = propiedades.filter(price__gte=min_precio, price__lt=max_precio)
        
        num_props = props_en_rango.count()
        
        # Calcular completitud promedio para este rango
        if num_props > 0:
            # Obtener propiedades con score para calcular completitud
            props_con_score_en_rango = [
                p for p in propiedades_con_score
                if p.price and p.price >= min_precio and
                (max_precio == float('inf') or p.price < max_precio)
            ]
            if props_con_score_en_rango:
                completitud_prom = sum(p.completitud_score for p in props_con_score_en_rango) / len(props_con_score_en_rango)
            else:
                completitud_prom = 0
        else:
            completitud_prom = 0
        
        stats_por_valor.append({
            'rango': etiqueta,
            'num_props': num_props,
            'completitud_promedio': completitud_prom
        })

    # Preparar opciones para los filtros
    # Tipos de propiedad únicos (de property_type_map)
    tipos_propiedad_opciones = sorted(set(property_type_map.values()))
    # Distritos únicos (de district_map)
    distritos_opciones = sorted(set(district_map.values()))
    # Agentes únicos (de stats_por_agente)
    agentes_opciones = sorted(set(stat['agente'] for stat in stats_por_agente if stat['agente'] != 'Sin asignar'))
    
    # Construir query string sin el parámetro 'estado' para los botones de filtro rápido
    from django.http import QueryDict
    params_sin_estado = request.GET.copy()
    if 'estado' in params_sin_estado:
        del params_sin_estado['estado']
    query_sin_estado = params_sin_estado.urlencode()

    context = {
        'propiedades': propiedades_con_score,
        'properties': propiedades_con_score,  # alias para el template
        'total_real': total_real,
        'props_disponibles': props_disponibles,
        'props_borradores': props_borradores,
        'props_sin_gps': props_sin_gps,
        'completitud_promedio': completitud_promedio,
        'precio_mediano_general': precio_mediano_general,
        'stats_por_agente': stats_por_agente,
        'stats_por_distrito': stats_por_distrito,
        'stats_por_tipo': stats_por_tipo,
        'stats_por_valor': stats_por_valor,
        'conteo_estados': conteo_estados,
        # Opciones de filtro
        'tipos_propiedad_opciones': tipos_propiedad_opciones,
        'distritos_opciones': distritos_opciones,
        'agentes_opciones': agentes_opciones,
        # Valores actuales de filtro (para mantener en los selects)
        'filtro_tipo_actual': tipo_filtro,
        'filtro_distrito_actual': distrito_filtro,
        'filtro_agente_actual': agente_filtro,
        # Query string sin estado para filtros rápidos
        'query_sin_estado': query_sin_estado,
    }
    return render(request, 'propifai/dashboard_calidad_cartera.html', context)


from django.db.models import Count, Min, Max, Q, F, Value, BooleanField, Case, When, ExpressionWrapper
from django.db.models.functions import Coalesce, TruncDate
from django.core.serializers.json import DjangoJSONEncoder
import json
from datetime import date
from django.utils.timezone import now
from .models import PropifaiProperty, Event


def property_visits_dashboard(request):
    """
    Vista principal del dashboard de visitas y actividad por propiedad.
    """
    # Obtener todas las propiedades con select_related a status, distrito, zona, tipo de propiedad, agente asignado
    # Nota: En nuestro modelo PropifaiProperty no tenemos FK a status, distrito, etc. Son campos de texto.
    # Vamos a usar los campos existentes: availability_status (status), district (distrito), urbanization (zona)
    # property_type no existe, pero podemos usar property_type_id? No está en el modelo.
    # Para simplificar, vamos a traer las propiedades y anotar eventos.
    
    properties = PropifaiProperty.objects.all()
    
    # Anotar con conteo de eventos y fechas
    # Usamos event (relación inversa) porque Event tiene ForeignKey a PropifaiProperty
    properties = properties.annotate(
        total_eventos=Count('event', distinct=True),
        primera_visita=Min('event__fecha_evento'),
        ultima_visita=Max('event__fecha_evento'),
        tiene_lead=Case(
            When(event__lead_id__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ),
        tiene_propuesta=Case(
            When(event__proposal_id__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).distinct()
    
    # Serializar a JSON
    properties_list = []
    for prop in properties:
        # Obtener nombres de status, distrito, zona, tipo, agente (si existen)
        status_name = prop.availability_status if prop.availability_status else 'Sin estado'
        distrito_name = prop.district if prop.district else 'Sin distrito'
        zona_name = prop.urbanization if prop.urbanization else 'Sin zona'
        tipo_name = prop.tipo_propiedad if hasattr(prop, 'tipo_propiedad') else 'Propiedad'
        agente_name = 'Sin agente'  # No tenemos agente asignado en el modelo
        
        # Calcular días en cartera (diferencia entre created_at y hoy)
        dias_en_cartera = 0
        if prop.created_at:
            from datetime import date
            hoy = date.today()
            dias_en_cartera = (hoy - prop.created_at.date()).days
        
        # Calcular frecuencia de visitas (días entre primera y última visita)
        frecuencia_visitas = 'N/A'
        if prop.primera_visita and prop.ultima_visita and prop.total_eventos > 1:
            dias = (prop.ultima_visita - prop.primera_visita).days
            frecuencia_visitas = f"{(dias / (prop.total_eventos - 1)):.1f} días"
        
        properties_list.append({
            'id': prop.id,
            'code': prop.code,
            'title': prop.title,
            'address': prop.real_address or prop.exact_address or 'Sin dirección',
            'property_type': tipo_name,
            'district': distrito_name,
            'zone': zona_name,
            'status': status_name,
            'status_code': prop.availability_status,
            'price': float(prop.price) if prop.price else None,
            'agent_name': agente_name,
            'total_eventos': prop.total_eventos,
            'primera_visita': prop.primera_visita.isoformat() if prop.primera_visita else None,
            'ultima_visita': prop.ultima_visita.isoformat() if prop.ultima_visita else None,
            'tiene_lead': prop.tiene_lead,
            'tiene_propuesta': prop.tiene_propuesta,
            'dias_en_cartera': dias_en_cartera,
            'frecuencia_visitas': frecuencia_visitas,
            'created_at': prop.created_at.isoformat() if prop.created_at else None,
        })
    
    # Convertir a JSON usando DjangoJSONEncoder
    properties_json = json.dumps(properties_list, cls=DjangoJSONEncoder)
    
    # Pasar al template
    context = {
        'properties_json': properties_json,
    }
    return render(request, 'propifai/property_visits_dashboard.html', context)


def property_events_api(request, property_id):
    """
    Endpoint API que devuelve el historial completo de eventos de una propiedad.
    """
    from .models import Event, EventType, User
    events = Event.objects.filter(property_id=property_id).select_related(
        'event_type', 'assigned_agent'
    ).order_by('-fecha_evento', '-hora_inicio')
    
    events_list = []
    for event in events:
        events_list.append({
            'id': event.id,
            'code': event.code,
            'titulo': event.titulo,
            'fecha_evento': event.fecha_evento.date().isoformat() if event.fecha_evento else None,
            'hora_inicio': event.hora_inicio.isoformat() if event.hora_inicio else None,
            'hora_fin': event.hora_fin.isoformat() if event.hora_fin else None,
            'detalle': event.detalle,
            'event_type_nombre': event.event_type.name if event.event_type else None,
            'event_type_color': event.event_type.color if event.event_type else None,
            'assigned_agent_nombre': event.assigned_agent.nombre_completo if event.assigned_agent else None,
            'status': event.status,
            'seguimiento': event.seguimiento,
            'rejection_reason': event.rejection_reason,
            'lead_id': event.lead_id,
            'proposal_id': event.proposal_id,
        })
    
    return JsonResponse({'events': events_list})


def property_timeline_api(request, property_id):
    """
    Endpoint API que devuelve datos completos de una propiedad para el drawer
    con información de etapas y línea de tiempo.
    """
    from .models import PropifaiProperty, Event, EventType, User
    from django.db import connections
    import json
    from datetime import date, datetime
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Obtener la propiedad principal
        prop = PropifaiProperty.objects.get(id=property_id)
    except PropifaiProperty.DoesNotExist:
        return JsonResponse({'error': 'Propiedad no encontrada'}, status=404)
    
    # Obtener información básica de la propiedad
    property_data = {
        'id': prop.id,
        'code': prop.code,
        'title': prop.title,
        'exact_address': prop.exact_address,
        'real_address': prop.real_address or prop.exact_address,
        'description': prop.description,
        'price': float(prop.price) if prop.price else None,
        'built_area': float(prop.built_area) if prop.built_area else None,
        'land_area': float(prop.land_area) if prop.land_area else None,
        'bedrooms': prop.bedrooms,
        'bathrooms': prop.bathrooms,
        'availability_status': prop.availability_status,
        'is_draft': prop.is_draft,
        'is_active': prop.is_active,
        'created_at': prop.created_at.isoformat() if prop.created_at else None,
        'updated_at': prop.updated_at.isoformat() if prop.updated_at else None,
        'district': prop.district,
        'urbanization': prop.urbanization,
        'department': prop.department,
        'province': prop.province,
    }
    
    # Obtener mapeos desde la base de datos propifai
    try:
        conn = connections['propifai']
        property_type_map = {}
        user_map = {}
        district_map = {}
        
        with conn.cursor() as cursor:
            # Mapeo property_type_id -> name
            cursor.execute("SELECT id, name FROM property_types")
            for row in cursor.fetchall():
                property_type_map[row[0]] = row[1]
            
            # Mapeo user id -> username
            cursor.execute("SELECT id, username FROM users")
            for row in cursor.fetchall():
                user_map[row[0]] = row[1]
            
            # Mapeo district id -> name
            cursor.execute("SELECT id, name FROM properties_district")
            for row in cursor.fetchall():
                district_map[str(row[0])] = row[1]
    except Exception as e:
        logger.error(f"Error al obtener mapeos de la base de datos propifai: {e}")
        # Continuar con diccionarios vacíos para no romper el flujo
        property_type_map = {}
        user_map = {}
        district_map = {}
    
    # Obtener información adicional desde properties table
    prop_extras_data = {}
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT property_type_id, created_by_id, responsible_id,
                       wp_post_id, wp_last_sync
                FROM properties
                WHERE id = %s
            """, [property_id])
            row = cursor.fetchone()
            if row:
                prop_extras_data = {
                    'property_type_id': row[0],
                    'created_by_id': row[1],
                    'responsible_id': row[2],
                    'wp_post_id': row[3],
                    'wp_last_sync': row[4],
                }
    except Exception as e:
        logger.error(f"Error al obtener información adicional de properties: {e}")
        prop_extras_data = {}
    
    # Determinar tipo de propiedad
    tipo_propiedad_valor = '—'
    if prop_extras_data and prop_extras_data['property_type_id']:
        pt_id = prop_extras_data['property_type_id']
        if pt_id in property_type_map:
            tipo_propiedad_valor = property_type_map[pt_id]
    property_data['property_type'] = tipo_propiedad_valor
    
    # Determinar agente y usuario
    agent_name = '—'
    user_name = '—'
    if prop_extras_data:
        cb_id = prop_extras_data['created_by_id']
        if cb_id and cb_id in user_map:
            user_name = user_map[cb_id]
        resp_id = prop_extras_data.get('responsible_id')
        if resp_id and resp_id in user_map:
            agent_name = user_map[resp_id]
    property_data['agent_name'] = agent_name
    property_data['user_name'] = user_name
    
    # Determinar nombre del distrito
    district_id = prop.district
    district_name = district_map.get(str(district_id), district_id) if district_id else '—'
    property_data['district_name'] = district_name
    
    # Obtener información financiera
    commission = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT initial_commission_percentage
                FROM property_financial_info
                WHERE property_id = %s
            """, [property_id])
            row = cursor.fetchone()
            if row:
                commission = row[0]
    except Exception as e:
        logger.error(f"Error al obtener información financiera: {e}")
        commission = None
    property_data['commission_percentage'] = commission
    
    # Función para obtener fecha en zona horaria de Perú (UTC-5) como string ISO con offset
    def to_peru_date(dt):
        if not dt:
            return None
        # Si dt es naive, asumir UTC
        from datetime import timezone, timedelta
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Convertir a Perú (UTC-5)
        peru_tz = timezone(timedelta(hours=-5))
        peru_dt = dt.astimezone(peru_tz)
        # Devolver string ISO con offset de Perú, pero con hora a mediodía para evitar problemas de medianoche
        # Usar mediodía (12:00) para que la fecha sea clara en cualquier zona horaria
        peru_dt_noon = peru_dt.replace(hour=12, minute=0, second=0, microsecond=0)
        return peru_dt_noon.isoformat()
    
    # Obtener eventos de la propiedad
    events = Event.objects.filter(property_id=property_id).select_related(
        'event_type', 'assigned_agent'
    ).order_by('fecha_evento', 'hora_inicio')
    
    events_list = []
    for event in events:
        events_list.append({
            'id': event.id,
            'code': event.code,
            'titulo': event.titulo,
            'fecha_evento': event.fecha_evento.isoformat() if event.fecha_evento else None,
            'hora_inicio': event.hora_inicio.isoformat() if event.hora_inicio else None,
            'hora_fin': event.hora_fin.isoformat() if event.hora_fin else None,
            'detalle': event.detalle,
            'event_type_nombre': event.event_type.name if event.event_type else None,
            'event_type_color': event.event_type.color if event.event_type else None,
            'assigned_agent_nombre': event.assigned_agent.nombre_completo if event.assigned_agent else None,
            'status': event.status,
            'seguimiento': event.seguimiento,
            'rejection_reason': event.rejection_reason,
            'lead_id': event.lead_id,
            'proposal_id': event.proposal_id,
        })
    
    # Calcular métricas de tiempo
    hoy = date.today()
    dias_activa = 0
    if prop.created_at:
        dias_activa = (hoy - prop.created_at.date()).days
    
    # Calcular precio por m² (el precio ya está en dólares)
    precio_m2 = None
    if prop.price and prop.built_area and prop.built_area > 0:
        # Calcular precio por m² y redondear a entero
        precio_m2 = round(float(prop.price) / float(prop.built_area))
    
    # Determinar etapa actual basada en eventos y status
    # Etapas: 1. Captación, 2. Publicación, 3. Visitas, 4. Propuesta, 5. Cierre
    etapa_actual = 'Captación y registro'
    etapa_numero = 1
    
    # Lógica simplificada para determinar etapa
    if prop.availability_status == 'sold':
        etapa_actual = 'Cierre y venta'
        etapa_numero = 5
    elif any(event['proposal_id'] for event in events_list if event['proposal_id']):
        etapa_actual = 'Propuesta y negociación'
        etapa_numero = 4
    elif any(event['event_type_nombre'] and 'visita' in event['event_type_nombre'].lower() for event in events_list):
        etapa_actual = 'Visitas al inmueble'
        etapa_numero = 3
    elif prop_extras_data and prop_extras_data.get('wp_post_id'):
        etapa_actual = 'Publicación web'
        etapa_numero = 2
    
    # Construir línea de tiempo de etapas
    # Usar fecha en zona horaria de Perú para evitar offset
    fecha_registro = to_peru_date(prop.created_at) if prop.created_at else None
    
    # Determinar fecha de publicación (usar wp_last_sync si está disponible)
    fecha_publicacion = fecha_registro  # Por defecto usar fecha de registro
    if prop_extras_data and prop_extras_data.get('wp_last_sync'):
        wp_last_sync = prop_extras_data['wp_last_sync']
        if hasattr(wp_last_sync, 'date'):
            # wp_last_sync puede ser datetime con timezone o naive
            fecha_publicacion = to_peru_date(wp_last_sync)
        elif isinstance(wp_last_sync, str):
            # Si es string, intentar parsear y extraer fecha
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(wp_last_sync.replace('Z', '+00:00'))
                # Asumir UTC si no tiene zona horaria
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                fecha_publicacion = to_peru_date(dt)
            except:
                pass
    
    etapas = [
        {
            'id': 1,
            'nombre': 'Captación y registro',
            'descripcion': 'Registro inicial de la propiedad en el sistema',
            'estado': 'completada',  # Siempre completada si la propiedad existe
            'fecha_inicio': fecha_registro,
            'duracion_dias': 1,  # Valor por defecto
            'datos': {
                'agente_responsable': agent_name,
                'completitud_ficha': '8/10 campos',  # Valor estimado
                'precio_inicial': float(prop.price) if prop.price else None,
                'tipo_contrato': 'simple'
            }
        },
        {
            'id': 2,
            'nombre': 'Publicación web',
            'descripcion': 'Publicación en portales inmobiliarios',
            'estado': 'completada' if etapa_numero >= 2 else 'pendiente',
            'fecha_inicio': fecha_publicacion if etapa_numero >= 2 else None,
            'duracion_dias': 3,
            'datos': {
                'portales': ['Propify', 'Adondevivir', 'Urbania'],
                'num_fotos': 5,  # Valor estimado
                'vistas_web': 150,  # Valor estimado
                'precio_publicado': float(prop.price) if prop.price else None
            }
        },
        {
            'id': 3,
            'nombre': 'Visitas al inmueble',
            'descripcion': 'Visitas programadas con clientes potenciales',
            'estado': 'activa' if etapa_numero == 3 else ('completada' if etapa_numero > 3 else 'pendiente'),
            'fecha_inicio': next((e['fecha_evento'] for e in events_list if 'visita' in e.get('event_type_nombre', '').lower()), None),
            'duracion_dias': 7,
            'datos': {
                'total_visitas': len([e for e in events_list if 'visita' in e.get('event_type_nombre', '').lower()]),
                'primera_visita': next((e['fecha_evento'] for e in events_list if 'visita' in e.get('event_type_nombre', '').lower()), None),
                'resultados_visitas': [{'fecha': e['fecha_evento'], 'resultado': 'Interesado' if e.get('lead_id') else 'No interesado'} for e in events_list if 'visita' in e.get('event_type_nombre', '').lower()][:3],
                'ajuste_precio': None  # Podría calcularse si hay eventos de ajuste
            }
        },
        {
            'id': 4,
            'nombre': 'Propuesta y negociación',
            'descripcion': 'Negociación de ofertas y términos de venta',
            'estado': 'activa' if etapa_numero == 4 else ('completada' if etapa_numero > 4 else 'pendiente'),
            'fecha_inicio': next((e['fecha_evento'] for e in events_list if e.get('proposal_id')), None),
            'duracion_dias': 5,
            'datos': {
                'comprador_interesado': 'Cliente potencial',
                'oferta_inicial': None,
                'contraoferta': None,
                'modalidad_pago': 'Por definir'
            }
        },
        {
            'id': 5,
            'nombre': 'Cierre y venta',
            'descripcion': 'Firma de documentos y liquidación de comisión',
            'estado': 'completada' if prop.availability_status == 'sold' else ('activa' if etapa_numero == 5 else 'pendiente'),
            'fecha_inicio': to_peru_date(prop.updated_at) if prop.availability_status == 'sold' else None,
            'duracion_dias': 14,
            'datos': {
                'precio_final': float(prop.price) if prop.price and prop.availability_status == 'sold' else None,
                'fecha_firma': to_peru_date(prop.updated_at) if prop.availability_status == 'sold' else None,
                'comision_liquidada': commission,
                'agente_cerro': agent_name
            }
        }
    ]
    
    # Calcular conectores entre etapas (días transcurridos)
    conectores = []
    benchmarks = {
        '1-2': 3,   # Captación → Publicación
        '2-3': 7,   # Publicación → 1ª visita
        '3-4': 5,   # Visita → Propuesta
        '4-5': 14   # Propuesta → Cierre
    }
    
    # Función para convertir fecha ISO a date (sin hora)
    def iso_to_date(iso_str):
        if not iso_str:
            return None
        try:
            # Si la cadena contiene 'T' (datetime), tomar solo la parte de fecha
            if 'T' in iso_str:
                iso_str = iso_str.split('T')[0]
            # Convertir a date
            return date.fromisoformat(iso_str)
        except:
            return None
    
    for i in range(len(etapas) - 1):
        etapa_actual_obj = etapas[i]
        etapa_siguiente_obj = etapas[i + 1]
        
        key = f"{etapa_actual_obj['id']}-{etapa_siguiente_obj['id']}"
        benchmark = benchmarks.get(key, 0)
        
        dias_transcurridos = 0
        fecha1 = iso_to_date(etapa_actual_obj['fecha_inicio'])
        fecha2 = iso_to_date(etapa_siguiente_obj['fecha_inicio'])
        
        if fecha1 and fecha2:
            dias_transcurridos = (fecha2 - fecha1).days
            # Asegurar que no sea negativo (si las fechas están invertidas)
            if dias_transcurridos < 0:
                dias_transcurridos = 0
        
        dentro_benchmark = dias_transcurridos <= benchmark if dias_transcurridos > 0 else True
        
        conectores.append({
            'desde': etapa_actual_obj['id'],
            'hacia': etapa_siguiente_obj['id'],
            'dias_transcurridos': dias_transcurridos,
            'benchmark': benchmark,
            'dentro_benchmark': dentro_benchmark,
            'texto': f"{etapa_actual_obj['nombre'].split()[0]} → {etapa_siguiente_obj['nombre'].split()[0]}"
        })
    
    # Respuesta final
    response_data = {
        'property': property_data,
        'events': events_list,
        'timeline': {
            'etapas': etapas,
            'conectores': conectores,
            'etapa_actual': etapa_actual,
            'etapa_numero': etapa_numero
        },
        'metrics': {
            'dias_activa': dias_activa,
            'precio_m2': precio_m2,
            'total_eventos': len(events_list),
            'total_visitas': len([e for e in events_list if 'visita' in e.get('event_type_nombre', '').lower()]),
            'tiene_lead': any(e.get('lead_id') for e in events_list),
            'tiene_propuesta': any(e.get('proposal_id') for e in events_list)
        }
    }
    
    return JsonResponse(response_data)
