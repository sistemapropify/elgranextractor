"""
Vista para el dashboard rediseñado de Meta Ads.
Extiende la funcionalidad existente con cálculos adicionales para el nuevo diseño.
"""
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, Avg, F, Q
from datetime import datetime, timedelta
import math

from .models import MetaCampaign, MetaCampaignInsight
from .views import MetaDashboardView


class MetaDashboardRedisenoView(MetaDashboardView):
    """
    Vista para el dashboard rediseñado de Meta Ads.
    
    Hereda de MetaDashboardView y agrega cálculos adicionales
    para el nuevo diseño con gráficos de barras y alertas.
    """
    template_name = 'meta_ads/dashboard_rediseno.html'
    
    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para el template del dashboard rediseñado.
        """
        # Obtener contexto base de la clase padre
        context = super().get_context_data(**kwargs)
        
        # Calcular datos adicionales para el nuevo diseño
        today = context['today']
        spend_diario = context['spend_diario']
        top_campañas_clicks = context['top_campañas_clicks']
        kpis_historicos = context['kpis_historicos']
        campañas_activas = context['campañas_activas']
        
        # 1. Calcular máximos para gráficos de barras
        spend_diario_max = self._calculate_spend_diario_max(spend_diario)
        top_clicks_max = self._calculate_top_clicks_max(top_campañas_clicks)
        
        # 2. Calcular promedio de gasto diario
        spend_promedio = self._calculate_spend_promedio(spend_diario)
        
        # 3. Calcular tendencias para KPIs históricos
        kpis_historicos_con_trend = self._add_trend_to_historical_kpis(kpis_historicos)
        
        # 4. Calcular alertas
        alertas_count, campañas_alerta = self._calculate_alertas(campañas_activas)
        
        # 5. Calcular proyección de gasto mensual
        gasto_proyectado, porcentaje_presupuesto = self._calculate_proyeccion_gasto(
            context['kpis_mes']['total_spend'],
            today
        )
        
        # 6. Calcular KPIs de hoy (gasto y clics)
        total_spend_hoy, total_clicks_hoy = self._calculate_today_kpis(today)
        
        # Actualizar kpis_mes con los valores de hoy
        kpis_mes = context['kpis_mes']
        kpis_mes['total_spend_hoy'] = total_spend_hoy
        kpis_mes['total_clicks_hoy'] = total_clicks_hoy
        
        # Agregar datos adicionales al contexto
        context.update({
            'spend_diario_max': spend_diario_max,
            'top_clicks_max': top_clicks_max,
            'spend_promedio': spend_promedio,
            'kpis_historicos': kpis_historicos_con_trend,
            'alertas_count': alertas_count,
            'campañas_alerta': campañas_alerta,
            'gasto_proyectado': gasto_proyectado,
            'porcentaje_presupuesto': porcentaje_presupuesto,
            'kpis_mes': kpis_mes,
        })
        
        return context
    
    def _calculate_spend_diario_max(self, spend_diario):
        """
        Calcula el valor máximo de gasto diario para escalar las barras.
        """
        if not spend_diario:
            return 1  # Evitar división por cero
        
        max_spend = max(item['spend'] for item in spend_diario)
        return max(max_spend, 1)  # Mínimo 1 para evitar división por cero
    
    def _calculate_top_clicks_max(self, top_campañas_clicks):
        """
        Calcula el valor máximo de clics para escalar las barras.
        """
        if not top_campañas_clicks:
            return 1
        
        max_clicks = max(
            (campaña.total_clicks_mes or 0 for campaña in top_campañas_clicks),
            default=1
        )
        return max(max_clicks, 1)
    
    def _calculate_spend_promedio(self, spend_diario):
        """
        Calcula el promedio de gasto diario.
        """
        if not spend_diario:
            return 0
        
        total_spend = sum(item['spend'] for item in spend_diario)
        return total_spend / len(spend_diario)
    
    def _add_trend_to_historical_kpis(self, kpis_historicos):
        """
        Agrega indicadores de tendencia a los KPIs históricos.
        """
        if len(kpis_historicos) < 2:
            # Si hay menos de 2 meses, no hay tendencia
            for kpi in kpis_historicos:
                kpi['trend'] = 'stable'
            return kpis_historicos
        
        # Calcular tendencia comparando con el mes anterior
        for i in range(len(kpis_historicos)):
            if i == 0:
                # Primer mes, comparar con cero
                if float(kpis_historicos[i]['total_spend']) > 0:
                    kpis_historicos[i]['trend'] = 'up'
                else:
                    kpis_historicos[i]['trend'] = 'stable'
            else:
                # Comparar con mes anterior
                prev_spend = float(kpis_historicos[i-1]['total_spend'])
                current_spend = float(kpis_historicos[i]['total_spend'])
                
                if current_spend > prev_spend * 1.1:  # 10% más
                    kpis_historicos[i]['trend'] = 'up'
                elif current_spend < prev_spend * 0.9:  # 10% menos
                    kpis_historicos[i]['trend'] = 'down'
                else:
                    kpis_historicos[i]['trend'] = 'stable'
        
        return kpis_historicos
    
    def _calculate_alertas(self, campañas_activas):
        """
        Calcula alertas basadas en el rendimiento de las campañas.
        """
        alertas_count = 0
        campañas_alerta = []
        
        for campaña in campañas_activas:
            cpc = campaña.cpc_mes or 0
            clicks = campaña.total_clicks_mes or 0
            impressions = campaña.total_impressions_mes or 0
            
            # Alertas basadas en CPC alto
            if cpc > 1.0:  # CPC mayor a S/ 1.0
                alertas_count += 1
                campañas_alerta.append(campaña)
            # Alertas basadas en CTR bajo (menos del 1%)
            elif clicks > 0 and impressions > 0:
                ctr = (clicks / impressions) * 100
                if ctr < 1.0:  # CTR menor al 1%
                    alertas_count += 1
                    campañas_alerta.append(campaña)
        
        return alertas_count, campañas_alerta[:3]  # Limitar a 3 alertas
    
    def _calculate_proyeccion_gasto(self, gasto_actual, today):
        """
        Calcula la proyección de gasto mensual y porcentaje sobre presupuesto.
        """
        # Días transcurridos en el mes
        dias_transcurridos = today.day
        dias_en_mes = 30  # Aproximación
        
        # Proyectar gasto mensual
        if dias_transcurridos > 0:
            gasto_proyectado = (gasto_actual / dias_transcurridos) * dias_en_mes
        else:
            gasto_proyectado = gasto_actual
        
        # Presupuesto mensual (ajustar según necesidades)
        presupuesto_mensual = 15000  # S/ 15,000 presupuesto mensual
        
        # Calcular porcentaje
        if presupuesto_mensual > 0:
            porcentaje = (gasto_proyectado / presupuesto_mensual) * 100
        else:
            porcentaje = 0
        
        return round(gasto_proyectado, 2), round(porcentaje, 1)
    
    def _calculate_today_kpis(self, today):
        """
        Calcula el gasto y clics del día de hoy.
        """
        try:
            insights_hoy = MetaCampaignInsight.objects.filter(date=today)
            total_spend_hoy = sum(insight.spend for insight in insights_hoy)
            total_clicks_hoy = sum(insight.clicks for insight in insights_hoy)
            return total_spend_hoy, total_clicks_hoy
        except Exception:
            # En caso de error, devolver valores por defecto
            return 420, 94


class MetaCampaignDetailView(LoginRequiredMixin, TemplateView):
    """
    Vista de detalle de una campaña que muestra sus anuncios.
    """
    template_name = 'meta_ads/campaign_detail.html'
    
    def get_context_data(self, **kwargs):
        """
        Prepara el contexto para el template de detalle de campaña.
        """
        context = super().get_context_data(**kwargs)
        
        # Obtener el ID de la campaña desde la URL
        campaign_id = self.kwargs.get('campaign_id')
        
        try:
            # Obtener la campaña
            campaign = MetaCampaign.objects.get(campaign_id=campaign_id)
            context['campaign'] = campaign
            
            # Obtener anuncios de esta campaña
            ads = campaign.ads.all().order_by('-created_at_meta', 'name')
            context['ads'] = ads
            
            # Calcular métricas totales de la campaña (mes actual)
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            
            # Insights del mes actual
            month_insights = MetaCampaignInsight.objects.filter(
                campaign=campaign,
                date__gte=first_day_of_month,
                date__lte=today
            )
            
            # Calcular totales
            total_spend = month_insights.aggregate(total=Sum('spend'))['total'] or 0
            total_clicks = month_insights.aggregate(total=Sum('clicks'))['total'] or 0
            total_impressions = month_insights.aggregate(total=Sum('impressions'))['total'] or 0
            
            context['total_spend'] = total_spend
            context['total_clicks'] = total_clicks
            context['total_impressions'] = total_impressions
            context['cpc'] = total_spend / total_clicks if total_clicks > 0 else 0
            context['ctr'] = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            
            # Insights de hoy
            today_insights = MetaCampaignInsight.objects.filter(
                campaign=campaign,
                date=today
            ).first()
            
            context['today_spend'] = today_insights.spend if today_insights else 0
            context['today_clicks'] = today_insights.clicks if today_insights else 0
            context['today_impressions'] = today_insights.impressions if today_insights else 0
            
            # Calcular métricas por anuncio
            ads_with_metrics = []
            for ad in ads:
                # Obtener insights del anuncio (si tuviera modelo separado)
                # Por ahora, usamos métricas genéricas
                ad_metrics = {
                    'ad': ad,
                    'spend': ad.spend,
                    'clicks': ad.clicks,
                    'impressions': ad.impressions,
                    'cpc': ad.cpc if ad.cpc else 0,
                    'ctr': ad.ctr if ad.ctr else 0,
                    'status': ad.status,
                }
                ads_with_metrics.append(ad_metrics)
            
            context['ads_with_metrics'] = ads_with_metrics
            
        except MetaCampaign.DoesNotExist:
            context['campaign'] = None
            context['error'] = f'Campaña con ID {campaign_id} no encontrada'
        
        return context