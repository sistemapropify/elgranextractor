from django.urls import path
from . import mobile_api, views

app_name = 'prospects'

urlpatterns = [
    path('api/mobile/login/', mobile_api.mobile_login, name='mobile-login'),
    path('api/mobile/captures/', mobile_api.mobile_capture, name='mobile-capture'),
    path('api/mobile/captures/<int:pk>/', mobile_api.mobile_capture_detail, name='mobile-capture-detail'),

    # Lista
    path('', views.prospect_list, name='list'),

    # Captura nueva (GET = form, POST = guarda foto+GPS)
    path('capture/', views.CaptureView.as_view(), name='capture'),

    # Detalle / edición manual
    path('<int:pk>/detail/', views.ProspectDetailView.as_view(), name='detail'),

    # Procesar con Qwen3-VL (POST → JSON)
    path('<int:pk>/process/', views.ProcessImageView.as_view(), name='process'),
]
