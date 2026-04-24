import requests, json, sys

url = 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/'
data = {
    'message': 'que propiedades tienes en cerro colorado',
    'use_rag': True,
    'collections': [],
    'session_id': 'test-debug-001'
}

try:
    resp = requests.post(url, json=data, timeout=60)
    with open('_test_server_output.txt', 'w', encoding='utf-8') as f:
        f.write(f'Status: {resp.status_code}\n')
        result = resp.json()
        response_text = result.get('response', '')
        f.write(f'Response length: {len(response_text)} chars\n')
        f.write(f'Response:\n{response_text}\n')
        f.write(f'\nMetadata: {json.dumps(result.get("metadata", {}), indent=2, ensure_ascii=False)}\n')
    print("Success - check _test_server_output.txt")
except Exception as e:
    with open('_test_server_output.txt', 'w', encoding='utf-8') as f:
        f.write(f'Error: {e}\n')
    print(f"Error: {e}")
