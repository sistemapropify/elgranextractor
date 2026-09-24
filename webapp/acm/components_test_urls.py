from django.urls import path, include
from django.http import HttpResponse
from acm.components_routes import urlpatterns as component_routes
patterns=[path('analisis-clasico/',lambda r:HttpResponse('Clásico'),name='acm_analisis_clasico')] + component_routes
urlpatterns=[path('acm/',include((patterns,'acm')))]
