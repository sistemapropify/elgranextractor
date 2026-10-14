from django.urls import path
from . import views

app_name = 'catastro'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/status/', views.status, name='status'),
    path('api/start/', views.start, name='start'),
    path('api/jobs/<slug:job_id>/stop/', views.stop, name='stop'),
    path('lotes/<str:lot_id>/', views.lot, name='lot'),
    path('archivos/<str:lot_id>/<str:filename>/', views.asset, name='asset'),
    path('paginas/<str:lot_id>/<str:filename>/<int:page_number>/', views.document_page, name='document_page'),
]
