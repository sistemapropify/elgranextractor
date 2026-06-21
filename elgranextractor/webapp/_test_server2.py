import requests

url = 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/'
data = {
    'message': 'hola',
    'use_rag': True,
    'collections': [],
    'session_id': 'test-debug-002'
}

try:
    resp = requests.post(url, json=data, timeout=30)
    with open('_test_server_output2.txt', 'w', encoding='utf-8') as f:
        f.write(f'Status: {resp.status_code}\n')
        f.write(f'Headers: {dict(resp.headers)}\n')
        f.write(f'Content-Type: {resp.headers.get("Content-Type", "N/A")}\n')
        f.write(f'Raw content (first 2000 chars):\n{resp.text[:2000]}\n')
    print("Done")
except Exception as e:
    with open('_test_server_output2.txt', 'w', encoding='utf-8') as f:
        f.write(f'Error: {e}\n')
    print(f"Error: {e}")
