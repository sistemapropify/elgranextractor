"""
Vistas para el dashboard de Meta Ads.
"""
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, Avg, F, Q
from datetime import datetime, timedelta

from .models import MetaCampaign, MetaCampaignInsight


class MetaDashboardView(LoginRequiredMixin, TemplateView):
    """
    Vista para el dashboard de métricas de Meta Ads.
    
    Requiere autenticación y muestra:
    - KPIs del mes actual
    - Lista de campañas activas
    - Gráfico de gasto diario
    """
    template_name = 'meta_ads/dashboard.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para el template del dashboard.
        """
        context = super().get_context_data(**kwargs)
        
        # Fechas para el mes actual
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)
        
        # 1. Campañas activas con métricas del mes actual
        campañas_activas = MetaCampaign.objects.filter(
            status=MetaCampaign.STATUS_ACTIVE
        ).annotate(
            total_spend_mes=Sum(
                'insights__spend',
                filter=Q(
                    insights__date__gte=first_day_of_month,
                    insights__date__lte=today
                )
            ),
            total_clicks_mes=Sum(
                'insights__clicks',
                filter=Q(
                    insights__date__gte=first_day_of_month,
                    insights__date__lte=today
                )
            ),
            total_impressions_mes=Sum(
                'insights__impressions',
                filter=Q(
                    insights__date__gte=first_day_of_month,
                    insights__date__lte=today
                )
            )
        ).order_by('-total_spend_mes')
        
        # Calcular CPC para cada campaña
        for campaña in campañas_activas:
            total_spend = campaña.total_spend_mes or 0
            total_clicks = campaña.total_clicks_mes or 0
            if total_clicks > 0:
                campaña.cpc_mes = total_spend / total_clicks
            else:
                campaña.cpc_mes = 0
        
        # 2. KPIs del mes actual
        kpis_mes = self._calculate_kpis(first_day_of_month, today)
        
        # 3. KPIs históricos (últimos 6 meses)
        kpis_historicos = self._get_historical_kpis(months=6)
        
        # 4. Top 3 campañas por clics del mes actual
        top_campañas_clicks = campañas_activas.filter(
            total_clicks_mes__gt=0
        ).order_by('-total_clicks_mes')[:3]
        
        # 5. Datos para gráfico de gasto diario (últimos 30 días)
        spend_diario = self._get_daily_spend_data(days=30)
        
        # 6. Datos para gráfico de gasto mensual (últimos 6 meses)
        spend_mensual = self._get_monthly_spend_data(months=6)
        
        # Agregar al contexto
        context.update({
            'campañas_activas': campañas_activas,
            'kpis_mes': kpis_mes,
            'kpis_historicos': kpis_historicos,
            'top_campañas_clicks': top_campañas_clicks,
            'spend_diario': spend_diario,
            'spend_mensual': spend_mensual,
            'today': today,
            'first_day_of_month': first_day_of_month,
        })
        
        return context
    
    def _calculate_kpis(self, start_date, end_date):
        """
        Calcula los KPIs para un período específico.
        
        Args:
            start_date (date): Fecha de inicio
            end_date (date): Fecha de fin
            
        Returns:
            dict: KPIs calculados
        """
        # Obtener insights del período
        insights_periodo = MetaCampaignInsight.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        # Agregar métricas
        agregados = insights_periodo.aggregate(
            total_spend=Sum('spend'),
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions'),
            avg_cpc=Avg('cpc')
        )
        
        # Calcular CPC promedio (evitar división por cero)
        total_spend = agregados['total_spend'] or 0
        total_clicks = agregados['total_clicks'] or 0
        
        if total_clicks > 0:
            cpc_promedio = total_spend / total_clicks
        else:
            cpc_promedio = 0
        
        # Formatear resultados
        return {
            'total_spend': total_spend,
            'total_clicks': total_clicks,
            'total_impresiones': agregados['total_impressions'] or 0,
            'cpc_promedio': cpc_promedio,
            'avg_cpc_from_db': agregados['avg_cpc'] or 0,
        }
    
    def _get_daily_spend_data(self, days=30):
        """
        Obtiene datos de gasto diario para los últimos N días.
        
        Args:
            days (int): Número de días hacia atrás
            
        Returns:
            list: Lista de diccionarios con fecha y gasto
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Obtener datos agregados por día
        daily_data = MetaCampaignInsight.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).values('date').annotate(
            daily_spend=Sum('spend')
        ).order_by('date')
        
        # Crear lista completa de días (incluso días sin datos)
        result = []
        current_date = start_date
        
        while current_date <= end_date:
            # Buscar datos para esta fecha
            data_for_date = next(
                (item for item in daily_data if item['date'] == current_date),
                None
            )
            
            result.append({
                'date': current_date,
                'spend': float(data_for_date['daily_spend']) if data_for_date else 0.0,
                'date_formatted': current_date.strftime('%d/%m')
            })
            
            current_date += timedelta(days=1)
        
        return result
    
    def _get_historical_kpis(self, months=6):
        """
        Obtiene KPIs históricos por mes para los últimos N meses.
        Incluye todos los meses en el rango, incluso si no hay datos.
        
        Args:
            months (int): Número de meses hacia atrás
            
        Returns:
            list: Lista de diccionarios con KPIs por mes
        """
        from django.db.models.functions import TruncMonth
        from dateutil.relativedelta import relativedelta
        
        today = timezone.now().date()
        # Primer día del mes actual
        current_month_start = today.replace(day=1)
        # Primer día del mes N meses atrás
        start_date = current_month_start - relativedelta(months=months-1)
        
        # Agrupar por mes los datos existentes
        monthly_data = MetaCampaignInsight.objects.filter(
            date__gte=start_date,
            date__lte=today
        ).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            total_spend=Sum('spend'),
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions')
        ).order_by('month')
        
        # Convertir a diccionario para búsqueda rápida
        data_dict = {}
        for item in monthly_data:
            month_key = item['month'].strftime('%Y-%m')
            total_spend = item['total_spend'] or 0
            total_clicks = item['total_clicks'] or 0
            
            if total_clicks > 0:
                cpc = total_spend / total_clicks
            else:
                cpc = 0
            
            data_dict[month_key] = {
                'month': item['month'],
                'total_spend': total_spend,
                'total_clicks': total_clicks,
                'total_impressions': item['total_impressions'] or 0,
                'cpc': cpc,
            }
        
        # Generar lista completa de meses
        result = []
        current_month = start_date.replace(day=1)
        
        while current_month <= current_month_start:
            month_key = current_month.strftime('%Y-%m')
            month_name = current_month.strftime('%B %Y')
            
            if month_key in data_dict:
                # Hay datos para este mes
                item = data_dict[month_key]
                result.append({
                    'month': month_key,
                    'month_name': month_name,
                    'total_spend': item['total_spend'],
                    'total_clicks': item['total_clicks'],
                    'total_impressions': item['total_impressions'],
                    'cpc': item['cpc'],
                })
            else:
                # Mes sin datos
                result.append({
                    'month': month_key,
                    'month_name': month_name,
                    'total_spend': 0,
                    'total_clicks': 0,
                    'total_impressions': 0,
                    'cpc': 0,
                })
            
            # Avanzar al siguiente mes
            current_month = current_month + relativedelta(months=1)
        
        return result
    
    def _get_monthly_spend_data(self, months=6):
        """
        Obtiene datos de gasto mensual para gráfico.
        
        Args:
            months (int): Número de meses hacia atrás
            
        Returns:
            dict: Datos para gráfico Chart.js
        """
        historical_data = self._get_historical_kpis(months=months)
        
        # Preparar datos para gráfico
        labels = []
        spend_data = []
        clicks_data = []
        
        for item in historical_data:
            labels.append(item['month_name'])
            spend_data.append(float(item['total_spend']))
            clicks_data.append(int(item['total_clicks']))
        
        return {
            'labels': labels,
            'spend': spend_data,
            'clicks': clicks_data,
        }


class MetaHistoricalAnalysisView(LoginRequiredMixin, TemplateView):
    """
    Vista para el análisis histórico detallado.
    """
    template_name = 'meta_ads/historical_analysis.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Crear una instancia de MetaDashboardView para acceder a sus métodos
        dashboard_view = MetaDashboardView()
        
        # Obtener KPIs históricos (12 meses)
        kpis_historicos = dashboard_view._get_historical_kpis(months=12)
        
        # Datos para gráficos
        spend_mensual = dashboard_view._get_monthly_spend_data(months=12)
        
        context.update({
            'kpis_historicos': kpis_historicos,
            'spend_mensual': spend_mensual,
            'today': today,
        })
        return context


class MetaCampaignListView(LoginRequiredMixin, TemplateView):
    """
    Vista para listar todas las campañas.
    """
    template_name = 'meta_ads/campaign_list.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener todas las campañas
        campañas = MetaCampaign.objects.all().order_by('-created_at')
        
        # Calcular estadísticas por estado
        campañas_activas_count = campañas.filter(status=MetaCampaign.STATUS_ACTIVE).count()
        campañas_pausadas_count = campañas.filter(status=MetaCampaign.STATUS_PAUSED).count()
        campañas_archivadas_count = campañas.filter(status=MetaCampaign.STATUS_ARCHIVED).count()
        
        context.update({
            'campañas': campañas,
            'campañas_activas_count': campañas_activas_count,
            'campañas_pausadas_count': campañas_pausadas_count,
            'campañas_archivadas_count': campañas_archivadas_count,
        })
        return context


class MetaSyncView(LoginRequiredMixin, TemplateView):
    """
    Vista para sincronización manual de datos.
    """
    template_name = 'meta_ads/sync.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Información básica sobre sincronización
        last_sync = MetaCampaignInsight.objects.order_by('-date').first()
        
        context.update({
            'last_sync_date': last_sync.date if last_sync else None,
            'total_campaigns': MetaCampaign.objects.count(),
            'total_insights': MetaCampaignInsight.objects.count(),
        })
        return context
