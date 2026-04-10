#!/usr/bin/env python3
"""
Script para corregir la altura del gráfico en dashboard.html
"""

import re

def fix_chart_height():
    file_path = 'webapp/eventos/templates/eventos/dashboard.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patrón para encontrar el div col-md-12 que contiene el canvas
    pattern = r'(<div class="col-md-12">\s*<canvas id="evolucionTiposChart" height="300"></canvas>)'
    
    # Reemplazo
    replacement = r'<div class="col-md-12" style="position: relative; height: 350px;">\n                            <canvas id="evolucionTiposChart"></canvas>'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Archivo modificado exitosamente.")
    else:
        print("No se encontró el patrón. Intentando otro patrón...")
        # Segundo intento con más contexto
        pattern2 = r'(<div class="col-md-12">\s*<canvas id="evolucionTiposChart" height="300">\s*</canvas>)'
        new_content = re.sub(pattern2, replacement, content)
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Archivo modificado con segundo patrón.")
        else:
            print("No se pudo modificar el archivo.")

if __name__ == '__main__':
    fix_chart_height()