from django.urls import path
from . import views

app_name = 'requerimientos'

urlpatterns = [
    # Subir archivo
    path('subir/', views.SubirExcelRequerimientoView.as_view(), name='subir'),
    
    # Validar mapeo
    path('validar/', views.ValidarMapeoRequerimientoView.as_view(), name='validar_mapeo'),
    
    # Procesar datos
    path('procesar/', views.ProcesarRequerimientoView.as_view(), name='procesar'),
    
    # Lista de requerimientos
    path('lista/', views.ListaRequerimientosView.as_view(), name='lista'),
    
    # Detalle de requerimiento
    path('detalle/<int:pk>/', views.DetalleRequerimientoView.as_view(), name='detalle'),
    
    # Análisis inteligente con DeepSeek
    path('analisis-inteligente/', views.AnalisisInteligenteView.as_view(), name='analisis_inteligente'),
    
    # Análisis completo del archivo Excel
    path('analisis-completo/', views.AnalisisCompletoView.as_view(), name='analisis_completo'),
]