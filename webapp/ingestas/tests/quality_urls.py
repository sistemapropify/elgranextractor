from django.urls import path
from ingestas.property_quality_views import PropertyEditor
urlpatterns = [path('edit/<int:pk>/', PropertyEditor.as_view())]
