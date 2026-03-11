import re

with open('webapp/market_analysis/templates/market_analysis/heatmap.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar todos los bloques
blocks = re.findall(r'\{%\s*(block|endblock)\s*[^%]*%\}', content)
print(f"Total bloques encontrados: {len(blocks)}")
for i, block in enumerate(blocks):
    print(f"  {i+1}: {block}")

# Contar
block_count = blocks.count('block')
endblock_count = blocks.count('endblock')
print(f"\nblock: {block_count}, endblock: {endblock_count}")

if block_count == endblock_count:
    print("OK: Bloques balanceados")
else:
    print("ERROR: Bloques desbalanceados")
    
# Mostrar líneas con bloques
lines = content.split('\n')
for i, line in enumerate(lines):
    if '{% block' in line or '{% endblock' in line:
        print(f"Línea {i+1}: {line.strip()}")