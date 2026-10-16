from django.urls import include, path
from . import portal_views as portal
from .components_routes import urlpatterns as components
patterns = [
    path('', portal.dashboard, name='acm_dashboard'),
    path('login/', portal.login, name='login'),
    path('logout/', portal.logout, name='logout'),
    path('historial/', portal.history, name='historial_acm'),
    path('historial/<uuid:uuid>/eliminar/', portal.delete_analysis, name='delete_analysis'),
    path('configuracion/', portal.role_settings, name='role_settings'),
    path('configuracion/roles/<int:role_id>/', portal.role_policy, name='role_policy'),
    path('vista-por-rol/', portal.perspective, name='perspective'),
    path('pdm/', portal.pdm_query, name='pdm_query'),
    path('capas-mapa/', portal.map_layers, name='map_layers'),
    path('fotos/revisar/', portal.review_photo, name='review_photo'),
    path('fotos/<str:ticket>/', portal.photo, name='photo'),
] + components
urlpatterns = [path('acm/', include((patterns, 'acm')))]
