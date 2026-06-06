import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

# Find "Francisco" assigned requirements
url = 'https://api.propify.pe/api/crm/requirements/?page_size=200'
all_reqs = {}
while url:
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    for r in d.get('results', []):
        all_reqs[r['id']] = r
    url = d.get('next')

# Find francisco
fco_reqs = [rid for rid, r in all_reqs.items() if 'francisco' in (r.get('assigned_to_name','') or '').lower()]
print(f"Requirements with 'francisco': {len(fco_reqs)}")
if fco_reqs:
    print(f"IDs: {fco_reqs[:10]}")
    print(f"Names: {[all_reqs[rid].get('assigned_to_name') for rid in fco_reqs[:5]]}")

# Test API filter with one ID
test_id = fco_reqs[0] if fco_reqs else 1
url2 = f'https://api.propify.pe/api/crm/requirement-matches/?requirement_id={test_id}'
req2 = urllib.request.Request(url2, headers={'Authorization': f'Bearer {tok}'})
d2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
print(f"\nDirect filter requirement_id={test_id}: count={d2.get('count', 'N/A')}")
