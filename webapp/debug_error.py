import requests
import sys

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
try:
    resp = requests.get(url)
    print('Status:', resp.status_code)
    print('Response body (first 2000 chars):')
    print(resp.text[:2000])
except requests.exceptions.RequestException as e:
    print('Request error:', e)
except Exception as e:
    print('Unexpected error:', e)
    import traceback
    traceback.print_exc()