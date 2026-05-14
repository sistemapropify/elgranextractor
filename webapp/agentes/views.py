from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.db.models import Count
from .models import Agente, Inmobiliaria
from .forms import AgenteForm, InmobiliariaForm


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
