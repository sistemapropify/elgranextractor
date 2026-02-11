"""
URLs para las vistas mejoradas de la API REST.
"""

from django.urls import path
from . import views_mejoradas

urlpatterns = [
    # Captura mejorada
    path('captura-mejorada/', views_mejoradas.CapturaMejoradaAPIView.as_view(), name='captura-mejorada'),
    
    # Reprocesamiento
    path('reprocesamiento/', views_mejoradas.ReprocesamientoAPIView.as_view(), name='reprocesamiento'),
    
    # Calidad de capturas
    path('calidad-capturas/', views_mejoradas.CalidadCapturasAPIView.as_view(), name='calidad-capturas'),
    
    # Comparación de capturas
    path('comparacion-capturas/<int:fuente_id>/', views_mejoradas.ComparacionCapturasAPIView.as_view(), name='comparacion-capturas'),
    
    # Captura manual mejorada (compatible con interfaz existente)
    path('captura-manual-mejorada/', views_mejoradas.CapturaManualMejoradaAPIView.as_view(), name='captura-manual-mejorada'),
]

# Agregar prefijo de versión
urlpatterns = [path('api/v1/mejorado/', include(urlpatterns))]