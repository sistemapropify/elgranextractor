import re

with open('webapp/market_analysis/templates/market_analysis/heatmap.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Eliminar contenido dentro de {% ... %} y {{ ... }} para simplificar
content_no_django = re.sub(r'\{[%{].*?[%}]\}', '', content, flags=re.DOTALL)

# Contar tags de apertura y cierre
tags = re.findall(r'</?(\w+)[^>]*>', content_no_django)
print(f"Total tags encontrados: {len(tags)}")

# Contar divs
open_div = content_no_django.count('<div')
close_div = content_no_django.count('</div')
print(f"<div>: {open_div}, </div>: {close_div}, diferencia: {open_div - close_div}")

# Contar otros tags importantes
for tag in ['span', 'p', 'ul', 'li', 'script', 'style', 'main', 'header', 'nav']:
    open_tag = content_no_django.count(f'<{tag}')
    close_tag = content_no_django.count(f'</{tag}')
    if open_tag != close_tag:
        print(f"  Desbalance: <{tag}>={open_tag}, </{tag}>={close_tag}")

# Buscar líneas problemáticas (div sin cerrar)
lines = content.split('\n')
for i, line in enumerate(lines):
    if '<div' in line and '</div>' not in line:
        # Verificar si hay cierre en líneas siguientes (simplificado)
        print(f"Línea {i+1}: posible div sin cerrar: {line.strip()[:80]}")

print("\n--- Últimas 10 líneas del template ---")
for line in lines[-10:]:
    print(line.rstrip())