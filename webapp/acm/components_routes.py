from django.urls import path
from . import components_views as views

urlpatterns = [
    path('analisis/', views.page, name='acm_analisis'),
    path('analisis-pruebas/', views.page, name='acm_analisis_pruebas'),
    path('componentes/buscar/', views.search, name='componentes_buscar'),
    path('componentes/calcular/', views.recalculate, name='componentes_calcular'),
    # Keep requests from already-open test dashboards working.
    path('pruebas/componentes/buscar/', views.search),
    path('pruebas/componentes/calcular/', views.recalculate),
]
