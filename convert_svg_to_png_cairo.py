#!/usr/bin/env python3
"""
Convierte SVG a PNG usando cairosvg.
"""
import os
import sys
import cairosvg

def convert_svg_to_png(svg_path, png_path, width=80, height=114):
    """Convierte SVG a PNG con cairosvg."""
    try:
        # Convertir SVG a PNG
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=width, output_height=height)
        print(f"✓ Convertido: {svg_path} -> {png_path} ({width}x{height}px)")
        return True
    except Exception as e:
        print(f"✗ Error al convertir {svg_path}: {e}")
        return False

if __name__ == "__main__":
    # Rutas
    svg_file = "webapp/static/requerimientos/data/Pin-propify.svg"
    png_file = "webapp/static/requerimientos/data/Pin-propify.png"
    
    # Verificar si el archivo SVG existe
    if not os.path.exists(svg_file):
        print(f"✗ Archivo SVG no encontrado: {svg_file}")
        sys.exit(1)
    
    # Convertir
    success = convert_svg_to_png(svg_file, png_file, width=80, height=114)
    
    if success:
        print(f"\nPNG creado en: {png_file}")
        print("Tamaño del archivo:", os.path.getsize(png_file), "bytes")
        print("\nAhora actualiza el template para usar la URL PNG:")
        print("  const iconUrl = '/static/requerimientos/data/Pin-propify.png';")
    else:
        print("\nFallo la conversión.")