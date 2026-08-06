from django.urls import path

from . import property_bot_views


app_name = "property_bot_dashboard"

urlpatterns = [
    path("", property_bot_views.property_bot_dashboard, name="dashboard"),
    path("emulador/", property_bot_views.property_bot_emulator, name="emulator"),
    path(
        "emulador/api/reply/",
        property_bot_views.property_bot_emulator_reply,
        name="emulator_reply",
    ),
    path("<uuid:interaction_id>/", property_bot_views.property_bot_interaction_detail, name="detail"),
    path("<uuid:interaction_id>/review/", property_bot_views.property_bot_review, name="review"),
]
