#!/usr/bin/env python
import re

template_path = "templates/propifai/property_visits_dashboard.html"

print(f"Leyendo template: {template_path}")
with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar el bloque DOMContentLoaded con el try-catch
pattern = r'(document\.addEventListener\(\'DOMContentLoaded\', function\(\) \{[\s\S]*?console\.log\(\'DOMContentLoaded ejecutado\'\)[\s\S]*?try \{[\s\S]*?\} catch \(error\) \{[\s\S]*?\}\s*\}\))'
match = re.search(pattern, content)

if match:
    print("=== BLOQUE DOMContentLoaded ENCONTRADO ===")
    block = match.group(1)
    print(block[:500] + "\n...\n" + block[-500:])
    
    # Verificar si hay un div de error
    if 'errorDiv' in block:
        print("\n✓ Ya existe errorDiv en el bloque")
    else:
        print("\n✗ No se encontró errorDiv en el bloque")
        
    # Buscar las funciones que se llaman
    func_calls = re.findall(r'(\w+)\(\)', block)
    print(f"\nFunciones llamadas en el bloque: {set(func_calls)}")
else:
    print("No se encontró el bloque DOMContentLoaded")

# Buscar la función renderTableBatch
print("\n=== BUSCANDO FUNCIÓN renderTableBatch ===")
render_pattern = r'function renderTableBatch\(\) \{[\s\S]*?\n\}'
render_match = re.search(render_pattern, content)
if render_match:
    print("Función renderTableBatch encontrada")
    render_func = render_match.group(0)
    print(render_func[:300] + "\n...")
else:
    print("Función renderTableBatch NO encontrada")

# Buscar la función clearTable
print("\n=== BUSCANDO FUNCIÓN clearTable ===")
clear_pattern = r'function clearTable\(\) \{[\s\S]*?\n\}'
clear_match = re.search(clear_pattern, content)
if clear_match:
    print("Función clearTable encontrada")
    clear_func = clear_match.group(0)
    print(clear_func)
    
    # Verificar si usa getElementById correctamente
    if 'getElementById(\'properties-tbody\')' in clear_func:
        print("✓ clearTable usa getElementById('properties-tbody') correctamente")
    else:
        print("✗ clearTable NO usa getElementById('properties-tbody') correctamente")
else:
    print("Función clearTable NO encontrada")