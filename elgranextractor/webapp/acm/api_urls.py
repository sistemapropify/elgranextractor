from django.urls import path
from . import api_views

urlpatterns = [
    path('calcular/', api_views.CalcularACMAPIView.as_view(), name='api-acm-calcular'),
    path('comparables/', api_views.ComparablesAPIView.as_view(), name='api-acm-comparables'),
]
