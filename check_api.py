import urllib.request
import urllib.error
import json

url = "http://localhost:8000/market-analysis/api/heatmap-data/"

try:
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
    content = response.read().decode('utf-8')
    data = json.loads(content)
    print("API response keys:", data.keys())
    if 'properties' in data:
        print("Number of properties:", len(data['properties']))
    else:
        print("No 'properties' key in response")
    # Print first few items
    print("Sample:", json.dumps(data, indent=2)[:500])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    content = e.read().decode('utf-8')
    print("Error content:", content[:500])
except Exception as e:
    print("Other error:", e)