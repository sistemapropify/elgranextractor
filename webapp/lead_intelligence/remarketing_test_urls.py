from django.http import HttpResponse
from django.urls import include, path
from . import remarketing_views as views

urlpatterns = [path('', include(([
    path('campaigns/', views.campaigns, name='remarketing_campaigns'),
    path('new/', views.campaign_edit, name='remarketing_campaign_new'),
    path('edit/<int:campaign_id>/', views.campaign_edit, name='remarketing_campaign_edit'),
    path('action/<int:campaign_id>/', views.campaign_action, name='remarketing_campaign_action'),
    path('report/', views.deliveries_report, name='remarketing_deliveries'),
    path('history/', lambda request: HttpResponse(), name='remarketing'),
], 'analisis_crm')))]
