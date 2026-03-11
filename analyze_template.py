import re

with open('webapp/market_analysis/templates/market_analysis/heatmap.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar todos los bloques Django
print("=== BLOQUES DJANGO EN TEMPLATE ===")
for match in re.finditer(r'(\{%[^%]+%\})', content):
    print(f"Línea ~{content[:match.start()].count(chr(10))+1}: {match.group(0)}")

# Contar bloques abiertos/cerrados
blocks = re.findall(r'\{%\s*(block|endblock|if|endif|for|endfor)\s*[^%]*%\}', content)
print(f"\n=== CONTEO DE BLOQUES ===")
print(f"Total: {len(blocks)}")
for block in ['block', 'endblock', 'if', 'endif', 'for', 'endfor']:
    count = sum(1 for b in blocks if b == block)
    print(f"{block}: {count}")

# Verificar balance
block_stack = []
for match in re.finditer(r'\{%\s*(block|endblock|if|endif|for|endfor)\s*([^%]*)?%\}', content):
    tag = match.group(1)
    if tag in ['block', 'if', 'for']:
        block_stack.append(tag)
    elif tag in ['endblock', 'endif', 'endfor']:
        if block_stack:
            block_stack.pop()
        else:
            print(f"ERROR: {tag} sin abrir en posición {match.start()}")

print(f"\nBloques sin cerrar: {block_stack}")

# Buscar el contenido después del último </div> antes de {% endblock %}
last_div = content.rfind('</div>')
endblock = content.rfind('{% endblock %}')
print(f"\n=== POSICIONES CLAVE ===")
print(f"Último </div>: {last_div}")
print(f"Último {{% endblock %}}: {endblock}")
print(f"Contenido entre ellos: {endblock - last_div} caracteres")

if endblock > last_div:
    between = content[last_div:endblock]
    print(f"\n=== CONTENIDO ENTRE ÚLTIMO DIV Y ENDBLOCK ===")
    print(between[:500] + "..." if len(between) > 500 else between)