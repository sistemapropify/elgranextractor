"""
Servicio para sincronizar datos con la Meta Marketing API.
"""
import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import transaction

from .models import MetaCampaign, MetaCampaignInsight

logger = logging.getLogger(__name__)


class MetaAdsSyncService:
    """
    Servicio para sincronizar campañas y métricas desde la Meta Marketing API.
    """
    
    def __init__(self):
        """Inicializa la conexión con la API de Meta."""
        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            
            self.FacebookAdsApi = FacebookAdsApi
            self.AdAccount = AdAccount
            self.Campaign = None
            
            # Inicializar API
            FacebookAdsApi.init(
                app_id=os.environ.get('META_APP_ID', ''),
                app_secret=os.environ.get('META_APP_SECRET', ''),
                access_token=os.environ.get('META_ACCESS_TOKEN', ''),
            )
            
            # Crear objeto de cuenta
            account_id = os.environ.get('META_AD_ACCOUNT_ID', '')
            if not account_id.startswith('act_'):
                account_id = f'act_{account_id}'
            
            self.account = AdAccount(account_id)
            
            # Importar Campaign dinámicamente
            from facebook_business.adobjects.campaign import Campaign
            self.Campaign = Campaign
            
            logger.info("✅ Servicio MetaAdsSyncService inicializado correctamente")
            
        except ImportError as e:
            logger.error(f"❌ Error al importar facebook-business: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error al inicializar MetaAdsSyncService: {e}")
            raise
    
    def sync_campaigns(self):
        """
        Sincroniza todas las campañas desde la API de Meta.
        
        Returns:
            tuple: (campañas_creadas, campañas_actualizadas)
        """
        try:
            logger.info("🔄 Sincronizando campañas desde Meta API...")
            
            # Obtener campañas desde la API
            fields = [
                'id', 'name', 'status', 'objective', 
                'daily_budget', 'created_time'
            ]
            params = {
                'limit': 1000
            }
            
            campaigns = self.account.get_campaigns(fields=fields, params=params)
            
            creadas = 0
            actualizadas = 0
            
            for campaign_data in campaigns:
                try:
                    campaign_id = campaign_data.get('id')
                    if not campaign_id:
                        continue
                    
                    # Parsear fecha de creación
                    created_time_str = campaign_data.get('created_time', '')
                    created_at_meta = None
                    if created_time_str:
                        try:
                            created_at_meta = datetime.strptime(
                                created_time_str[:10], '%Y-%m-%d'
                            ).date()
                        except (ValueError, TypeError):
                            pass
                    
                    # Parsear presupuesto diario
                    daily_budget = None
                    budget_data = campaign_data.get('daily_budget', {})
                    if budget_data and 'amount' in budget_data:
                        try:
                            daily_budget = Decimal(str(budget_data['amount'])) / 100  # Convertir de centavos
                        except (ValueError, TypeError):
                            pass
                    
                    # Crear o actualizar campaña
                    obj, created = MetaCampaign.objects.update_or_create(
                        campaign_id=campaign_id,
                        defaults={
                            'name': campaign_data.get('name', ''),
                            'status': campaign_data.get('status', MetaCampaign.STATUS_ACTIVE),
                            'objective': campaign_data.get('objective', ''),
                            'daily_budget': daily_budget,
                            'created_at_meta': created_at_meta,
                        }
                    )
                    
                    if created:
                        creadas += 1
                        logger.debug(f"  ✅ Campaña creada: {obj.name} ({campaign_id})")
                    else:
                        actualizadas += 1
                        logger.debug(f"  🔄 Campaña actualizada: {obj.name} ({campaign_id})")
                        
                except Exception as e:
                    logger.error(f"  ❌ Error procesando campaña {campaign_data.get('id')}: {e}")
                    continue
            
            logger.info(f"✅ Sincronización de campañas completada: {creadas} creadas, {actualizadas} actualizadas")
            return creadas, actualizadas
            
        except Exception as e:
            logger.error(f"❌ Error en sync_campaigns: {e}")
            return 0, 0
    
    def sync_insights(self, days=30):
        """
        Sincroniza métricas diarias para campañas activas.
        
        Args:
            days (int): Número de días hacia atrás para sincronizar
            
        Returns:
            tuple: (insights_creados, insights_actualizados)
        """
        try:
            logger.info(f"🔄 Sincronizando insights de los últimos {days} días...")
            
            # Obtener campañas activas
            active_campaigns = MetaCampaign.objects.filter(
                status=MetaCampaign.STATUS_ACTIVE
            )
            
            total_campaigns = active_campaigns.count()
            logger.info(f"  📊 Procesando {total_campaigns} campañas activas")
            
            creados = 0
            actualizados = 0
            
            # Calcular fechas
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days - 1)
            
            for campaign in active_campaigns:
                try:
                    campaign_creados, campaign_actualizados = self._sync_campaign_insights(
                        campaign, start_date, end_date
                    )
                    creados += campaign_creados
                    actualizados += campaign_actualizados
                    
                except Exception as e:
                    logger.error(f"  ❌ Error sincronizando insights para campaña {campaign.campaign_id}: {e}")
                    continue
            
            logger.info(f"✅ Sincronización de insights completada: {creados} creados, {actualizados} actualizados")
            return creados, actualizados
            
        except Exception as e:
            logger.error(f"❌ Error en sync_insights: {e}")
            return 0, 0
    
    def _sync_campaign_insights(self, campaign, start_date, end_date):
        """
        Sincroniza insights para una campaña específica.
        
        Args:
            campaign (MetaCampaign): Instancia de la campaña
            start_date (date): Fecha de inicio
            end_date (date): Fecha de fin
            
        Returns:
            tuple: (creados, actualizados)
        """
        try:
            # Obtener insights desde la API
            fields = [
                'date_start',
                'impressions',
                'clicks',
                'spend',
                'reach',
                'cpc',
                'ctr',
                'frequency'
            ]
            
            params = {
                'time_range': {
                    'since': start_date.strftime('%Y-%m-%d'),
                    'until': end_date.strftime('%Y-%m-%d')
                },
                'time_increment': 1  # Datos diarios
            }
            
            # Obtener objeto Campaign de la API
            api_campaign = self.Campaign(campaign.campaign_id)
            insights_data = api_campaign.get_insights(fields=fields, params=params)
            
            creados = 0
            actualizados = 0
            
            for insight_data in insights_data:
                try:
                    date_str = insight_data.get('date_start', '')
                    if not date_str:
                        continue
                    
                    # Parsear fecha
                    date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    
                    # Parsear métricas
                    impressions = int(insight_data.get('impressions', 0))
                    clicks = int(insight_data.get('clicks', 0))
                    spend = Decimal(insight_data.get('spend', 0))
                    reach = int(insight_data.get('reach', 0))
                    
                    # Parsear métricas derivadas (pueden venir como strings)
                    cpc_str = insight_data.get('cpc', '0')
                    ctr_str = insight_data.get('ctr', '0')
                    frequency_str = insight_data.get('frequency', '0')
                    
                    cpc = Decimal(cpc_str) if cpc_str and cpc_str != '0' else None
                    ctr = Decimal(ctr_str) if ctr_str and ctr_str != '0' else None
                    frequency = Decimal(frequency_str) if frequency_str and frequency_str != '0' else None
                    
                    # Crear o actualizar insight
                    obj, created = MetaCampaignInsight.objects.update_or_create(
                        campaign=campaign,
                        date=date,
                        defaults={
                            'impressions': impressions,
                            'clicks': clicks,
                            'spend': spend,
                            'reach': reach,
                            'cpc': cpc,
                            'ctr': ctr,
                            'frequency': frequency,
                        }
                    )
                    
                    if created:
                        creados += 1
                    else:
                        actualizados += 1
                        
                except Exception as e:
                    logger.error(f"    ❌ Error procesando insight para fecha {date_str}: {e}")
                    continue
            
            logger.debug(f"  ✅ Campaña {campaign.name}: {creados} creados, {actualizados} actualizados")
            return creados, actualizados
            
        except Exception as e:
            logger.error(f"  ❌ Error obteniendo insights para campaña {campaign.campaign_id}: {e}")
            return 0, 0
    
    def sync_all(self, days=30):
        """
        Ejecuta la sincronización completa de campañas e insights.
        
        Args:
            days (int): Número de días hacia atrás para sincronizar insights
            
        Returns:
            dict: Resumen de la sincronización
        """
        logger.info("🚀 Iniciando sincronización completa de Meta Ads...")
        
        try:
            # Sincronizar campañas
            campaigns_created, campaigns_updated = self.sync_campaigns()
            
            # Sincronizar insights
            insights_created, insights_updated = self.sync_insights(days)
            
            # Resumen
            summary = {
                'campañas_creadas': campaigns_created,
                'campañas_actualizadas': campaigns_updated,
                'campañas_totales': campaigns_created + campaigns_updated,
                'insights_creados': insights_created,
                'insights_actualizados': insights_updated,
                'insights_totales': insights_created + insights_updated,
                'dias_sincronizados': days,
                'fecha_sincronizacion': timezone.now().isoformat(),
                'estado': 'completado'
            }
            
            logger.info("✅ Sincronización completa finalizada")
            logger.info(f"   📊 Resumen: {summary}")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error en sincronización completa: {e}")
            
            summary = {
                'campañas_creadas': 0,
                'campañas_actualizadas': 0,
                'campañas_totales': 0,
                'insights_creados': 0,
                'insights_actualizados': 0,
                'insights_totales': 0,
                'dias_sincronizados': days,
                'fecha_sincronizacion': timezone.now().isoformat(),
                'estado': 'error',
                'error': str(e)
            }
            
            return summary