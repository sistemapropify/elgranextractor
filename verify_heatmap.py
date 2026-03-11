import urllib.request
import urllib.error

url = "http://localhost:8000/market-analysis/heatmap/"

try:
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
    content = response.read().decode('utf-8')
    print("Content length:", len(content))
    # Verificar si contiene el mensaje esperado
    if "HEATMAP FUNCIONANDO CORRECTAMENTE" in content:
        print("✅ Heatmap funciona correctamente (mensaje encontrado)")
    else:
        print("⚠️  Mensaje no encontrado, pero la página carga")
    # Verificar Google Maps API
    if "maps.googleapis.com" in content:
        print("✅ Google Maps API incluida")
    else:
        print("⚠️  Google Maps API no encontrada")
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Error:", e.reason)
except Exception as e:
    print("Other error:", e)