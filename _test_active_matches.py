import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = json.loads(urllib.request.urlopen(login, timeout=15).read())
tok = resp['access']

# Try without filter
for url in [
    'https://api.propify.pe/api/crm/matches/active-matches/',
    'https://api.propify.pe/api/crm/matches/active-matches/?requirement=1',
    'https://api.propify.pe/api/crm/matches/active-matches/?requirement=39',
]:
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    n = len(d) if isinstance(d, list) else 'N/A'
    print(f"active-matches (req in URL): {n} items")
    if isinstance(d, list) and d:
        print(json.dumps(d[0], indent=2)[:800])
        break
