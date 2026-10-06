from django.urls import path, include
from django.http import HttpResponse
from acm.components_routes import urlpatterns as component_routes
# Enlaces que la plantilla del dashboard ofrece a módulos fuera del alcance de
# estas pruebas aisladas; se resuelven con stubs para poder renderizar la página.
patterns=[
    path('analisis-clasico/',lambda r:HttpResponse('Clásico'),name='acm_analisis_clasico'),
    path('modelos/',lambda r:HttpResponse('Modelos'),name='modelos_dashboard'),
    path('modelos/estimacion/',lambda r:HttpResponse('Estimación'),name='modelo_estimacion'),
] + component_routes
urlpatterns=[path('acm/',include((patterns,'acm')))]
