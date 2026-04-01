import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from meta_ads.services import MetaAdsSyncService

def test_api():
    print("=== Probando conexion a Meta API ===")
    
    try:
        service = MetaAdsSyncService()
        print("[OK] Servicio inicializado correctamente")
        
        # Intentar obtener campañas directamente
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount
        from facebook_business.adobjects.campaign import Campaign
        
        import environ
        env = environ.Env()
        environ.Env.read_env('webapp/.env')
        
        app_id = env('META_APP_ID')
        app_secret = env('META_APP_SECRET')
        access_token = env('META_ACCESS_TOKEN')
        account_id = env('META_AD_ACCOUNT_ID')
        
        print(f"App ID: {app_id}")
        print(f"Account ID: {account_id}")
        print(f"Token (primeros 20 chars): {access_token[:20]}...")
        
        # Inicializar API
        FacebookAdsApi.init(app_id, app_secret, access_token)
        
        # Obtener cuenta
        account = AdAccount(account_id)
        
        # Intentar obtener campañas
        print("\n[LUPA] Obteniendo campañas...")
        campaigns = account.get_campaigns(fields=[
            Campaign.Field.id,
            Campaign.Field.name,
            Campaign.Field.status,
            Campaign.Field.objective,
        ], params={'limit': 10})
        
        print(f"[OK] Se encontraron {len(campaigns)} campañas")
        
        for i, camp in enumerate(campaigns):
            print(f"  {i+1}. {camp['id']} - {camp['name']} ({camp['status']}) - {camp.get('objective', 'N/A')}")
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_api()