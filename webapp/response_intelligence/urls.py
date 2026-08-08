from django.urls import path

from . import views

app_name = "response_intelligence"

urlpatterns = [
    path(
        "calidad-motor-ia/",
        views.response_dashboard,
        name="dashboard",
    ),
    path(
        "calidad-motor-ia/evaluar/",
        views.evaluate_draft,
        name="evaluate_draft",
    ),
    path(
        "calidad-motor-ia/promover/",
        views.promote_draft,
        name="promote_draft",
    ),
]
