#!/usr/bin/env python
"""
Script simple para arreglar el template.
"""
import os

template_path = 'webapp/templates/ingestas/lista_propiedades_rediseno.html'

print("Leyendo template...")

with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar la línea con el contador
target_line = '<span class="properties-count">{{ total_propiedades }} propiedades ({{ conteo_locales }} locales + {{ conteo_externas }} externas + {{ conteo_propify }} propify)</span>'

if target_line in content:
    print("OK: Encontrada la línea del contador")
    
    # Reemplazar con versión mejorada
    new_line = '''<span class="properties-count">{{ total_propiedades }} propiedades ({{ conteo_locales }} locales + {{ conteo_externas }} externas + {{ conteo_propify }} propify)</span>
                {% if conteo_propify and conteo_propify > 0 %}
                <div class="alert alert-success alert-dismissible fade show mt-2" style="padding: 5px 10px; font-size: 0.9rem; margin-top: 5px !important;">
                    <i class="fas fa-check-circle"></i> <strong>PROPIFY FUNCIONANDO:</strong> Se encontraron {{ conteo_propify }} propiedades de la base de datos Propify.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close" style="padding: 5px; font-size: 0.7rem;"></button>
                </div>
                {% endif %}'''
    
    content = content.replace(target_line, new_line)
    print("OK: Línea reemplazada")
    
    # Guardar backup
    backup_path = template_path + '.backup2'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"OK: Backup guardado en: {backup_path}")
    
    # Escribir el archivo original
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("OK: Template actualizado correctamente")
    
else:
    print("ERROR: No se encontró la línea del contador")
    
print("\nSCRIPT COMPLETADO")