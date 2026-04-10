import urllib.request
import sys
import re

try:
    response = urllib.request.urlopen('http://127.0.0.1:8000/analisis-crm/')
    html = response.read().decode('utf-8')
    
    # Verificar que la página carga
    if response.status == 200:
        print('Status: 200 - Page loaded successfully')
    else:
        print(f'Status: {response.status}')
        sys.exit(1)
    
    # Buscar la columna "Estado Lead" en la tabla
    if 'Estado Lead' in html:
        print('[OK] Columna "Estado Lead" encontrada en el HTML')
    else:
        print('[FAIL] Columna "Estado Lead" NO encontrada en el HTML')
        
    # Buscar algún nombre de estado (ejemplo: "Nuevo", "No interesado")
    if 'Nuevo' in html or 'No interesado' in html or 'Interesado' in html:
        print('[OK] Nombres de estados detectados')
    else:
        print('[WARN] No se detectaron nombres de estados (puede que no haya leads con estado)')
        
    # Verificar que no hay errores de template
    if 'Error' in html and 'Traceback' in html:
        print('[FAIL] Se detectó un error en el template')
        sys.exit(1)
    else:
        print('[OK] Sin errores de template aparentes')
        
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)