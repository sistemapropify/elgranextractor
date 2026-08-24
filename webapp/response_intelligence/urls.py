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
    path(
        "calidad-motor-ia/aprobar-ejemplo/",
        views.approve_example,
        name="approve_example",
    ),
    path(
        "calidad-motor-ia/toggle-ejemplo/",
        views.toggle_example,
        name="toggle_example",
    ),
    path(
        "calidad-motor-ia/sugerir-candidatos/",
        views.suggest_candidates,
        name="suggest_candidates",
    ),
    path(
        "calidad-motor-ia/toggle-shadow/",
        views.toggle_shadow,
        name="toggle_shadow",
    ),
    # Reglas de negocio del motor (prompt del sistema)
    path(
        "calidad-motor-ia/reglas/crear/",
        views.create_rule,
        name="create_rule",
    ),
    path(
        "calidad-motor-ia/reglas/toggle/",
        views.toggle_rule,
        name="toggle_rule",
    ),
    path(
        "calidad-motor-ia/reglas/eliminar/",
        views.delete_rule,
        name="delete_rule",
    ),
    path(
        "calidad-motor-ia/reglas/editar/",
        views.edit_rule,
        name="edit_rule",
    ),
]
