from django.http import HttpResponse
from django.urls import include, path
from . import control_views as views
urlpatterns = [path('', include(([
    path('', views.board, name='home'),
    path('resumen/', lambda request: HttpResponse(), name='dashboard'),
    path('control/', views.board, name='control_board'),
    path('control/apk/', lambda request: HttpResponse(), name='mobile_updates'),
    path('control/sincronizar/', views.sync_lead, name='control_sync'),
    path('lead/<int:lead_id>/', views.lead_detail, name='control_lead'),
    path('action/<int:obligation_id>/', views.obligation_action, name='control_action'),
    path('assign/<int:lead_id>/', views.assign, name='control_assign'),
    path('commit/<int:lead_id>/', views.add_commitment, name='control_commitment'),
    path('rules/', views.rules, name='control_rules'),
    path('directory/', views.directory, name='control_directory'),
    path('directory/<int:member_id>/', views.directory, name='control_member'),
    path('remarketing/', lambda request: HttpResponse(), name='remarketing_campaigns'),
], 'analisis_crm')))]
