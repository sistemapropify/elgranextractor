#!/usr/bin/env python3
"""
Limpia el archivo dashboard.html de caracteres extraños y ajusta estilos.
"""

import re

def cleanup():
    file_path = 'webapp/eventos/templates/eventos/dashboard.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Reemplazar cualquier ocurrencia de '\\n' (backslash + n) con un salto de línea real
    # pero solo si está dentro de un atributo style o similar? Mejor reemplazar globalmente.
    # Usar replace simple
    content = content.replace('\\n', '\n')
    
    # También corregir encoding de caracteres acentuados (opcional)
    # Escribir de vuelta
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Archivo limpiado.")

if __name__ == '__main__':
    cleanup()