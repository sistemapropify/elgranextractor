import urllib.request
import re
import sys

try:
    resp = urllib.request.urlopen('http://127.0.0.1:8001/market-analysis/heatmap/', timeout=5)
    html = resp.read().decode('utf-8')
    
    # Buscar el radio
    match = re.search(r'Radio del heatmap.*?(\d+)px', html, re.DOTALL)
    if match:
        print(f'Radio encontrado: {match.group(1)}px')
    else:
        print('No se encontró el radio')
    
    # Buscar el slider
    slider_match = re.search(r'id="radiusSlider".*?min="(\d+)".*?max="(\d+)".*?value="(\d+)"', html, re.DOTALL)
    if slider_match:
        print(f'Slider: min={slider_match.group(1)}, max={slider_match.group(2)}, value={slider_match.group(3)}')
    else:
        print('No se encontró el slider')
        
    # Mostrar fragmento alrededor de "Radio del heatmap"
    pos = html.find('Radio del heatmap')
    if pos != -1:
        fragment = html[pos:pos+300]
        print(f'\nFragmento HTML:\n{fragment}')
    else:
        print('Texto "Radio del heatmap" no encontrado en el HTML')
        
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)