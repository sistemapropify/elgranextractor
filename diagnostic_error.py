import urllib.request
import urllib.error

url = "http://localhost:8000/market-analysis/heatmap/"

try:
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
    content = response.read().decode('utf-8')
    print("Content length:", len(content))
    # Mostrar primeros 2000 caracteres
    print("\n=== CONTENT ===")
    print(content[:2000])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    content = e.read().decode('utf-8')
    print("Error content length:", len(content))
    print("\n=== ERROR CONTENT ===")
    print(content[:3000])
except Exception as e:
    print("Other error:", e)