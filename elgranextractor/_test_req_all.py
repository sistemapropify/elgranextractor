import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

# Get all requirements (multiple pages)
all_reqs = {}
url = 'https://api.propify.pe/api/crm/requirements/?page_size=200'
while url:
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    for r in d.get('results', []):
        all_reqs[r['id']] = r['assigned_to_name']
    url = d.get('next')

print(f"Total requirements loaded: {len(all_reqs)}")

# Get matches and check if req exists
url2 = 'https://api.propify.pe/api/crm/requirement-matches/?page_size=10'
req2 = urllib.request.Request(url2, headers={'Authorization': f'Bearer {tok}'})
d2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
print(f"Sample matches:")
for m in d2['results'][:5]:
    rid = m['requirement']
    has = rid in all_reqs
    print(f"  Match req#{rid} -> {'FOUND: ' + str(all_reqs.get(rid)) if has else 'NOT FOUND'}")
