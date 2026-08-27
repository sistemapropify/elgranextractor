from django.urls import path

from . import views

app_name = "property_traceability"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/property/<int:property_id>/", views.workflow_detail, name="workflow_detail"),
]


