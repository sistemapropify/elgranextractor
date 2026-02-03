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
from . import views

urlpatterns = [
    # Página principal
    path('', views.home, name='home'),
    
    # Fuentes Web
    path('fuentes-web/', views.fuentes_web, name='fuentes_web'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # API del dashboard
    path('api/estadisticas/', views.estadisticas_api, name='estadisticas_api'),
    path('api/fuentes/', views.fuentes_api, name='fuentes_api'),
    path('api/agregar-fuente/', views.agregar_fuente_api, name='agregar_fuente_api'),
    path('api/ejecutar-sistema/', views.ejecutar_sistema_api, name='ejecutar_sistema_api'),
    path('api/descubrir-urls/', views.descubrir_urls_api, name='descubrir_urls_api'),
    path('api/actualizar-frecuencias/', views.actualizar_frecuencias_api, name='actualizar_frecuencias_api'),
    
    # API REST (DRF)
    path('api/', include('api.urls')),
]
