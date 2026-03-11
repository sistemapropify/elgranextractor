#!/usr/bin/env python3
"""
Crea un data URL base64 para el PNG.
"""
import base64
import os

def create_png_data_url(png_path):
    """Lee un archivo PNG y lo convierte a data URL base64."""
    with open(png_path, 'rb') as f:
        png_content = f.read()
    
    # Codificar a base64
    png_base64 = base64.b64encode(png_content).decode('utf-8')
    data_url = f"data:image/png;base64,{png_base64}"
    return data_url

def main():
    png_file = "webapp/static/requerimientos/data/Pin-propify.png"
    
    if not os.path.exists(png_file):
        print(f"✗ Archivo PNG no encontrado: {png_file}")
        return
    
    data_url = create_png_data_url(png_file)
    
    print("Data URL generado (primeros 100 caracteres):")
    print(data_url[:100] + "...")
    print("\nCódigo JavaScript para usar en el template:")
    print("=" * 80)
    print(f"""    // Icono personalizado para Propify - data URL PNG
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
    
    # Guardar data URL en archivo
    output_file = "png_data_url.txt"
    with open(output_file, 'w') as f:
        f.write(data_url)
    print(f"\nData URL completo guardado en: {output_file}")

if __name__ == "__main__":
    main()