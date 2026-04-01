"""
Script para probar la validez del token de Meta Ads.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from meta_ads.services import MetaAdsSyncService

print("=== PRUEBA DE TOKEN META ADS ===\n")

try:
    # Crear instancia del servicio
    print("1. Inicializando servicio...")
    service = MetaAdsSyncService()
    print("   [OK] Servicio inicializado")
    
    # Intentar obtener campañas (prueba simple)
    print("\n2. Probando conexión con API...")
    try:
        # Intentar obtener una campaña
        fields = ['id', 'name']
        params = {'limit': 1}
        campaigns = service.account.get_campaigns(fields=fields, params=params)
        campaign_count = len(list(campaigns))
        print(f"   [OK] Conexión exitosa. Se encontraron {campaign_count} campaña(s)")
        
        # Mostrar información de la primera campaña
        campaigns = service.account.get_campaigns(fields=fields, params=params)
        for campaign in campaigns:
            print(f"   [INFO] Campaña: {campaign.get('id')} - {campaign.get('name')}")
            break
            
    except Exception as e:
        print(f"   [ERROR] Error al conectar con la API: {e}")
        print(f"   Tipo de error: {type(e).__name__}")
        
        # Verificar si es error de token
        error_msg = str(e).lower()
        if 'token' in error_msg or 'expired' in error_msg or 'invalid' in error_msg:
            print("\n   [ADVERTENCIA] EL TOKEN PODRÍA ESTAR VENCIDO O INVÁLIDO")
        elif 'permission' in error_msg:
            print("\n   [ADVERTENCIA] ERROR DE PERMISOS - El token no tiene los permisos necesarios")
        elif 'rate limit' in error_msg:
            print("\n   [ADVERTENCIA] LÍMITE DE TASA EXCEDIDO")
            
except ImportError as e:
    print(f"[ERROR] Error de importación: {e}")
    print("   Asegúrate de tener instalado 'facebook-business'")
except Exception as e:
    print(f"[ERROR] Error general: {e}")
    import traceback
    traceback.print_exc()

print("\n=== PRUEBA COMPLETADA ===")