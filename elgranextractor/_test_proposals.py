import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

url = 'https://api.propify.pe/api/crm/proposals/'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
d = json.loads(urllib.request.urlopen(req, timeout=15).read())
print(f"Tipo: {type(d).__name__}")
if isinstance(d, list):
    print(f"Items: {len(d)}")
    if d: print(json.dumps(d[0], indent=2, ensure_ascii=False)[:1500])
elif isinstance(d, dict):
    print(f"Keys: {list(d.keys())}")
    print(f"Count: {d.get('count', 'N/A')}")
    results = d.get('results', d.get('data', []))
    print(f"Results: {len(results) if isinstance(results, list) else 'N/A'}")
    if results and isinstance(results, list) and len(results) > 0:
        print(json.dumps(results[0], indent=2, ensure_ascii=False)[:1500])
    else:
        print(json.dumps(d, indent=2, ensure_ascii=False)[:1500])
