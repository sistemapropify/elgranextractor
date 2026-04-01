import urllib.request
import re
import json

url = 'http://localhost:8000/propifai/dashboard/visitas/'
try:
    html = urllib.request.urlopen(url).read().decode('utf-8')
except Exception as e:
    print(f'Error al obtener la página: {e}')
    exit(1)

# Buscar el JSON
match = re.search(r'propertiesData\s*=\s*(\[.*?\]);', html, re.DOTALL)
if not match:
    print('No se encontró propertiesData en el HTML')
    # Imprimir un fragmento del HTML para debug
    print('Fragmento HTML (primeros 2000 caracteres):')
    print(html[:2000])
    exit(1)

json_str = match.group(1)
print(f'JSON encontrado, longitud: {len(json_str)} caracteres')

try:
    data = json.loads(json_str)
except json.JSONDecodeError as e:
    print(f'Error decodificando JSON: {e}')
    print('JSON string (primeros 500 caracteres):')
    print(json_str[:500])
    exit(1)

print(f'Número de propiedades: {len(data)}')
if len(data) == 0:
    print('No hay propiedades en los datos. Esto puede deberse a:')
    print('1. No hay propiedades en la base de datos')
    print('2. La consulta de la vista no está devolviendo resultados')
    print('3. Hay un error en la serialización')
else:
    print('\nPrimera propiedad:')
    for key, value in data[0].items():
        print(f'  {key}: {value}')
    
    # Contar propiedades con eventos
    with_events = sum(1 for p in data if p.get('total_eventos', 0) > 0)
    print(f'\nPropiedades con eventos: {with_events} de {len(data)}')
    
    # Mostrar propiedades con eventos
    if with_events > 0:
        print('\nPropiedades con eventos:')
        for prop in data[:5]:
            if prop.get('total_eventos', 0) > 0:
                print(f'  {prop["code"]}: {prop["total_eventos"]} eventos')