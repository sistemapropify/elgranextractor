import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

# Get sample match requirement IDs
url = 'https://api.propify.pe/api/crm/requirement-matches/?page_size=10'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
d = json.loads(urllib.request.urlopen(req, timeout=15).read())
req_ids_in_matches = set(m['requirement'] for m in d['results'])
print(f"Requirement IDs in matches (sample 10): {sorted(req_ids_in_matches)}")

# Test single requirement_id filter
for rid in sorted(req_ids_in_matches)[:3]:
    url2 = f'https://api.propify.pe/api/crm/requirement-matches/?requirement_id={rid}'
    req2 = urllib.request.Request(url2, headers={'Authorization': f'Bearer {tok}'})
    d2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
    print(f"  requirement_id={rid}: count={d2.get('count', 0)}")
