from django.urls import path
from . import views

app_name = 'prospects'

urlpatterns = [
    # Lista
    path('', views.prospect_list, name='list'),

    # Captura nueva (GET = form, POST = guarda foto+GPS)
    path('capture/', views.CaptureView.as_view(), name='capture'),

    # Detalle / edición manual
    path('<int:pk>/detail/', views.ProspectDetailView.as_view(), name='detail'),

    # Procesar con Qwen3-VL (POST → JSON)
    path('<int:pk>/process/', views.ProcessImageView.as_view(), name='process'),
]
