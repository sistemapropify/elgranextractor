from django.urls import path
from . import views

app_name = 'agentes'

urlpatterns = [
    # Agentes
    path('', views.AgenteListView.as_view(), name='lista_agentes'),
    path('nuevo/', views.AgenteCreateView.as_view(), name='crear_agente'),
    path('<int:pk>/editar/', views.AgenteUpdateView.as_view(), name='editar_agente'),
    path('<int:pk>/propuestas/', views.AgentePropuestasView.as_view(), name='agente-propuestas'),
    path('<int:pk>/eliminar/', views.AgenteDeleteView.as_view(), name='eliminar_agente'),

    # Inmobiliarias (rutas con prefijo para evitar conflicto con agentes)
    path('inmobiliarias/', views.InmobiliariaListView.as_view(), name='lista_inmobiliarias'),
    path('inmobiliarias/nueva/', views.InmobiliariaCreateView.as_view(), name='crear_inmobiliaria'),
    path('inmobiliarias/<int:pk>/editar/', views.InmobiliariaUpdateView.as_view(), name='editar_inmobiliaria'),
    path('inmobiliarias/<int:pk>/eliminar/', views.InmobiliariaDeleteView.as_view(), name='eliminar_inmobiliaria'),
]
