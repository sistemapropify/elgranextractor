#!/usr/bin/env python3
"""
Script simple para inspeccionar datos de la gráfica usando manage.py shell.
"""

import subprocess
import sys
import os

# Comando para ejecutar en shell de Django
script = """
import json
from eventos.models import Event
from eventos.views import calcular_evolucion_semanal_tipos_eventos

# Obtener todos los eventos
eventos_list = Event.objects.all().order_by('-fecha_evento', '-hora_inicio')
total_eventos = eventos_list.count()
print(f"Total de eventos en BD: {total_eventos}")

# Calcular datos del gráfico
datos_grafico = calcular_evolucion_semanal_tipos_eventos(eventos_list)

# Analizar estructura
print(f"\\nEstructura del gráfico:")
print(f"- Número de semanas: {len(datos_grafico['semanas'])}")
print(f"- Semanas: {datos_grafico['semanas']}")
print(f"- Número de tipos de eventos: {len(datos_grafico['tipos'])}")
print(f"- Tipos: {list(datos_grafico['tipos'].values())}")

# Analizar valores del eje Y
print(f"\\nAnálisis de valores del eje Y (conteos por tipo):")
max_valor = 0
min_valor = float('inf')

for tipo_id, valores in datos_grafico['datos'].items():
    tipo_nombre = datos_grafico['tipos'][tipo_id]
    max_tipo = max(valores) if valores else 0
    min_tipo = min(valores) if valores else 0
    
    print(f"\\n  Tipo: {tipo_nombre} (ID: {tipo_id})")
    print(f"    Valores: {valores}")
    print(f"    Máximo: {max_tipo}, Mínimo: {min_tipo}")
    
    max_valor = max(max_valor, max_tipo)
    min_valor = min(min_valor, min_tipo)

print(f"\\nResumen global:")
print(f"  Valor máximo en todos los tipos: {max_valor}")
print(f"  Valor mínimo en todos los tipos: {min_valor}")

# Verificar si hay valores extremos
print(f"\\nAnálisis de valores extremos:")
if max_valor > 100:
    print(f"  ⚠️  VALOR EXTREMO DETECTADO: {max_valor} eventos en una semana")
    print(f"     Esto podría causar expansión del eje Y.")
elif max_valor > 50:
    print(f"  ⚠️  Valor alto: {max_valor} eventos en una semana")
else:
    print(f"  ✅ Valores normales: máximo {max_valor} eventos")

# Mostrar algunos datos de ejemplo
print(f"\\nDatos de ejemplo (primer tipo):")
if datos_grafico['datos']:
    first_key = list(datos_grafico['datos'].keys())[0]
    print(f"  Tipo ID: {first_key}")
    print(f"  Nombre: {datos_grafico['tipos'][first_key]}")
    print(f"  Valores: {datos_grafico['datos'][first_key]}")
    print(f"  Color: {datos_grafico['colores'].get(first_key, 'No definido')}")
"""

# Guardar script temporal
with open('temp_script.py', 'w', encoding='utf-8') as f:
    f.write(script)

# Ejecutar usando manage.py shell
print("Ejecutando análisis de datos de gráfica...")
try:
    result = subprocess.run(
        ['cd', 'webapp', '&&', 'C:\\Users\\USUARIO\\AppData\\Local\\Python\\bin\\python.exe', 'manage.py', 'shell', '-c', script],
        shell=True,
        capture_output=True,
        text=True,
        cwd='d:/proyectos/prometeo'
    )
    
    print("Salida del comando:")
    print(result.stdout)
    if result.stderr:
        print("Errores:")
        print(result.stderr)
        
except Exception as e:
    print(f"Error ejecutando comando: {e}")

# Limpiar
if os.path.exists('temp_script.py'):
    os.remove('temp_script.py')