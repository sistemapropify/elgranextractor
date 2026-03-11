import requests
import re

r = requests.get('http://localhost:8000/ingestas/propiedades/')
html = r.text

# Buscar el script que contiene ICONO_PROPIFFY
pattern = r'const ICONO_PROPIFFY = \'([^\']+)\';'
match = re.search(pattern, html)
if match:
    print('ICONO_PROPIFFY:', match.group(1))
else:
    print('ICONO_PROPIFFY not found')
    # Buscar más ampliamente
    pattern2 = r'ICONO_PROPIFFY.*?=.*?[\'"]([^\'"]+)[\'"]'
    match2 = re.search(pattern2, html, re.DOTALL)
    if match2:
        print('Found alternative:', match2.group(1))

# Verificar también ICONO_REMAX
pattern3 = r'const ICONO_REMAX = \'([^\']+)\';'
match3 = re.search(pattern3, html)
if match3:
    print('ICONO_REMAX:', match3.group(1))
else:
    print('ICONO_REMAX not found')

# Verificar que el archivo exista en el sistema de archivos
import os
static_path = 'webapp/static/requerimientos/data'
print('\nChecking static files:')
print('Pin-propify.png exists?', os.path.exists(os.path.join(static_path, 'Pin-propify.png')))
print('pin-remax.png exists?', os.path.exists(os.path.join(static_path, 'pin-remax.png')))