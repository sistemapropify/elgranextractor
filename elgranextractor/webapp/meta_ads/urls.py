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
from .views_rediseno import MetaDashboardRedisenoView, MetaCampaignDetailView
from .views_exacto import MetaDashboardExactoView

app_name = 'meta_ads'

urlpatterns = [
    path('dashboard/', MetaDashboardView.as_view(), name='meta_ads_dashboard'),
    path('dashboard/rediseno/', MetaDashboardRedisenoView.as_view(), name='meta_ads_dashboard_rediseno'),
    path('dashboard/exacto/', MetaDashboardExactoView.as_view(), name='meta_ads_dashboard_exacto'),
    path('analisis/historico/', MetaHistoricalAnalysisView.as_view(), name='meta_ads_historical'),
    path('campañas/', MetaCampaignListView.as_view(), name='meta_ads_campaigns'),
    path('sincronizar/', MetaSyncView.as_view(), name='meta_ads_sync'),
    path('campaña/<str:campaign_id>/', MetaCampaignDetailView.as_view(), name='meta_ads_campaign_detail'),
]