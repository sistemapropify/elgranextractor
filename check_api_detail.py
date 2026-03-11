import urllib.request
import json

url = "http://localhost:8000/market-analysis/api/heatmap-data/?debug=real"
try:
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    print("Total properties:", len(data['properties']))
    # Agrupar por fuente
    sources = {}
    for prop in data['properties']:
        source = prop.get('fuente', 'unknown')
        sources[source] = sources.get(source, 0) + 1
    print("Sources:", sources)
    # Mostrar algunas propiedades
    for i, prop in enumerate(data['properties'][:3]):
        print(f"Property {i}: lat={prop['lat']}, lng={prop['lng']}, precio_m2={prop['precio_m2']}, fuente={prop['fuente']}, tipo={prop.get('tipo_propiedad')}")
except Exception as e:
    print("Error:", e)