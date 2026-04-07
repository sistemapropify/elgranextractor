"""
URL configuration for webapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
import views

urlpatterns = [
    # Página principal
    path('', views.home, name='home'),
    
    # Fuentes Web
    path('fuentes-web/', views.fuentes_web, name='fuentes_web'),
    
    # Capturas - Nueva sección
    path('capturas/', views.capturas_view, name='capturas'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # API del dashboard
    path('api/estadisticas/', views.estadisticas_api, name='estadisticas_api'),
    path('api/fuentes/', views.fuentes_api, name='fuentes_api'),
    path('api/agregar-fuente/', views.agregar_fuente_api, name='agregar_fuente_api'),
    path('api/ejecutar-sistema/', views.ejecutar_sistema_api, name='ejecutar_sistema_api'),
    path('api/descubrir-urls/', views.descubrir_urls_api, name='descubrir_urls_api'),
    path('api/actualizar-frecuencias/', views.actualizar_frecuencias_api, name='actualizar_frecuencias_api'),
    
    # API de Capturas (públicas para desarrollo)
    path('api/capturas/', views.capturas_api, name='capturas_api'),
    path('api/capturas/<int:captura_id>/', views.captura_detalle_api, name='captura_detalle_api'),
    path('api/capturas/estadisticas/', views.estadisticas_capturas_api, name='estadisticas_capturas_api'),
    path('api/capturas/manual/', views.captura_manual_api, name='captura_manual_api'),
    path('api/fuentes/<int:fuente_id>/procesar/', views.procesar_fuente_api, name='procesar_fuente_api'),
    
    # API REST (DRF)
    path('api/', include('api.urls')),
    
    # Ingestas de Excel Inmobiliario
    path('ingestas/', include('ingestas.urls')),
    
    # Requerimientos de clientes
    path('requerimientos/', include('requerimientos.urls')),
    
    # Cuadrantización Inmobiliaria
    path('cuadrantizacion/', include('cuadrantizacion.urls')),
    
    # Propiedades de la base de datos Propifai/Propify
    path('propifai/', include('propifai.urls')),
    
    # Matching inmobiliario
    path('matching/', include(('matching.urls', 'matching'), namespace='matching')),
    
    # ACM - Análisis Comparativo de Mercado
    path('acm/', include('acm.urls')),
    
    # Market Analysis - Análisis de Mercado (Heatmap + Dashboard)
    path('market-analysis/', include('market_analysis.urls')),
    
    # Análisis CRM - Dashboard de leads
    path('analisis-crm/', include('analisis_crm.urls')),  # Habilitado para desarrollo
    
    # Eventos - Dashboard de análisis de eventos
    path('eventos/', include('eventos.urls')),
    
    # Meta Ads - Dashboard de campañas publicitarias de Meta
    # path('meta-ads/', include('meta_ads.urls')),  # Comentado temporalmente debido a error de importación en producción
]
