import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

# Test received-matches
url = 'https://api.propify.pe/api/crm/matches/received-matches/'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
d = json.loads(urllib.request.urlopen(req, timeout=15).read())
print(f"Tipo: {type(d).__name__}")
if isinstance(d, list):
    print(f"Items: {len(d)}")
    if d:
        print(json.dumps(d[0], indent=2)[:1000])
elif isinstance(d, dict):
    print(f"Keys: {list(d.keys())}")
    print(json.dumps(d, indent=2)[:1000])
