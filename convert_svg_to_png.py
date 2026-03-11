#!/usr/bin/env python3
"""
Script para convertir SVG a PNG usando svglib y reportlab.
"""
import os
import sys
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM

def convert_svg_to_png(svg_path, png_path, width=40, height=40):
    """Convierte un archivo SVG a PNG con las dimensiones especificadas."""
    try:
        # Convertir SVG a ReportLab Drawing
        drawing = svg2rlg(svg_path)
        
        # Escalar al tamaño deseado
        scale_x = width / drawing.width
        scale_y = height / drawing.height
        drawing.scale(scale_x, scale_y)
        drawing.width = width
        drawing.height = height
        
        # Renderizar a PNG
        renderPM.drawToFile(drawing, png_path, fmt='PNG')
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
    success = convert_svg_to_png(svg_file, png_file, width=40, height=40)
    
    if success:
        print(f"\nPNG creado en: {png_file}")
        print("Ahora actualiza el template para usar la URL PNG:")
        print("  const iconUrl = '/static/requerimientos/data/Pin-propify.png';")
    else:
        print("\nFallo la conversión. Intentando método alternativo...")
        # Método alternativo: usar cairosvg si está disponible
        try:
            import cairosvg
            cairosvg.svg2png(url=svg_file, write_to=png_file, output_width=40, output_height=40)
            print(f"✓ Convertido con cairosvg: {png_file}")
        except ImportError:
            print("✗ cairosvg no está instalado. Instala con: pip install cairosvg")
            print("\nSugerencia: Usa una herramienta online para convertir SVG a PNG")
            print("y guarda el archivo manualmente en:", png_file)