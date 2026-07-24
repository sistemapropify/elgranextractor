from django.urls import path

from . import views

app_name = 'n8n_bridge'

urlpatterns = [
    path('ping/', views.ping, name='ping'),
    path('message/', views.lead_message, name='lead_message'),
    path('reset/', views.reset_session, name='reset_session'),
]
