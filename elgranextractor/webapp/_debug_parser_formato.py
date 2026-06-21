"""
Debug: probar el parser con el archivo real de EXITO INMOBILIARIO AGENTES.
"""
import re
import os
import sys

# Agregar webapp al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# Ruta al archivo
ruta = r"d:\proyectos\prometeo\webapp\media\whatsapp_extracciones\6a7bbb117912404ca72237e8552ea550_Chat de WhatsApp de EXITO INMOBILIARIO AGENTES.txt"

with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
    contenido = f.read()

lineas = contenido.split('\n')
print(f"Total líneas: {len(lineas)}")
print(f"Total caracteres: {len(contenido)}")
print()

# Mostrar primeras 15 líneas NO VACÍAS con representación exacta
count = 0
for i, linea in enumerate(lineas):
    stripped = linea.rstrip('\n\r')
    if stripped:
        # Mostrar los primeros 100 caracteres con escapes
        muestra = repr(stripped[:120])
        print(f"L{i:5d}: {muestra}")
        count += 1
        if count >= 15:
            break

print("\n\n=== PROBAR REGEX PATRON_FORMATO_3 ===")
patron3 = re.compile(
    r'^\[(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:[\s\u202f]*[aApP][\.\s\u202f]*[mM][\.\s\u202f]*)?)\]\s*([^:]+):\s*(.*)',
    re.UNICODE
)

# Probar con primeras 20 líneas con timestamp
count = 0
for i, linea in enumerate(lineas):
    stripped = linea.rstrip('\n\r')
    if not stripped:
        continue
    m = patron3.match(stripped)
    if m:
        print(f"\nL{i}: MATCH!")
        print(f"  timestamp: {m.group(1)!r}")
        print(f"  autor: {m.group(2)!r}")
        print(f"  texto: {m.group(3)[:80]!r}...")
        count += 1
        if count >= 5:
            break
    else:
        # Ver si parece un timestamp
        if stripped.startswith('[') and ']' in stripped[:50]:
            print(f"\nL{i}: NO MATCH pero parece timestamp!")
            print(f"  linea: {repr(stripped[:100])}")
            # Mostrar bytes del inicio
            print(f"  bytes: {stripped[:30].encode('utf-8')}")
            count += 1
            if count >= 5:
                break
