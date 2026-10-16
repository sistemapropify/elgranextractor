from django.urls import path
from . import api_views
from .access import legacy_admin

urlpatterns = [
    path('calcular/', legacy_admin(api_views.CalcularACMAPIView.as_view()), name='api-acm-calcular'),
    path('comparables/', legacy_admin(api_views.ComparablesAPIView.as_view()), name='api-acm-comparables'),
]
