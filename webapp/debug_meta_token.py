"""
Debug detallado del token de Meta Ads.
"""
import os
import sys
import requests
import json

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('META_ACCESS_TOKEN')
app_id = os.getenv('META_APP_ID')
app_secret = os.getenv('META_APP_SECRET')
account_id = os.getenv('META_AD_ACCOUNT_ID')

print("=== DEBUG DETALLADO TOKEN META ADS ===\n")
print(f"App ID: {app_id}")
print(f"App Secret: {app_secret[:10]}...")
print(f"Account ID: {account_id}")
print(f"Token (inicio): {token[:30]}...")
print(f"Token longitud: {len(token) if token else 0} caracteres")

if not all([token, app_id, app_secret]):
    print("[ERROR] Faltan variables de entorno")
    sys.exit(1)

# 1. Verificar token con debug_token endpoint
print("\n1. DEBUG TOKEN ENDPOINT:")
try:
    url = "https://graph.facebook.com/debug_token"
    params = {
        'input_token': token,
        'access_token': f"{app_id}|{app_secret}"
    }
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if 'data' in data:
        token_info = data['data']
        print(f"   [OK] Token valido")
        print(f"   App ID: {token_info.get('app_id')}")
        print(f"   User ID: {token_info.get('user_id')}")
        print(f"   Tipo: {token_info.get('type')}")
        print(f"   Aplicacion: {token_info.get('application')}")
        
        # Expiración
        expires_at = token_info.get('expires_at')
        if expires_at:
            from datetime import datetime
            expiry = datetime.fromtimestamp(expires_at)
            now = datetime.now()
            days = (expiry - now).days
            print(f"   Expira: {expiry} ({days} dias)")
        else:
            print(f"   Expira: Nunca (token del sistema)")
        
        # Scopes
        scopes = token_info.get('scopes', [])
        print(f"   Permisos ({len(scopes)}): {', '.join(scopes[:10])}")
        
        # Verificar permisos críticos
        critical_scopes = {'ads_management', 'ads_read', 'business_management'}
        missing = critical_scopes - set(scopes)
        if missing:
            print(f"   [ADVERTENCIA] Faltan permisos criticos: {missing}")
        else:
            print(f"   [OK] Todos los permisos criticos presentes")
            
    else:
        print(f"   [ERROR] Error: {data.get('error', {}).get('message', 'Unknown error')}")
        
except Exception as e:
    print(f"   [ERROR] Error en debug_token: {e}")

# 2. Verificar estado de la aplicación
print("\n2. ESTADO DE LA APLICACION:")
try:
    url = f"https://graph.facebook.com/{app_id}"
    params = {
        'access_token': token,
        'fields': 'id,name,app_domains,category,app_type'
    }
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if 'id' in data:
        print(f"   [OK] App encontrada: {data.get('name')} ({data.get('id')})")
        print(f"   Categoria: {data.get('category')}")
        print(f"   Tipo: {data.get('app_type')}")
        
        # Verificar modo de la app
        url = f"https://graph.facebook.com/{app_id}/"
        params = {'access_token': f"{app_id}|{app_secret}", 'fields': 'review_status'}
        response = requests.get(url, params=params, timeout=10)
        review_data = response.json()
        print(f"   Estado revision: {review_data.get('review_status', 'Unknown')}")
        
    else:
        print(f"   [ERROR] Error: {data.get('error', {}).get('message', 'Unknown error')}")
        
except Exception as e:
    print(f"   [ERROR] Error: {e}")

# 3. Verificar acceso a la cuenta de ads
print("\n3. VERIFICACION CUENTA DE ADS:")
try:
    # Primero obtener el ID numérico (sin 'act_')
    numeric_id = account_id.replace('act_', '') if account_id.startswith('act_') else account_id
    
    url = f"https://graph.facebook.com/v25.0/{numeric_id}"
    params = {
        'access_token': token,
        'fields': 'id,name,account_status,amount_spent,balance'
    }
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if 'id' in data:
        print(f"   [OK] Cuenta encontrada: {data.get('name', 'No name')}")
        print(f"   ID: {data.get('id')}")
        print(f"   Estado: {data.get('account_status')}")
        print(f"   Gasto: {data.get('amount_spent')}")
        print(f"   Balance: {data.get('balance')}")
    else:
        error = data.get('error', {})
        print(f"   [ERROR] Error: {error.get('message', 'Unknown error')}")
        print(f"   Codigo: {error.get('code')}")
        print(f"   Subcodigo: {error.get('error_subcode')}")
        print(f"   Tipo: {error.get('type')}")
        
except Exception as e:
    print(f"   [ERROR] Error: {e}")

# 4. Probar endpoint de campañas (el que falla)
print("\n4. PRUEBA ENDPOINT CAMPAÑAS:")
try:
    url = f"https://graph.facebook.com/v25.0/{account_id}/campaigns"
    params = {
        'access_token': token,
        'fields': 'id,name',
        'limit': 1
    }
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if 'data' in data:
        campaigns = data['data']
        print(f"   [OK] Exito! {len(campaigns)} campaña(s) encontrada(s)")
        for camp in campaigns[:1]:
            print(f"   Campaña: {camp.get('id')} - {camp.get('name')}")
    else:
        error = data.get('error', {})
        print(f"   [ERROR] Error en campañas: {error.get('message', 'Unknown error')}")
        print(f"   Codigo completo: {json.dumps(error, indent=2)}")
        
except Exception as e:
    print(f"   [ERROR] Error: {e}")

print("\n=== DEBUG COMPLETADO ===")