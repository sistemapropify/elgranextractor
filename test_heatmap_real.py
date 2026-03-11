import urllib.request
import urllib.error
import json

url = "http://localhost:8000/market-analysis/heatmap/"

try:
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
    content = response.read().decode('utf-8')
    print("Content length:", len(content))
    # Buscar la variable heatmapDataJson
    import re
    match = re.search(r'const heatmapDataJson = (\[.*?\]);', content, re.DOTALL)
    if match:
        data_json = match.group(1)
        print("Found heatmapDataJson, length:", len(data_json))
        data = json.loads(data_json)
        print("Number of points:", len(data))
        if len(data) > 0:
            print("Sample point:", data[0])
            # Contar fuentes
            sources = {}
            for p in data:
                src = p.get('fuente', 'unknown')
                sources[src] = sources.get(src, 0) + 1
            print("Sources:", sources)
        else:
            print("No points found")
    else:
        print("heatmapDataJson not found, maybe still using example data")
    # Verificar mensaje de éxito
    if "HEATMAP FUNCIONANDO CORRECTAMENTE" in content:
        print("✅ Heatmap message present")
    else:
        print("⚠️  Heatmap message missing")
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Error:", e.reason)
except Exception as e:
    print("Other error:", e)