from django.urls import include, path


urlpatterns = [
    path('agentes-externos/', include('external_agents.urls')),
]
