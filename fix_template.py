#!/usr/bin/env python
"""
Script para arreglar el template y asegurar que las propiedades Propify se muestren.
"""
import os

template_path = 'webapp/templates/ingestas/lista_propiedades_rediseno.html'

print(f"Leyendo template: {template_path}")

with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar la línea con el contador
target_line = '<span class="properties-count">{{ total_propiedades }} propiedades ({{ conteo_locales }} locales + {{ conteo_externas }} externas + {{ conteo_propify }} propify)</span>'

if target_line in content:
    print("✓ Encontrada la línea del contador")
    
    # Reemplazar con versión mejorada
    new_line = '''<span class="properties-count">{{ total_propiedades }} propiedades ({{ conteo_locales }} locales + {{ conteo_externas }} externas + {{ conteo_propify }} propify)</span>
                {% if conteo_propify and conteo_propify > 0 %}
                <div class="alert alert-success alert-dismissible fade show mt-2" style="padding: 5px 10px; font-size: 0.9rem; margin-top: 5px !important;">
                    <i class="fas fa-check-circle"></i> <strong>✓ PROPIFY FUNCIONANDO:</strong> Se encontraron {{ conteo_propify }} propiedades de la base de datos Propify.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close" style="padding: 5px; font-size: 0.7rem;"></button>
                </div>
                {% endif %}'''
    
    content = content.replace(target_line, new_line)
    print("✓ Línea reemplazada")
    
    # También vamos a agregar un comentario de debug en cada propiedad Propify
    # Buscar la sección donde se muestra el badge Propify
    propify_badge_section = '{% if propiedad.es_propify %}\n                                        <span class="badge bg-success text-white ms-1" style="font-size: 0.6rem; padding: 0.1rem 0.3rem;">Propify</span>'
    
    if propify_badge_section in content:
        # Agregar un comentario antes del badge
        enhanced_badge = '''{% if propiedad.es_propify %}
                                        <!-- PROPIEDAD PROPIY ID: {{ propiedad.id|default:propiedad.id_externo }} -->
                                        <span class="badge bg-success text-white ms-1" style="font-size: 0.6rem; padding: 0.1rem 0.3rem;">Propify ✓</span>'''
        
        content = content.replace(propify_badge_section, enhanced_badge)
        print("✓ Badge Propify mejorado")
    
    # Guardar los cambios
    backup_path = template_path + '.backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Backup guardado en: {backup_path}")
    
    # Ahora escribir el archivo original
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ Template actualizado correctamente")
    
    # Verificar que los cambios se aplicaron
    with open(template_path, 'r', encoding='utf-8') as f:
        new_content = f.read()
    
    if 'PROPIFY FUNCIONANDO' in new_content:
        print("✓ Cambios verificados: 'PROPIFY FUNCIONANDO' encontrado en el template")
    else:
        print("✗ Error: Cambios no aplicados correctamente")
        
else:
    print("✗ No se encontró la línea del contador")
    
print("\n=== SCRIPT COMPLETADO ===")