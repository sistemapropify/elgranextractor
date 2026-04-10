#!/usr/bin/env python3
"""
Script para corregir la altura del gráfico en dashboard.html
"""

import re

def fix_chart_height():
    file_path = 'webapp/eventos/templates/eventos/dashboard.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Buscar la línea que contiene 'col-md-12' y '\\n'
    for i, line in enumerate(lines):
        if 'col-md-12' in line and '\\n' in line:
            print(f"Encontrada línea {i+1}: {line}")
            # Reemplazar la línea con una versión corregida
            # Eliminar el '\\n' y dividir en dos líneas
            if '\\n' in line:
                # Separar antes y después de \\n
                before, after = line.split('\\n')
                # Asegurar que after tenga la indentación correcta
                # La indentación es la misma que before más 4 espacios?
                # Simplemente creamos dos líneas
                lines[i] = before.rstrip() + '\n'
                # Insertar after en la siguiente línea
                lines.insert(i+1, after)
                print("Línea corregida.")
                break
    
    # También corregir encoding de caracteres acentuados (opcional)
    # Escribir de vuelta
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Archivo guardado.")

if __name__ == '__main__':
    fix_chart_height()