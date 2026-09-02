from django.urls import path
from . import mobile_api, views

app_name = 'prospects'

urlpatterns = [
    path('api/mobile/version/', mobile_api.mobile_version, name='mobile-version'),
    path('api/mobile/login/', mobile_api.mobile_login, name='mobile-login'),
    path('api/mobile/captures/', mobile_api.mobile_capture, name='mobile-capture'),
    path('api/mobile/captures/<int:pk>/', mobile_api.mobile_capture_detail, name='mobile-capture-detail'),
    path('api/mobile/crm-alerts/', mobile_api.mobile_crm_alerts, name='mobile-crm-alerts'),
    path('api/mobile/crm-alerts/<int:pk>/', mobile_api.mobile_crm_alert_detail, name='mobile-crm-alert-detail'),
    path('api/mobile/notification-device/', mobile_api.mobile_notification_device, name='mobile-notification-device'),

    # Lista
    path('', views.prospect_list, name='list'),

    # Captura nueva (GET = form, POST = guarda foto+GPS)
    path('capture/', views.CaptureView.as_view(), name='capture'),

    # Detalle / edición manual
    path('<int:pk>/detail/', views.ProspectDetailView.as_view(), name='detail'),

    # Procesar con Qwen3-VL (POST → JSON)
    path('<int:pk>/process/', views.ProcessImageView.as_view(), name='process'),
]
