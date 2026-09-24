from django.urls import path, include
from django.http import HttpResponse
from acm import components_views
patterns=[path('analisis/',lambda r:HttpResponse('Original'),name='acm_analisis'),
    path('analisis-pruebas/',components_views.page,name='acm_analisis_pruebas'),
    path('pruebas/componentes/buscar/',components_views.search),
    path('pruebas/componentes/calcular/',components_views.recalculate)]
urlpatterns=[path('acm/',include((patterns,'acm')))]
