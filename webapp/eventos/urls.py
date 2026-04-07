from django.urls import path
from . import views

app_name = 'eventos'

urlpatterns = [
    path('', views.dashboard_eventos, name='dashboard_eventos'),
    path('<int:evento_id>/', views.detalle_evento, name='detalle_evento'),
    path('api/eventos/', views.api_eventos, name='api_eventos'),
]