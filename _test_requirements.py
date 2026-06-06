import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

# Get first requirement
url = 'https://api.propify.pe/api/crm/requirements/?page_size=1'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
d = json.loads(urllib.request.urlopen(req, timeout=15).read())
if d['results']:
    print("=== REQUIREMENT FIELDS ===")
    for k, v in d['results'][0].items():
        print(f"  {k}: {v}")
