import requests
import re

url = "http://127.0.0.1:8000/propifai/dashboard/calidad/"
response = requests.get(url)
html = response.text

# Buscar todas las ocurrencias de PROP seguido de 6 dígitos en el HTML
codes = re.findall(r'PROP\d{6}', html)
print(f"Total códigos encontrados: {len(codes)}")
print("Primeros 10 códigos:")
for i, code in enumerate(codes[:10]):
    print(f"{i}: {code}")

print("\nÚltimos 10 códigos:")
for i, code in enumerate(codes[-10:]):
    print(f"{i+len(codes)-10}: {code}")

# Verificar si están ordenados por fecha (no podemos saberlo solo con códigos)
# Pero podemos asumir que PROP000001 es antiguo y PROP000097 es reciente
if codes and codes[0] == 'PROP000097':
    print("\n¡ÉXITO! La primera propiedad es la más reciente (PROP000097).")
elif codes and codes[0] == 'PROP000001':
    print("\n¡PROBLEMA! La primera propiedad es la más antigua (PROP000001).")
else:
    print(f"\nPrimera propiedad: {codes[0]}")