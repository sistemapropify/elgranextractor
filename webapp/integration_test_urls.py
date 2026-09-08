from django.urls import include, path
from intelligence import views as identity_views

urlpatterns = [
    path('login/', identity_views.login_view, name='login'),
    path('logout/', identity_views.logout_view, name='logout'),
    path('register/', identity_views.register_view, name='register'),
    path('api/n8n/', include('n8n_bridge.urls')),
    path('ingestas/', include('ingestas.urls')),
    path('prospects/', include('prospects.urls')),
    path('analisis-crm/', include('analisis_crm.urls')),
    path('intelligence/', include('intelligence.urls')),
]
