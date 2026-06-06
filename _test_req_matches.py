import json, urllib.request

# Login
login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = json.loads(urllib.request.urlopen(login, timeout=15).read())
tok = resp['access']
print(f"Token obtenido: {tok[:30]}...")

# Query requirement-matches for requirement 39
req = urllib.request.Request(
    'https://api.propify.pe/api/crm/requirement-matches/?requirement=39&page_size=3',
    headers={'Authorization': f'Bearer {tok}'}
)
d = json.loads(urllib.request.urlopen(req, timeout=15).read())
print(f"\nTotal matches para requirement 39: {d['count']}")
for r in d['results'][:3]:
    print(f"  #{r['id']}: {r['property_code']} | Score: {r['score']}% | {r['property_title'][:60]}")
