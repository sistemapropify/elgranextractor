from django.urls import path

from . import views
from . import property_bot_views

app_name = 'n8n_bridge'

urlpatterns = [
    path('ping/', views.ping, name='ping'),
    path('message/', views.lead_message, name='lead_message'),
    path('reset/', views.reset_session, name='reset_session'),
    path('property-bot/v1/initial-response/', property_bot_views.initial_property_response, name='initial_property_response'),
]
