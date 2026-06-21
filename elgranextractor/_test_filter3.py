import json, urllib.request

login = urllib.request.Request(
    'https://api.propify.pe/api/auth/token/',
    data=json.dumps({"username":"adminpropify","password":"yosoytupapi"}).encode(),
    headers={'Content-Type': 'application/json'}
)
tok = json.loads(urllib.request.urlopen(login, timeout=15).read())['access']

# Get ALL requirement IDs from the matches API
url = 'https://api.propify.pe/api/crm/requirement-matches/?page_size=200'
all_match_req_ids = set()
while url:
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    for m in d.get('results', []):
        all_match_req_ids.add(m['requirement'])
    url = d.get('next')

print(f"Total unique requirement IDs in matches: {len(all_match_req_ids)}")
print(f"Sample: {sorted(list(all_match_req_ids))[:20]}")

# Get Francisco's requirement IDs
url2 = 'https://api.propify.pe/api/crm/requirements/?page_size=200'
fco_ids = set()
while url2:
    req2 = urllib.request.Request(url2, headers={'Authorization': f'Bearer {tok}'})
    d2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
    for r in d2.get('results', []):
        if 'francisco' in (r.get('assigned_to_name','') or '').lower():
            fco_ids.add(r['id'])
    url2 = d2.get('next')

print(f"\nFrancisco's requirement IDs: {sorted(fco_ids)}")
print(f"Total: {len(fco_ids)}")
print(f"Intersection with match req IDs: {fco_ids & all_match_req_ids}")
