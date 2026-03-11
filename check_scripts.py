import re

with open('heatmap_debug.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Buscar todas las etiquetas script
scripts = re.findall(r'<script[^>]*>.*?</script>', html, re.DOTALL)
print(f'Total scripts encontrados: {len(scripts)}')

for i, script in enumerate(scripts):
    # Extraer src si existe
    src_match = re.search(r'src="([^"]+)"', script)
    src = src_match.group(1) if src_match else '(inline)'
    print(f'Script {i+1}: {src}')
    if src == '(inline)':
        # Mostrar primeras 100 caracteres del contenido
        content = re.sub(r'<script[^>]*>|</script>', '', script, flags=re.DOTALL)
        preview = content.strip()[:150]
        print(f'  Contenido: {preview}...')
    print()

# Buscar Google Maps API específicamente
if 'maps.googleapis.com' in html:
    print('✓ Google Maps API encontrada en HTML')
else:
    print('✗ Google Maps API NO encontrada en HTML')

# Buscar heatmap.js
if 'heatmap.js' in html:
    print('✓ heatmap.js encontrado en HTML')
else:
    print('✗ heatmap.js NO encontrado en HTML')

# Buscar initHeatmapMap
if 'initHeatmapMap' in html:
    print('✓ initHeatmapMap encontrado en HTML')
else:
    print('✗ initHeatmapMap NO encontrado en HTML')