from django.urls import include, path
from . import portal_views as portal
from . import cadastral_views
from . import property_gallery
from .components_routes import urlpatterns as components
patterns = [
    path('catastro/configuracion/', cadastral_views.configuration, name='cadastral_config'),
    path('catastro/revisiones/', cadastral_views.revisions, name='cadastral_revisions'),
    path('catastro/fuentes/<slug:source_id>/radio/', cadastral_views.reference_geometry, name='cadastral_reference'),
    path('catastro/lotes/<str:lot_id>/', cadastral_views.lot, name='cadastral_lot'),
    path('catastro/lotes/<str:lot_id>/fachada/', cadastral_views.facade, name='cadastral_facade'),
    path('catastro/lotes/<str:lot_id>/reporte.pdf', cadastral_views.report_pdf, name='cadastral_report_pdf'),
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
    path('galeria/<str:ticket>/', property_gallery.gallery, name='property_gallery'),
    path('fotos/<str:ticket>/', portal.photo, name='photo'),
] + components
urlpatterns = [path('acm/', include((patterns, 'acm')))]
