"""
URLs para la app meta_ads.
"""
from django.urls import path
from .views import (
    MetaDashboardView,
    MetaHistoricalAnalysisView,
    MetaCampaignListView,
    MetaSyncView
)

app_name = 'meta_ads'

urlpatterns = [
    path('dashboard/', MetaDashboardView.as_view(), name='meta_ads_dashboard'),
    path('analisis/historico/', MetaHistoricalAnalysisView.as_view(), name='meta_ads_historical'),
    path('campañas/', MetaCampaignListView.as_view(), name='meta_ads_campaigns'),
    path('sincronizar/', MetaSyncView.as_view(), name='meta_ads_sync'),
]