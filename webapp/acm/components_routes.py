from django.urls import path
from . import components_views as views

urlpatterns = [
    path('analisis/', views.page, name='acm_analisis'),
    path('analisis-pruebas/', views.page, name='acm_analisis_pruebas'),
    path('componentes/buscar/', views.search, name='componentes_buscar'),
    path('componentes/calcular/', views.recalculate, name='componentes_calcular'),
    path('componentes/explicar/', views.explain_ai, name='componentes_explicar'),
    path('componentes/informe-word/', views.word_report, name='componentes_informe_word'),
    path('componentes/informe-pdf/', views.pdf_report, name='componentes_informe_pdf'),
    path('componentes/guardar/', views.save_history, name='componentes_guardar'),
    path('componentes/historial/<uuid:uuid>/informe-word/', views.history_word_report, name='componentes_historial_word'),
    path('componentes/historial/<uuid:uuid>/informe-pdf/', views.history_pdf_report, name='componentes_historial_pdf'),
    # Keep requests from already-open test dashboards working.
    path('pruebas/componentes/buscar/', views.search),
    path('pruebas/componentes/calcular/', views.recalculate),
]
