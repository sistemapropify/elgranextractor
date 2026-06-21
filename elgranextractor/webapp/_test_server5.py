import requests, json

# Probar con los mismos datos que envía el frontend
# Incluyendo CSRF token y cookies
url = 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/api/'

# Primero obtener CSRF token
session = requests.Session()
try:
    # Obtener la página principal para conseguir CSRF token
    resp = session.get('http://127.0.0.1:8000/api/v1/intelligence/chat-web/', timeout=10)
    csrf_token = session.cookies.get('csrftoken', '')
    
    data = {
        'message': 'que propiedades tienes en cerro colorado',
        'use_rag': True,
        'collections': [],
        'email': 'usuario_temporal@propifai.com',
        'session_id': 'test-debug-005'
    }
    
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token,
        'Referer': 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/'
    }
    
    resp = session.post(url, json=data, headers=headers, timeout=120)
    
    with open('_test_server_output5.txt', 'w', encoding='utf-8') as f:
        f.write(f'Status: {resp.status_code}\n')
        f.write(f'Cookies: {dict(session.cookies)}\n')
        f.write(f'Content-Type: {resp.headers.get("Content-Type", "N/A")}\n')
        try:
            result = resp.json()
            response_text = result.get('response', '')
            f.write(f'Response length: {len(response_text)} chars\n')
            f.write(f'Response:\n{response_text}\n')
            f.write(f'\nMetadata: {json.dumps(result.get("metadata", {}), indent=2, ensure_ascii=False)}\n')
        except:
            f.write(f'Raw (first 3000 chars):\n{resp.text[:3000]}\n')
    print("Done")
except Exception as e:
    with open('_test_server_output5.txt', 'w', encoding='utf-8') as f:
        f.write(f'Error: {e}\n')
    print(f"Error: {e}")
