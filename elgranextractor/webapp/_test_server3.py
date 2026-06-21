import requests, json

# Probar la URL correcta de la API
url = 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/api/'
data = {
    'message': 'que propiedades tienes en cerro colorado',
    'use_rag': True,
    'collections': [],
    'session_id': 'test-debug-003'
}

try:
    resp = requests.post(url, json=data, timeout=60)
    with open('_test_server_output3.txt', 'w', encoding='utf-8') as f:
        f.write(f'Status: {resp.status_code}\n')
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
    with open('_test_server_output3.txt', 'w', encoding='utf-8') as f:
        f.write(f'Error: {e}\n')
    print(f"Error: {e}")
