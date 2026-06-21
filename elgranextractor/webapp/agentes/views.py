from collections import defaultdict
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib import messages
from django.db.models import Count, Q
from .models import Agente, Inmobiliaria
from .forms import AgenteForm, InmobiliariaForm
from matching.models import PropuestaWhatsApp


# ===================================================================
# Vistas para Agente
# ===================================================================

class AgenteListView(ListView):
    """Listado de agentes con filtros."""
    model = Agente
    template_name = 'agentes/lista_agentes.html'
    context_object_name = 'agentes'
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().select_related('inmobiliaria')

        # Filtros
        tipo = self.request.GET.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo_agente=tipo)

        inmobiliaria_id = self.request.GET.get('inmobiliaria')
        if inmobiliaria_id:
            queryset = queryset.filter(inmobiliaria_id=inmobiliaria_id)

        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(nombre_completo__icontains=busqueda)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Agentes'
        context['tipos_agente'] = Agente.TipoAgente.choices
        context['inmobiliarias'] = Inmobiliaria.objects.all().order_by('nombre')
        context['tipo_seleccionado'] = self.request.GET.get('tipo', '')
        context['inmobiliaria_seleccionada'] = self.request.GET.get('inmobiliaria', '')
        context['busqueda'] = self.request.GET.get('q', '')

        # Stats para el dashboard
        context['total_agentes'] = Agente.objects.count()
        context['independientes_count'] = Agente.objects.filter(tipo_agente='INDEPENDIENTE').count()
        context['inmobiliarias_count'] = Agente.objects.filter(tipo_agente='INMOBILIARIA').count()
        context['total_inmobiliarias_reg'] = Inmobiliaria.objects.count()
        return context


class AgenteCreateView(CreateView):
    """Crear un nuevo agente."""
    model = Agente
    form_class = AgenteForm
    template_name = 'agentes/formulario_agente.html'
    success_url = reverse_lazy('agentes:lista_agentes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nuevo Agente'
        context['accion'] = 'Crear'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Agente creado correctamente.')
        return super().form_valid(form)


class AgenteUpdateView(UpdateView):
    """Editar un agente existente."""
    model = Agente
    form_class = AgenteForm
    template_name = 'agentes/formulario_agente.html'
    success_url = reverse_lazy('agentes:lista_agentes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Agente'
        context['accion'] = 'Guardar cambios'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Agente actualizado correctamente.')
        return super().form_valid(form)


class AgenteDeleteView(DeleteView):
    """Eliminar un agente."""
    model = Agente
    template_name = 'agentes/confirmar_eliminar.html'
    success_url = reverse_lazy('agentes:lista_agentes')
    context_object_name = 'objeto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Eliminar Agente'
        context['tipo_objeto'] = 'agente'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Agente eliminado correctamente.')
        return super().form_valid(form)


# ===================================================================
# Vista de Pipeline de Propuestas WhatsApp
# ===================================================================

class AgentePropuestasView(DetailView):
    """Pipeline de propuestas WhatsApp enviadas a un agente."""
    model = Agente
    template_name = 'agentes/pipeline_propuestas.html'
    context_object_name = 'agente'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agente = self.object

        propuestas = PropuestaWhatsApp.objects.filter(
            Q(agente_nombre__icontains=agente.nombre_completo) |
            Q(agente_telefono=agente.telefono)
        ).select_related('requerimiento').order_by('-enviado_en')

        # ── Agrupar propuestas por requerimiento ──
        propuestas_por_req = defaultdict(list)
        for p in propuestas:
            propuestas_por_req[p.requerimiento_id].append(p)

        # Ordenar requerimientos por la propuesta más reciente
        req_ids_ordenados = sorted(
            propuestas_por_req.keys(),
            key=lambda rid: max(p.enviado_en for p in propuestas_por_req[rid] if p.enviado_en) if any(p.enviado_en for p in propuestas_por_req[rid]) else rid,
            reverse=True
        )

        # Información resumida de cada requerimiento para el template
        # Y crear lista ordenada de tuplas (requerimiento_info, [propuestas])
        requerimiento_list = []
        for rid in req_ids_ordenados:
            req = propuestas_por_req[rid][0].requerimiento
            req_info = {
                'id': rid,
                'texto': req.requerimiento[:200] if req.requerimiento else '',
                'agente': (req.agente or '').replace('\n', ' ').strip(),
                'tipo_propiedad': req.get_tipo_propiedad_display() if req.tipo_propiedad else '—',
                'presupuesto_monto': float(req.presupuesto_monto) if req.presupuesto_monto else None,
                'presupuesto_moneda': req.presupuesto_moneda or '',
                'fecha': req.fecha,
            }
            requerimiento_list.append({
                'info': req_info,
                'propuestas': propuestas_por_req[rid],
            })

        context['propuestas'] = propuestas  # Para la tabla original
        context['propuestas_por_req'] = dict(propuestas_por_req)
        context['req_ids_ordenados'] = req_ids_ordenados
        context['requerimiento_list'] = requerimiento_list

        status_counts = {}
        for s, label in PropuestaWhatsApp.Status.choices:
            cnt = propuestas.filter(status=s).count()
            if cnt > 0:
                status_counts[s] = {'label': label, 'count': cnt}
        context['status_counts'] = status_counts

        context['total_propuestas'] = propuestas.count()

        # Filtrar por status si viene en GET
        status_filter = self.request.GET.get('status')
        if status_filter:
            # Filtrar propuestas_por_req también
            filtered_reqs = defaultdict(list)
            for rid, props in propuestas_por_req.items():
                filtered = [p for p in props if p.status == status_filter]
                if filtered:
                    filtered_reqs[rid] = filtered
            context['propuestas_por_req'] = dict(filtered_reqs)
            filtered_ids = [rid for rid in req_ids_ordenados if rid in filtered_reqs]
            context['req_ids_ordenados'] = filtered_ids
            context['requerimiento_list'] = [
                item for item in requerimiento_list if item['info']['id'] in filtered_reqs
            ]
            context['status_activo'] = status_filter
        else:
            context['status_activo'] = ''

        return context


# ===================================================================
# Vistas para Inmobiliaria
# ===================================================================

class InmobiliariaListView(ListView):
    """Listado de inmobiliarias."""
    model = Inmobiliaria
    template_name = 'agentes/lista_inmobiliarias.html'
    context_object_name = 'inmobiliarias'
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(nombre__icontains=busqueda)

        orden = self.request.GET.get('orden', '-creado_en')
        ordenes_validos = ['nombre', '-nombre', 'creado_en', '-creado_en']
        if orden in ordenes_validos:
            queryset = queryset.order_by(orden)
        else:
            queryset = queryset.order_by('-creado_en')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Inmobiliarias'
        context['busqueda'] = self.request.GET.get('q', '')

        # Stats para el dashboard
        context['total_inmobiliarias'] = Inmobiliaria.objects.count()
        context['total_agentes'] = Agente.objects.count()
        context['inmobiliarias_con_agentes'] = Inmobiliaria.objects.annotate(num_agentes=Count('agente')).filter(num_agentes__gt=0).count()
        return context


class InmobiliariaCreateView(CreateView):
    """Crear una nueva inmobiliaria."""
    model = Inmobiliaria
    form_class = InmobiliariaForm
    template_name = 'agentes/formulario_inmobiliaria.html'
    success_url = reverse_lazy('agentes:lista_inmobiliarias')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nueva Inmobiliaria'
        context['accion'] = 'Crear'
        context['google_maps_api_key'] = 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Inmobiliaria creada correctamente.')
        return super().form_valid(form)


class InmobiliariaUpdateView(UpdateView):
    """Editar una inmobiliaria existente."""
    model = Inmobiliaria
    form_class = InmobiliariaForm
    template_name = 'agentes/formulario_inmobiliaria.html'
    success_url = reverse_lazy('agentes:lista_inmobiliarias')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Inmobiliaria'
        context['accion'] = 'Guardar cambios'
        context['google_maps_api_key'] = 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Inmobiliaria actualizada correctamente.')
        return super().form_valid(form)


class InmobiliariaDeleteView(DeleteView):
    """Eliminar una inmobiliaria."""
    model = Inmobiliaria
    template_name = 'agentes/confirmar_eliminar.html'
    success_url = reverse_lazy('agentes:lista_inmobiliarias')
    context_object_name = 'objeto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Eliminar Inmobiliaria'
        context['tipo_objeto'] = 'inmobiliaria'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Inmobiliaria eliminada correctamente.')
        return super().form_valid(form)
