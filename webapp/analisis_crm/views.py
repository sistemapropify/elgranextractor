import json
import logging
from django.shortcuts import render
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Lead, LeadAssignment, User, LeadStatus

logger = logging.getLogger(__name__)


def agenda_analysis(request):
    """Análisis de agenda sobre dbo.event (solo lectura)."""
    from eventos.models import Event, EventType
    from datetime import date
    import calendar
    today = timezone.localdate()
    granularity = request.GET.get('granularity', 'day')
    if granularity not in {'day', 'week', 'month', 'year'}:
        granularity = 'day'
    try:
        date_from = datetime.strptime(request.GET.get('from', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_from = today - timedelta(days=30)
    try:
        date_to = datetime.strptime(request.GET.get('to', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    qs = Event.objects.filter(start_time__date__range=(date_from, date_to), is_active=True)
    agent_id = request.GET.get('agent', '').strip()
    type_id = request.GET.get('event_type', '').strip()
    status = request.GET.get('status', '').strip()
    if agent_id.isdigit(): qs = qs.filter(assigned_agent_id=int(agent_id))
    if type_id.isdigit(): qs = qs.filter(event_type_id=int(type_id))
    if status: qs = qs.filter(status=status)
    events = list(qs.order_by('start_time'))
    type_map = {x.id: x.name for x in EventType.objects.filter(is_active=True)}
    agent_ids = {e.assigned_agent_id for e in events if e.assigned_agent_id}
    # dbpropify_be usa dbo.[user] (singular); el modelo Django histórico apunta
    # a "users", por lo que aquí resolvemos los nombres sin activar ese mapeo.
    users = {}
    if agent_ids:
        from django.db import connections
        with connections['propifai'].cursor() as cursor:
            # Cargar el catálogo completo evita incompatibilidades del driver
            # MSSQL con listas parametrizadas en cláusulas IN.
            cursor.execute('SELECT id, username, first_name, last_name FROM dbo.[user]')
            users = {row[0]: (' '.join(x for x in (row[2], row[3]) if x).strip() or row[1] or f'Agente {row[0]}') for row in cursor.fetchall()}
    def bucket(dt):
        d = timezone.localtime(dt).date()
        if granularity == 'year': return d.strftime('%Y')
        if granularity == 'month': return d.strftime('%Y-%m')
        if granularity == 'week':
            iso = d.isocalendar(); return f'{iso.year}-W{iso.week:02d}'
        return d.isoformat()
    periods, by_agent, by_type, matrix = {}, {}, {}, {}
    series = {g: {'labels': [], 'types': {}} for g in ('day', 'week', 'month', 'year')}
    completed = pending = overdue = cancelled = 0
    now = timezone.now()
    for e in events:
        p = bucket(e.start_time); periods[p] = periods.get(p, 0) + 1
        series[granularity]['types'].setdefault(type_map.get(e.event_type_id, 'Sin tipo'), {})[p] = series[granularity]['types'].setdefault(type_map.get(e.event_type_id, 'Sin tipo'), {}).get(p, 0) + 1
        a = users.get(e.assigned_agent_id, 'Sin asignar'); by_agent.setdefault(a, [0, 0, 0]); by_agent[a][0] += 1
        t = type_map.get(e.event_type_id, 'Sin tipo'); by_type.setdefault(t, [0, 0, 0]); by_type[t][0] += 1
        matrix.setdefault(a, {}); matrix[a][t] = matrix[a].get(t, 0) + 1
        state = (e.status or '').lower()
        if e.completed or state in {'completed', 'complete', 'done', 'completado'}:
            completed += 1; by_agent[a][1] += 1; by_type[t][1] += 1
        elif 'cancel' in state: cancelled += 1
        else:
            pending += 1; by_agent[a][2] += 1; by_type[t][2] += 1
            if e.start_time and e.start_time < now: overdue += 1
    period_keys = sorted(periods)
    display_labels = period_keys
    if granularity == 'day':
        display_labels = [datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m') for value in period_keys]
    series_payload = {
        'labels': display_labels,
        'types': {t: [vals.get(p, 0) for p in period_keys] for t, vals in series[granularity]['types'].items()},
    }
    agent_rows = sorted(({'name': k, 'total': v[0], 'comp': v[1], 'pend': v[2], 'rate': round(v[1] * 100 / v[0]) if v[0] else 0, 'unassigned': k == 'Sin asignar'} for k, v in by_agent.items()), key=lambda x: -x['total'])
    type_rows = sorted(({'name': k, 'total': v[0], 'comp': v[1], 'pend': v[2]} for k, v in by_type.items()), key=lambda x: -x['total'])
    agent_choices = sorted(
        ({'id': agent_pk, 'name': users.get(agent_pk, f'Agente {agent_pk}')} for agent_pk in agent_ids),
        key=lambda item: item['name'].lower(),
    )
    agenda_payload = []
    for e in reversed(events[-100:]):
        state = (e.status or '').lower()
        normalized = 'completado' if e.completed or state in {'completed', 'complete', 'done', 'completado'} else ('cancelado' if 'cancel' in state else ('vencido' if e.start_time and e.start_time < now else 'pendiente'))
        local_start = timezone.localtime(e.start_time) if e.start_time else None
        agenda_payload.append({
            'code': e.code or f'EVT-{e.id}', 'title': e.title or 'Evento sin título',
            'type': type_map.get(e.event_type_id, 'Sin tipo'), 'agent': users.get(e.assigned_agent_id, 'Sin asignar'),
            'date': local_start.strftime('%d %b') if local_start else 'Sin fecha',
            'time': local_start.strftime('%H:%M') if local_start else None, 'status': normalized,
            'completed': bool(e.completed), 'lead': f'L-{e.lead_id}' if e.lead_id else 'Sin lead',
            'contact': f'Contacto {e.contact_id}' if e.contact_id else 'Sin contacto',
            'property': f'P-{e.property_id}' if e.property_id else None,
            'proposal': f'PR-{e.proposal_id}' if e.proposal_id else None,
            'match': f'M-{e.match_id}' if e.match_id else None,
            'creator': users.get(e.created_by_id, f'Usuario {e.created_by_id}') if e.created_by_id else None,
            'updater': users.get(e.updated_by_id, f'Usuario {e.updated_by_id}') if e.updated_by_id else None,
            'created': timezone.localtime(e.created_at).strftime('%d/%m/%Y %H:%M') if e.created_at else None,
            'updated': timezone.localtime(e.updated_at).strftime('%d/%m/%Y %H:%M') if e.updated_at else None,
            'tracing': e.tracing or None, 'desc': e.description or None,
        })
    kpis_payload = [
        {'val': len(events), 'label': 'Total de eventos', 'accent': 'var(--blue)'},
        {'val': completed, 'label': 'Eventos completados', 'accent': 'var(--green)', 'cls': 'good'},
        {'val': pending, 'label': 'Eventos pendientes', 'accent': 'var(--blue)'},
        {'val': cancelled, 'label': 'Eventos cancelados', 'accent': 'var(--red)', 'cls': 'bad'},
        {'val': overdue, 'label': 'Eventos vencidos', 'accent': 'var(--red)', 'cls': 'bad'},
        {'val': len(agent_rows), 'label': 'Agentes activos', 'accent': 'var(--blue)'},
        {'val': len(type_rows), 'label': 'Tipos de evento utilizados', 'accent': 'var(--text-2)'},
        {'val': f'{round(completed * 100 / (completed + pending + cancelled)) if completed + pending + cancelled else 0}%', 'label': 'Tasa de cumplimiento', 'accent': 'var(--green)', 'cls': 'good'},
        {'val': '—', 'label': 'Tiempo promedio hasta completar', 'accent': 'var(--amber)'},
        {'val': sum(1 for e in events if not e.assigned_agent_id), 'label': 'Eventos sin agente asignado', 'accent': 'var(--amber)', 'cls': 'warn'},
    ]
    return render(request, 'analisis_crm/agenda_analysis.html', {
        'events': events[-100:], 'periods': sorted(periods.items()), 'agent_rows': agent_rows,
        'type_rows': type_rows, 'total': len(events), 'completed': completed, 'pending': pending,
        'overdue': overdue, 'cancelled': cancelled, 'date_from': date_from, 'date_to': date_to,
        'granularity': granularity, 'event_types': EventType.objects.filter(is_active=True).order_by('name'),
        'agents': agent_choices, 'agent_filter': agent_id, 'type_filter': type_id, 'status_filter': status,
        'series_json': json.dumps(series_payload, ensure_ascii=False),
        'agents_json': json.dumps(agent_rows, ensure_ascii=False),
        'types_json': json.dumps(type_rows, ensure_ascii=False),
        'matrix_json': json.dumps(matrix, ensure_ascii=False),
        'agenda_json': json.dumps(agenda_payload, ensure_ascii=False),
        'kpis_json': json.dumps(kpis_payload, ensure_ascii=False),
    })


def dashboard(request):
    """
    Vista principal del dashboard de análisis de leads.
    """
    # Log para depuración del gráfico
    import os
    log_path = os.path.join(os.path.dirname(__file__), 'dashboard_debug.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n=== Dashboard called at {timezone.now()} ===\n")
    
    # Obtener parámetro de filtro por fecha (formato YYYY-MM-DD)
    filter_date_str = request.GET.get('filter_date', '').strip()
    filter_date = None
    if filter_date_str:
        try:
            from datetime import datetime
            filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
        except ValueError:
            filter_date = None
    
    # Obtener parámetros de ordenamiento
    sort_by = request.GET.get('sort_by', 'date_entry')
    sort_order = request.GET.get('sort_order', 'desc')
    
    # Validar parámetros de ordenamiento
    valid_sort_fields = ['id', 'full_name', 'phone', 'email', 'date_entry', 'is_active', 'lead_status_id', 'status_name', 'assigned_user']
    if sort_by not in valid_sort_fields:
        sort_by = 'date_entry'
    
    if sort_order not in ['asc', 'desc']:
        sort_order = 'desc'
    
    # Obtener parámetro de búsqueda por nombre/teléfono/email
    search = request.GET.get('search', '').strip()
    
    # Base queryset con filtros
    leads_qs = Lead.objects.all()
    
    # Aplicar filtro por fecha si existe
    if filter_date:
        leads_qs = leads_qs.filter(date_entry__date=filter_date)
    
    # Aplicar filtro de búsqueda
    if search:
        leads_qs = leads_qs.filter(
            Q(full_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Aplicar ordenamiento según parámetros (ahora en base de datos, no en Python)
    order_prefix = '-' if sort_order == 'desc' else ''
    
    # Mapear campos de ordenamiento a campos reales del modelo
    sort_field_map = {
        'id': 'id',
        'full_name': 'full_name',
        'phone': 'phone',
        'email': 'email',
        'date_entry': 'date_entry',
        'is_active': 'is_active',
        'lead_status_id': 'lead_status_id',
        'status_name': 'lead_status_id',  # Ordenar por ID de estado
        'assigned_user': 'leadassignment__user_id',  # Ordenar por ID de usuario asignado
    }
    
    sort_field = sort_field_map.get(sort_by, 'date_entry')
    
    # Construir ordenamiento
    if sort_order == 'desc':
        sort_field = '-' + sort_field
    
    # Aplicar ordenamiento
    leads_qs = leads_qs.order_by(sort_field, '-date_entry')
    
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(leads_qs, 50)  # 50 leads por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener leads de la página actual
    leads_on_page = list(page_obj.object_list)
    
    # Obtener asignaciones de leads (lead -> usuario) para los leads de esta página
    lead_ids = [lead.id for lead in leads_on_page]
    assignments = LeadAssignment.objects.filter(lead_id__in=lead_ids).select_related('user')
    
    # Crear diccionario de asignaciones por lead_id
    assignment_map = {}
    for assignment in assignments:
        assignment_map[assignment.lead_id] = assignment.user
    
    # Obtener estados de leads (lead_status_id -> nombre) para los leads de esta página
    status_ids = [lead.lead_status_id for lead in leads_on_page if lead.lead_status_id is not None]
    lead_statuses = LeadStatus.objects.filter(id__in=status_ids)
    status_map = {status.id: status.name for status in lead_statuses}
    
    # Asignar usuario y estado a cada lead (monkey-patch para uso en template)
    for lead in leads_on_page:
        lead.assigned_user = assignment_map.get(lead.id)
        lead.status_name = status_map.get(lead.lead_status_id, 'Sin estado')
    
    # Para compatibilidad con template (mantener nombres de variables similares)
    unique_leads = leads_on_page
    all_leads = leads_qs  # Queryset completo para estadísticas
    
    # Estadísticas básicas
    total_leads = Lead.objects.count()
    active_leads = Lead.objects.filter(is_active=True).count()
    leads_last_7_days = Lead.objects.filter(
        date_entry__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Leads por estado (lead_status_id) - agrupar
    status_counts_raw = Lead.objects.values('lead_status_id').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Obtener nombres de estados para los IDs encontrados
    status_ids = [item['lead_status_id'] for item in status_counts_raw if item['lead_status_id'] is not None]
    lead_statuses = LeadStatus.objects.filter(id__in=status_ids)
    status_name_map = {status.id: status.name for status in lead_statuses}
    
    # Crear lista final con nombres de estado
    status_counts = []
    for item in status_counts_raw:
        status_id = item['lead_status_id']
        status_name = status_name_map.get(status_id, 'Sin estado') if status_id is not None else 'Sin estado'
        status_counts.append({
            'lead_status_id': status_id,
            'status_name': status_name,
            'count': item['count']
        })
    
    # Leads por canal (canal_lead_id)
    canal_counts = Lead.objects.values('canal_lead_id').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Leads sin email
    leads_without_email = Lead.objects.filter(email__isnull=True).count()
    
    # Evolución de leads por día del mes actual
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Debug: información de fechas
    print(f"[DEBUG CRM] === INICIO GRÁFICO ===")
    print(f"[DEBUG CRM] now: {now} (timezone: {now.tzinfo})")
    print(f"[DEBUG CRM] first_day_of_month: {first_day_of_month}")
    print(f"[DEBUG CRM] Diferencia en días: {(now - first_day_of_month).days}")
    
    # Obtener leads agrupados por día (date_entry) - CON LEADS ÚNICOS POR TELÉFONO
    # Primero obtenemos los días con leads
    days_with_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').distinct().order_by('day')
    
    # Para cada día, contar leads únicos por teléfono
    daily_leads = []
    for day_entry in days_with_leads:
        day = day_entry['day']
        
        # Leads únicos por teléfono para este día
        unique_phones = Lead.objects.filter(
            date_entry__date=day,
            phone__isnull=False
        ).values('phone').distinct().count()
        
        # Leads sin teléfono (contar como únicos)
        no_phone_count = Lead.objects.filter(
            date_entry__date=day,
            phone__isnull=True
        ).count()
        
        total_unique = unique_phones + no_phone_count
        
        # También obtener conteo total para comparación
        total_count = Lead.objects.filter(date_entry__date=day).count()
        
        daily_leads.append({
            'day': day,
            'count': total_unique,  # Usar conteo de leads únicos
            'total_count': total_count,  # Mantener total para debug
            'duplicates': total_count - total_unique
        })
    
    print(f"[DEBUG CRM] daily_leads calculado, días: {len(daily_leads)}")
    for entry in daily_leads:
        print(f"[DEBUG CRM]   {entry['day']}: {entry['count']} únicos (de {entry['total_count']} total, {entry['duplicates']} duplicados)")
    
    # Log a archivo
    import os
    log_path = os.path.join(os.path.dirname(__file__), 'dashboard_debug.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n[DEBUG CRM] daily_leads calculado, días: {len(daily_leads)}\n")
        for entry in daily_leads:
            f.write(f"[DEBUG CRM]   {entry['day']}: {entry['count']} únicos (de {entry['total_count']} total, {entry['duplicates']} duplicados)\n")
    
    # Crear estructura para el gráfico: lista de días y conteos
    days_of_month = []
    counts_per_day = []
    
    # Generar solo los días hasta la fecha actual (no incluir días futuros)
    # Calcular último día del mes actual para referencia
    import calendar
    year = now.year
    month = now.month
    last_day_of_month = calendar.monthrange(year, month)[1]  # último día del mes
    
    # Crear datetime para el último día del mes (solo para debug)
    last_day_datetime = now.replace(day=last_day_of_month, hour=23, minute=59, second=59)
    
    print(f"[DEBUG CRM] Mes actual: {month}/{year}")
    print(f"[DEBUG CRM] Último día del mes: {last_day_of_month}")
    print(f"[DEBUG CRM] last_day_datetime: {last_day_datetime}")
    print(f"[DEBUG CRM] Generando días hasta: {now.date()}")
    
    current_day = first_day_of_month
    day_counter = 0
    # Solo generar días hasta la fecha actual (incluyendo hoy)
    while current_day.date() <= now.date():
        day_counter += 1
        # Mostrar solo el día del mes (sin cero a la izquierda para que sea 1, 2, 3... no 01, 02, 03)
        days_of_month.append(str(current_day.day))
        # Buscar conteo para este día (leads únicos)
        count = 0
        total_for_day = 0
        duplicates_for_day = 0
        current_date = current_day.date()  # Convertir datetime a date
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']  # Leads únicos
                total_for_day = entry['total_count']  # Total (con duplicados)
                duplicates_for_day = entry['duplicates']  # Duplicados
                break
        counts_per_day.append(count)
        
        # Debug adicional para días con duplicados
        if duplicates_for_day > 0:
            print(f"[DEBUG CRM] Día {current_date}: {count} únicos (de {total_for_day} total, {duplicates_for_day} duplicados)")
        current_day += timedelta(days=1)
    
    print(f"[DEBUG CRM] días generados: {day_counter}")
    print(f"[DEBUG CRM] días del mes: {len(days_of_month)}")
    print(f"[DEBUG CRM] días list: {days_of_month}")
    print(f"[DEBUG CRM] conteos: {counts_per_day}")
    
    # Verificar si las listas están vacías
    if not days_of_month:
        print("[DEBUG CRM] ERROR: days_of_month está vacío - el bucle while no se ejecutó")
        print(f"[DEBUG CRM] current_day inicial: {first_day_of_month}, now: {now}")
        # Forzar datos de ejemplo para debugging
        days_of_month = ['1', '2', '3']
        counts_per_day = [5, 10, 15]
    
    # Convertir a JSON para uso en JavaScript
    days_of_month_json = json.dumps(days_of_month)
    counts_per_day_json = json.dumps(counts_per_day)
    print(f"[DEBUG CRM] days_of_month_json: {days_of_month_json}")
    print(f"[DEBUG CRM] counts_per_day_json: {counts_per_day_json}")
    
    # Debug adicional: verificar tipos y longitudes
    print(f"[DEBUG CRM] Tipo days_of_month: {type(days_of_month)}, longitud: {len(days_of_month)}")
    print(f"[DEBUG CRM] Tipo counts_per_day: {type(counts_per_day)}, longitud: {len(counts_per_day)}")
    print(f"[DEBUG CRM] Tipo days_of_month_json: {type(days_of_month_json)}, valor: '{days_of_month_json}'")
    print(f"[DEBUG CRM] Tipo counts_per_day_json: {type(counts_per_day_json)}, valor: '{counts_per_day_json}'")
    
    # Crear strings de JavaScript directamente (para usar en template sin json_script)
    days_js = json.dumps(days_of_month)  # Ya es un string JSON
    counts_js = json.dumps(counts_per_day)
    
    # Obtener asignaciones de leads (lead -> usuario)
    lead_ids = [lead.id for lead in unique_leads]
    assignments = LeadAssignment.objects.filter(lead_id__in=lead_ids).select_related('user')
    
    # Crear diccionario de asignaciones por lead_id
    assignment_map = {}
    for assignment in assignments:
        assignment_map[assignment.lead_id] = assignment.user
    
    # Obtener estados de leads (lead_status_id -> nombre)
    status_ids = [lead.lead_status_id for lead in unique_leads if lead.lead_status_id is not None]
    lead_statuses = LeadStatus.objects.filter(id__in=status_ids)
    status_map = {status.id: status.name for status in lead_statuses}
    
    # Asignar usuario a cada lead (monkey-patch para uso en template)
    for lead in unique_leads:
        lead.assigned_user = assignment_map.get(lead.id)
        lead.status_name = status_map.get(lead.lead_status_id, 'Sin estado')
    
    # Calcular estadísticas de duplicación
    duplicate_stats = {
        'total_in_list': all_leads.count(),
        'unique_in_list': len(unique_leads),
        'duplicate_count': all_leads.count() - len(unique_leads),
        'duplicate_percentage': ((all_leads.count() - len(unique_leads)) / all_leads.count() * 100) if all_leads.count() > 0 else 0,
    }
    
    # Datos combinados para iterar en template
    daily_data = zip(days_of_month, counts_per_day)
    
    context = {
        'leads': unique_leads,  # Usar leads únicos (lista)
        'all_leads': all_leads,  # Mantener referencia a lista original para debugging
        'total_leads': total_leads,
        'active_leads': active_leads,
        'leads_last_7_days': leads_last_7_days,
        'status_counts': status_counts,
        'canal_counts': canal_counts,
        'leads_without_email': leads_without_email,
        'days_of_month': days_of_month,
        'counts_per_day': counts_per_day,
        'daily_data': daily_data,  # Para iterar fácilmente en template
        'days_of_month_json': days_of_month_json,
        'counts_per_day_json': counts_per_day_json,
        'days_js': days_js,  # Para usar directamente en JavaScript
        'counts_js': counts_js,
        'duplicate_stats': duplicate_stats,  # Estadísticas de duplicación
        'assignment_map': assignment_map,  # Mapeo de lead_id -> usuario asignado
        'filter_date': filter_date,
        'filter_date_str': filter_date_str,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'title': 'Dashboard de Leads CRM',
    }
    
    # Debug: imprimir claves del contexto
    print(f"[DEBUG CRM] Claves del contexto: {list(context.keys())}")
    
    return render(request, 'analisis_crm/dashboard.html', context)


def lead_list(request):
    """
    Lista paginada de todos los leads con filtros.
    """
    from django.core.paginator import Paginator
    
    # Obtener parámetros de filtro
    search = request.GET.get('search', '').strip()
    is_active = request.GET.get('is_active', '')
    order_by = request.GET.get('order_by', '-date_entry')
    
    # Construir queryset base
    lead_list = Lead.objects.all()
    
    # Aplicar filtros
    if search:
        lead_list = lead_list.filter(
            models.Q(full_name__icontains=search) |
            models.Q(phone__icontains=search) |
            models.Q(email__icontains=search)
        )
    
    if is_active == '1':
        lead_list = lead_list.filter(is_active=True)
    elif is_active == '0':
        lead_list = lead_list.filter(is_active=False)
    
    # Validar y aplicar ordenación
    valid_order_fields = ['date_entry', '-date_entry', 'created_at', '-created_at', 'full_name', '-full_name']
    if order_by not in valid_order_fields:
        order_by = '-date_entry'
    
    lead_list = lead_list.order_by(order_by)
    
    # Paginación
    paginator = Paginator(lead_list, 50)  # 50 leads por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'Lista de Leads',
    }
    return render(request, 'analisis_crm/lead_list.html', context)


def lead_detail(request, pk):
    """
    Detalle de un lead específico.
    """
    try:
        lead = Lead.objects.get(pk=pk)
    except Lead.DoesNotExist:
        from django.http import Http404
        raise Http404("Lead no encontrado")
    
    context = {
        'lead': lead,
        'title': f'Lead: {lead.full_name or lead.phone}',
    }
    return render(request, 'analisis_crm/lead_detail.html', context)


def analytics(request):
    """
    Vista de análisis más detallado con gráficos (podría usar Chart.js).
    """
    # Conteo por mes basado en date_entry
    from django.db.models.functions import TruncMonth
    monthly_counts = Lead.objects.annotate(
        month=TruncMonth('date_entry')
    ).values('month').annotate(count=Count('id')).order_by('month')
    
    # Top 10 usuarios que crearon leads
    top_creators = Lead.objects.values('created_by_id').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    context = {
        'monthly_counts': list(monthly_counts),
        'top_creators': list(top_creators),
        'title': 'Análisis Detallado',
    }
    return render(request, 'analisis_crm/analytics.html', context)
