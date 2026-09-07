from django.urls import path
from . import mobile_api, views
from . import control_api
from . import app_updates

app_name = 'prospects'

urlpatterns = [
    path('api/mobile/version/publish/', app_updates.publish_api, name='publish_version'),
    path('api/mobile/apk/<int:asset_id>/', app_updates.download_apk, name='download_apk'),
    path('api/mobile/notification-device/', control_api.register_device, name='notification_device'),
    path('api/mobile/crm-alerts/', control_api.alerts, name='crm_alerts'),
    path('api/mobile/crm-alerts/<int:pk>/', control_api.alert_detail, name='crm_alert_detail'),
    # Autenticación propia del módulo (Propify, independiente de Prometeo)
    path('login/', views.propify_login, name='login'),
    path('logout/', views.propify_logout, name='logout'),

    # API de la APK: el Bearer token es emitido y validado por Propify.
    path('api/mobile/version/', mobile_api.mobile_version, name='mobile_version'),
    path('api/mobile/login/', mobile_api.mobile_login, name='mobile_login'),
    path('api/mobile/captures/', mobile_api.mobile_capture, name='mobile_capture'),
    path('api/mobile/captures/<int:pk>/', mobile_api.mobile_capture_detail, name='mobile_capture_detail'),

    # Lista
    path('', views.prospect_list, name='list'),
    path('dashboard/', views.prospect_dashboard, name='dashboard'),

    # Captura nueva (GET = form, POST = guarda foto+GPS)
    path('capture/', views.CaptureView.as_view(), name='capture'),

    # Detalle / edición manual
    path('<int:pk>/detail/', views.ProspectDetailView.as_view(), name='detail'),

    # Procesar con Qwen3-VL (POST → JSON)
    path('<int:pk>/process/', views.ProcessImageView.as_view(), name='process'),
]
