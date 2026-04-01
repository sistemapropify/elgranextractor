"""
Comando de gestión para sincronizar datos con la Meta Marketing API.
"""
import sys
from django.core.management.base import BaseCommand
from django.utils import timezone

from meta_ads.services import MetaAdsSyncService


class Command(BaseCommand):
    """
    Comando para sincronizar campañas y métricas desde la Meta Marketing API.
    
    Uso:
        python manage.py sync_meta_ads
        python manage.py sync_meta_ads --days 30
        python manage.py sync_meta_ads --days 7 --verbose
    """
    
    help = 'Sincroniza campañas y métricas desde la Meta Marketing API'
    
    def add_arguments(self, parser):
        """
        Define los argumentos del comando.
        """
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Número de días hacia atrás para sincronizar métricas (por defecto: 30)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra información detallada durante la ejecución'
        )
    
    def handle(self, *args, **options):
        """
        Ejecuta el comando de sincronización.
        """
        days = options['days']
        verbose = options['verbose']
        
        self.stdout.write(self.style.SUCCESS(
            f'[INICIANDO] Iniciando sincronización de Meta Ads (últimos {days} días)...'
        ))
        
        if verbose:
            self.stdout.write(f'  [CALENDARIO] Días a sincronizar: {days}')
            self.stdout.write(f'  [RELOJ] Hora de inicio: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
        
        try:
            # Crear instancia del servicio
            sync_service = MetaAdsSyncService()
            
            # Ejecutar sincronización completa
            summary = sync_service.sync_all(days=days)
            
            # Mostrar resultados
            self._display_results(summary, verbose)
            
        except ImportError as e:
            self.stdout.write(self.style.ERROR(
                '[ERROR] Error: No se pudo importar facebook-business.'
            ))
            self.stdout.write(self.style.WARNING(
                '   Asegúrate de haber instalado la dependencia:'
            ))
            self.stdout.write(self.style.WARNING(
                '   pip install facebook-business>=20.0.0'
            ))
            self.stdout.write(self.style.ERROR(f'   Detalles: {e}'))
            sys.exit(1)
            
        except KeyError as e:
            self.stdout.write(self.style.ERROR(
                '[ERROR] Error: Variable de entorno no encontrada.'
            ))
            self.stdout.write(self.style.WARNING(
                '   Asegúrate de tener configuradas las siguientes variables en .env:'
            ))
            self.stdout.write(self.style.WARNING(
                '   META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN, META_AD_ACCOUNT_ID'
            ))
            self.stdout.write(self.style.ERROR(f'   Variable faltante: {e}'))
            sys.exit(1)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Error durante la sincronización: {e}'
            ))
            
            if verbose:
                import traceback
                self.stdout.write(self.style.ERROR('   Traceback:'))
                for line in traceback.format_exc().split('\n'):
                    if line.strip():
                        self.stdout.write(self.style.ERROR(f'   {line}'))
            
            sys.exit(1)
    
    def _display_results(self, summary, verbose):
        """
        Muestra los resultados de la sincronización.
        
        Args:
            summary (dict): Resumen de la sincronización
            verbose (bool): Si se debe mostrar información detallada
        """
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('[OK] Sincronización completada'))
        self.stdout.write('=' * 60)
        
        # Mostrar resumen básico
        self.stdout.write(self.style.SUCCESS(
            f'[GRAFICO] Campañas: {summary["campañas_totales"]} procesadas '
            f'({summary["campañas_creadas"]} nuevas, {summary["campañas_actualizadas"]} actualizadas)'
        ))
        
        self.stdout.write(self.style.SUCCESS(
            f'[TENDENCIA] Métricas: {summary["insights_totales"]} procesadas '
            f'({summary["insights_creados"]} nuevas, {summary["insights_actualizados"]} actualizadas)'
        ))
        
        self.stdout.write(self.style.SUCCESS(
            f'[CALENDARIO] Período: Últimos {summary["dias_sincronizados"]} días'
        ))
        
        self.stdout.write(self.style.SUCCESS(
            f'[RELOJ] Finalizado: {summary["fecha_sincronizacion"][:19].replace("T", " ")}'
        ))
        
        # Mostrar información detallada si se solicita
        if verbose:
            self.stdout.write('\n' + '-' * 60)
            self.stdout.write(self.style.HTTP_INFO('[LISTA] Resumen detallado:'))
            
            for key, value in summary.items():
                if key not in ['fecha_sincronizacion', 'estado']:
                    formatted_key = key.replace('_', ' ').title()
                    self.stdout.write(f'  {formatted_key}: {value}')
            
            self.stdout.write('-' * 60)
        
        # Mostrar advertencias si hubo errores
        if summary.get('estado') == 'error':
            self.stdout.write(self.style.WARNING(
                '\n[ADVERTENCIA] La sincronización completó con errores.'
            ))
            if 'error' in summary:
                self.stdout.write(self.style.WARNING(f'   Error: {summary["error"]}'))
        
        self.stdout.write('\n' + self.style.SUCCESS('[CELEBRACION] ¡Sincronización finalizada con éxito!'))