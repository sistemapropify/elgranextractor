#!/usr/bin/env python3
"""
Crea un data URL base64 para el SVG y genera el código JavaScript.
"""
import base64
import os

def create_svg_data_url(svg_path):
    """Lee un archivo SVG y lo convierte a data URL base64."""
    with open(svg_path, 'rb') as f:
        svg_content = f.read()
    
    # Codificar a base64
    svg_base64 = base64.b64encode(svg_content).decode('utf-8')
    data_url = f"data:image/svg+xml;base64,{svg_base64}"
    return data_url

def main():
    svg_file = "webapp/static/requerimientos/data/Pin-propify.svg"
    
    if not os.path.exists(svg_file):
        print(f"✗ Archivo SVG no encontrado: {svg_file}")
        return
    
    data_url = create_svg_data_url(svg_file)
    
    print("Data URL generado (primeros 100 caracteres):")
    print(data_url[:100] + "...")
    print("\nCódigo JavaScript para usar en el template:")
    print("=" * 80)
    print(f"""    // Icono personalizado para Propify - data URL SVG
    const iconUrl = '{data_url}';

    const marker = new google.maps.Marker({{
        position: {{ lat: lat, lng: lng }},
        map: map,
        title: description,
        icon: {{
            url: iconUrl,
            scaledSize: new google.maps.Size(40, 40),
            anchor: new google.maps.Point(20, 40)
        }}
    }});""")
    print("=" * 80)
    
    # También crear un archivo con el data URL para referencia
    output_file = "svg_data_url.txt"
    with open(output_file, 'w') as f:
        f.write(data_url)
    print(f"\nData URL completo guardado en: {output_file}")

if __name__ == "__main__":
    main()