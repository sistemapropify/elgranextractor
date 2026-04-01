from django.urls import path
from . import views

app_name = 'analisis_crm'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('analytics/', views.analytics, name='analytics'),
]