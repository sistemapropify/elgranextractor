import json, urllib.request, sys

# Login
login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = json.loads(urllib.request.urlopen(login, timeout=15).read())
tok = resp['access']

# Test different param names
for param in ['requirement', 'requirement_id', 'requirement__id']:
    try:
        url = f'https://api.propify.pe/api/crm/requirement-matches/?{param}=1&page_size=1'
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        print(f'{param}=1 -> count={d["count"]}')
    except Exception as e:
        print(f'{param}=1 -> ERROR: {e}')
