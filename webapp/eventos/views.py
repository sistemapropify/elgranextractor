import json
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, date, timedelta
from collections import defaultdict
from .models import Event, EventType
from propifai.models import PropifaiProperty, User


def calcular_evolucion_semanal(eventos_queryset):
    """
    Calcula la evolución semanal de eventos por tipo (agrupado por semanas).
    Retorna un diccionario con:
    - labels: lista de semanas (últimas 8 semanas)
    - datasets: lista de datasets por tipo de evento
    - tipos_evento: información de cada tipo (id, nombre, color)
    """
    hoy = date.today()
    # Número de semanas a mostrar
    num_semanas = 8
    
    # Generar lista de las últimas N semanas (semana del año, año)
    semanas = []
    for i in range(num_semanas - 1, -1, -1):
        # Fecha de referencia dentro de la semana (usamos lunes)
        fecha_ref = hoy - timedelta(days=hoy.weekday() + 7 * i)
        año, semana, _ = fecha_ref.isocalendar()
        semanas.append((año, semana, fecha_ref))
    
    # Obtener todos los tipos de eventos activos
    tipos_evento = EventType.objects.filter(is_active=True).order_by('name')
    
    # Crear estructura para almacenar conteos por tipo y semana
    conteos = defaultdict(lambda: defaultdict(int))
    
    # Filtrar eventos de las últimas N*7 días (para cubrir todas las semanas)
    fecha_inicio = hoy - timedelta(days=7 * num_semanas)
    eventos_recientes = eventos_queryset.filter(
        fecha_evento__gte=fecha_inicio,
        fecha_evento__lte=hoy
    )
    
    # Contar eventos por tipo y semana
    for evento in eventos_recientes:
        # Obtener semana ISO
        año_sem, semana_sem, _ = evento.fecha_evento.isocalendar()
        clave_semana = f"{año_sem}-W{semana_sem:02d}"
        tipo_id = evento.event_type_id
        conteos[tipo_id][clave_semana] += 1
    
    # Preparar datasets para Chart.js
    datasets = []
    tipos_info = []
    
    # Mapeo de clave_semana a índice en la lista de semanas
    semana_keys = [f"{año}-W{semana:02d}" for año, semana, _ in semanas]
    
    for tipo in tipos_evento:
        tipo_id = tipo.id
        datos = [conteos[tipo_id][clave] for clave in semana_keys]
        
        # Solo incluir tipos que tengan al menos un evento en el período
        if sum(datos) > 0:
            datasets.append({
                'label': tipo.name,
                'data': datos,
                'borderColor': tipo.color if tipo.color else '#007bff',
                'backgroundColor': tipo.color + '20' if tipo.color else '#007bff20',
                'borderWidth': 2,
                'fill': False,
                'tension': 0.4,
            })
            
            tipos_info.append({
                'id': tipo.id,
                'name': tipo.name,
                'color': tipo.color if tipo.color else '#007bff',
                'total_semana': sum(datos),
            })
    
    # Generar etiquetas legibles para las semanas
    labels = []
    for año, semana, fecha_ref in semanas:
        # Calcular lunes de esa semana
        lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
        domingo = lunes + timedelta(days=6)
        labels.append(f"Sem {semana} ({lunes.day}/{lunes.month}-{domingo.day}/{domingo.month})")
    
    return {
        'labels': labels,
        'datasets': datasets,
        'tipos_evento': tipos_info,
        'semanas_iso': semana_keys,
    }


def dashboard_eventos(request):
    """
    Vista principal del dashboard de eventos con paginación y filtros.
    """
    # Obtener todos los eventos ordenados por fecha descendente
    eventos_list = Event.objects.all().order_by('-fecha_evento', '-hora_inicio')
    
    # Inicializar filtros
    filtros = {}
    
    # Filtro por día (fecha específica)
    dia = request.GET.get('dia')
    if dia:
        try:
            fecha_filtro = datetime.strptime(dia, '%Y-%m-%d').date()
            eventos_list = eventos_list.filter(fecha_evento=fecha_filtro)
            filtros['dia'] = dia
        except ValueError:
            pass
    
    # Filtro por propiedad (property_id)
    propiedad_id = request.GET.get('propiedad')
    if propiedad_id and propiedad_id.isdigit():
        eventos_list = eventos_list.filter(property_id=int(propiedad_id))
        filtros['propiedad'] = propiedad_id
    
    # Filtro por tipo de evento (event_type_id)
    tipo_id = request.GET.get('tipo')
    if tipo_id and tipo_id.isdigit():
        eventos_list = eventos_list.filter(event_type_id=int(tipo_id))
        filtros['tipo'] = tipo_id
    
    # Filtro por agente (assigned_agent_id)
    agente_id = request.GET.get('agente')
    if agente_id and agente_id.isdigit():
        eventos_list = eventos_list.filter(assigned_agent_id=int(agente_id))
        filtros['agente'] = agente_id
    
    # Paginación
    paginator = Paginator(eventos_list, 25)  # 25 eventos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener información de propiedades para los eventos de esta página
    eventos_con_propiedad = []
    propiedades_dict = {}
    usuarios_dict = {}
    
    # Recopilar todos los property_id únicos de los eventos en esta página
    property_ids = [evento.property_id for evento in page_obj.object_list if evento.property_id]
    
    if property_ids:
        # Obtener propiedades en una sola consulta
        propiedades = PropifaiProperty.objects.filter(id__in=property_ids)
        propiedades_dict = {prop.id: prop for prop in propiedades}
    
    # Recopilar todos los assigned_agent_id únicos de los eventos en esta página
    agent_ids = [evento.assigned_agent_id for evento in page_obj.object_list if evento.assigned_agent_id]
    
    if agent_ids:
        # Obtener usuarios en una sola consulta
        usuarios = User.objects.filter(id__in=agent_ids)
        usuarios_dict = {user.id: f"{user.first_name} {user.last_name}".strip() for user in usuarios}
    
    # Preparar datos para el template
    for evento in page_obj.object_list:
        propiedad_info = None
        if evento.property_id and evento.property_id in propiedades_dict:
            prop = propiedades_dict[evento.property_id]
            propiedad_info = {
                'id': prop.id,
                'title': prop.title,
                'coordinates': prop.coordinates,
                'latitude': prop.latitude,
                'longitude': prop.longitude,
                'has_coordinates': prop.latitude is not None and prop.longitude is not None,
            }
        
        # Obtener nombre del agente si existe
        agente_nombre = None
        if evento.assigned_agent_id and evento.assigned_agent_id in usuarios_dict:
            agente_nombre = usuarios_dict[evento.assigned_agent_id]
        
        eventos_con_propiedad.append({
            'evento': evento,
            'propiedad_info': propiedad_info,
            'agente_nombre': agente_nombre,
        })
    
    # Obtener tipos de eventos para el dropdown de filtro
    tipos_evento = EventType.objects.filter(is_active=True).order_by('name')
    
    # Estadísticas básicas
    total_eventos = eventos_list.count()
    eventos_hoy = eventos_list.filter(fecha_evento=date.today()).count()
    eventos_semana = eventos_list.filter(
        fecha_evento__gte=date.today() - timedelta(days=7)
    ).count()
    
    # Calcular evolución semanal por tipo de evento
    evolucion_semanal = calcular_evolucion_semanal(eventos_list)
    evolucion_semanal_json = json.dumps(evolucion_semanal)

    context = {
        'page_obj': page_obj,
        'eventos_con_propiedad': eventos_con_propiedad,
        'tipos_evento': tipos_evento,
        'filtros': filtros,
        'total_eventos': total_eventos,
        'eventos_hoy': eventos_hoy,
        'eventos_semana': eventos_semana,
        'hoy': date.today().isoformat(),
        'evolucion_semanal': evolucion_semanal,
        'evolucion_semanal_json': evolucion_semanal_json,
    }
    
    return render(request, 'eventos/dashboard.html', context)


def detalle_evento(request, evento_id):
    """
    Vista para mostrar el detalle de un evento específico.
    """
    try:
        evento = Event.objects.get(id=evento_id)
    except Event.DoesNotExist:
        evento = None
    
    context = {
        'evento': evento,
    }
    return render(request, 'eventos/detalle.html', context)


def api_eventos(request):
    """
    API simple para obtener eventos en formato JSON (para AJAX).
    """
    from django.http import JsonResponse
    import json
    
    eventos = Event.objects.all().order_by('-fecha_evento')[:100]
    
    data = []
    for e in eventos:
        data.append({
            'id': e.id,
            'code': e.code,
            'titulo': e.titulo,
            'fecha_evento': e.fecha_evento.isoformat() if e.fecha_evento else None,
            'hora_inicio': str(e.hora_inicio) if e.hora_inicio else None,
            'hora_fin': str(e.hora_fin) if e.hora_fin else None,
            'interesado': e.interesado,
            'property_id': e.property_id,
            'event_type_id': e.event_type_id,
            'assigned_agent_id': e.assigned_agent_id,
            'status': e.status,
        })
    
    return JsonResponse({'eventos': data})
