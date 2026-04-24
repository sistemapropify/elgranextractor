"""Prueba del chat para buscar propiedades en Cerro Colorado"""
import requests
import json
import sys
import time

url = 'http://localhost:8000/api/v1/intelligence/chat-web/api/'
data = {
    'message': 'hola tienes propiedades en cerro colorado que me puedas mostrar?',
    'collections': ['propiedades_propify'],
    'conversation_id': None,
    'user_id': None,
    'phone': '51999999999'
}

print(f"[{time.strftime('%H:%M:%S')}] Enviando solicitud...")
print(f"URL: {url}")
print(f"Data: {json.dumps(data, ensure_ascii=False)}")
sys.stdout.flush()

try:
    r = requests.post(url, json=data, timeout=180)
    print(f"[{time.strftime('%H:%M:%S')}] Status: {r.status_code}")
    sys.stdout.flush()
    
    result = r.json()
    
    print(f"success: {result.get('success')}")
    print(f"message: {result.get('message', '')}")
    print(f"response: {result.get('response', '')}")
    print(f"rag_context_used: {result.get('rag_context_used')}")
    print(f"retrieved_documents_count: {result.get('retrieved_documents_count')}")
    sys.stdout.flush()
    
    if 'data' in result:
        d = result['data']
        rag_context = d.get('rag_context', [])
        print(f"rag_context count: {len(rag_context)}")
        for i, ctx in enumerate(rag_context):
            print(f"  [{i}] {ctx.get('title', 'sin titulo')} - {ctx.get('distrito', 'sin distrito')}")
        print(f"sources: {d.get('sources', [])}")
    
    sys.stdout.flush()
except requests.Timeout:
    print(f"[{time.strftime('%H:%M:%S')}] TIMEOUT - la solicitud tomó más de 180 segundos")
    sys.stdout.flush()
except Exception as e:
    print(f"[{time.strftime('%H:%M:%S')}] ERROR: {type(e).__name__}: {e}")
    sys.stdout.flush()
