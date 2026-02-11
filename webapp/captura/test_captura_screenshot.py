"""
Script de prueba para la funcionalidad de captura de screenshot y OCR.
Este script prueba el módulo captura_screenshot.py sin requerir dependencias externas.
"""

import sys
import os
import json
from pathlib import Path

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Prueba las importaciones del módulo captura_screenshot."""
    print("=== Prueba de importaciones ===")
    
    try:
        # Intentar importar directamente desde el archivo
        import sys
        import os
        # Agregar el directorio actual al path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from webapp.captura.captura_screenshot import CapturaScreenshot
        print("[OK] CapturaScreenshot importado correctamente")
    except ImportError as e:
        print(f"[ERROR] Error importando CapturaScreenshot: {e}")
        return False
    
    try:
        from webapp.captura.captura_screenshot import capturar_pagina_completa
        print("[OK] Funcion capturar_pagina_completa importada correctamente")
    except ImportError as e:
        print(f"[ERROR] Error importando capturar_pagina_completa: {e}")
        return False
    
    return True

def test_class_structure():
    """Prueba la estructura de la clase CapturaScreenshot."""
    print("\n=== Prueba de estructura de clase ===")
    
    try:
        from webapp.captura.captura_screenshot import CapturaScreenshot
        
        # Crear instancia
        capturador = CapturaScreenshot(output_dir="test_capturas")
        
        # Verificar atributos
        assert hasattr(capturador, 'driver'), "Falta atributo 'driver'"
        assert hasattr(capturador, 'output_dir'), "Falta atributo 'output_dir'"
        assert hasattr(capturador, 'jpg_quality'), "Falta atributo 'jpg_quality'"
        assert hasattr(capturador, 'ocr_language'), "Falta atributo 'ocr_language'"
        
        print("✓ Estructura de clase correcta")
        print(f"  - output_dir: {capturador.output_dir}")
        print(f"  - jpg_quality: {capturador.jpg_quality}")
        print(f"  - ocr_language: {capturador.ocr_language}")
        
        # Verificar que el directorio se creó
        if capturador.output_dir.exists():
            print(f"✓ Directorio de salida creado: {capturador.output_dir}")
        else:
            print(f"✗ Directorio de salida no creado: {capturador.output_dir}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error en estructura de clase: {e}")
        return False

def test_dependencies():
    """Verifica las dependencias necesarias."""
    print("\n=== Verificación de dependencias ===")
    
    # Lista de dependencias y módulos de prueba
    dependencias = [
        ('selenium', 'from selenium import webdriver'),
        ('PIL', 'from PIL import Image'),
        ('pytesseract', 'import pytesseract'),
        ('cv2', 'import cv2'),
    ]
    
    todas_ok = True
    for nombre, import_stmt in dependencias:
        try:
            exec(import_stmt)
            print(f"✓ {nombre} disponible")
        except ImportError:
            print(f"⚠ {nombre} NO disponible (algunas funciones pueden no trabajar)")
            todas_ok = False
    
    if not todas_ok:
        print("\n⚠ Algunas dependencias faltan. Instalar con:")
        print("  pip install selenium Pillow pytesseract opencv-python")
        print("  Además, necesitarás Tesseract OCR instalado en el sistema:")
        print("  - Windows: Descargar de https://github.com/UB-Mannheim/tesseract/wiki")
        print("  - Linux: sudo apt install tesseract-ocr tesseract-ocr-spa")
        print("  - macOS: brew install tesseract")
    
    return todas_ok

def test_simple_capture_without_driver():
    """Prueba una captura simple sin driver real (solo verifica lógica)."""
    print("\n=== Prueba de lógica de captura (sin driver real) ===")
    
    try:
        from webapp.captura.captura_screenshot import CapturaScreenshot
        
        # Crear capturador con modo de prueba
        capturador = CapturaScreenshot(output_dir="test_capturas")
        
        # Verificar métodos
        metodos_requeridos = [
            'inicializar_driver',
            'cerrar_driver',
            '_hacer_scroll_completo',
            'capturar_screenshot_completo',
            'extraer_texto_ocr',
            'capturar_y_extraer_texto'
        ]
        
        for metodo in metodos_requeridos:
            if hasattr(capturador, metodo):
                print(f"✓ Método '{metodo}' presente")
            else:
                print(f"✗ Método '{metodo}' faltante")
                return False
        
        # Probar contexto manager
        with CapturaScreenshot(output_dir="test_capturas") as capturador_ctx:
            print("✓ Context manager funciona correctamente")
            assert capturador_ctx is not None
        
        print("✓ Todas las pruebas de lógica pasaron")
        return True
        
    except Exception as e:
        print(f"✗ Error en prueba de lógica: {e}")
        return False

def generate_usage_example():
    """Genera un ejemplo de uso del módulo."""
    print("\n=== Ejemplo de uso ===")
    
    ejemplo = '''
# Ejemplo 1: Captura simple con función de conveniencia
from webapp.captura.captura_screenshot import capturar_pagina_completa

resultado = capturar_pagina_completa("https://example.com")
if resultado['exito']:
    print(f"Captura exitosa: {resultado['captura']['ruta_imagen']}")
    print(f"Texto extraído: {len(resultado['texto_completo'])} caracteres")
else:
    print(f"Error: {resultado['error']}")

# Ejemplo 2: Uso avanzado con clase
from webapp.captura.captura_screenshot import CapturaScreenshot

with CapturaScreenshot(output_dir="mis_capturas", jpg_quality=90) as capturador:
    # Capturar screenshot sin OCR
    resultado_captura = capturador.capturar_screenshot_completo("https://example.com")
    
    if resultado_captura['exito']:
        # Extraer texto con OCR después
        resultado_ocr = capturador.extraer_texto_ocr(resultado_captura['ruta_imagen'])
        
        if resultado_ocr['exito']:
            print(f"Texto extraído: {resultado_ocr['texto'][:200]}...")

# Ejemplo 3: Desde línea de comandos
# python -m webapp.captura.captura_screenshot https://example.com
'''
    
    print(ejemplo)
    return True

def create_requirements_file():
    """Crea un archivo requirements.txt con las dependencias necesarias."""
    print("\n=== Creando archivo de dependencias ===")
    
    requirements_content = """# Dependencias para captura de screenshot y OCR
selenium>=4.0.0
Pillow>=10.0.0
pytesseract>=0.3.10
opencv-python>=4.8.0
webdriver-manager>=4.0.0  # Para manejo automático de drivers

# Dependencias opcionales pero recomendadas
numpy>=1.24.0  # Para procesamiento de imágenes
scikit-image>=0.22.0  # Para mejor preprocesamiento de OCR

# Nota: También necesitas Tesseract OCR instalado en el sistema
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
# macOS: brew install tesseract tesseract-lang
"""
    
    try:
        with open("requirements_screenshot.txt", "w", encoding="utf-8") as f:
            f.write(requirements_content)
        
        print("✓ Archivo requirements_screenshot.txt creado")
        print("  Contenido:")
        print(requirements_content[:200] + "...")
        return True
    except Exception as e:
        print(f"✗ Error creando archivo de dependencias: {e}")
        return False

def main():
    """Función principal de pruebas."""
    print("=" * 60)
    print("PRUEBA DEL MÓDULO DE CAPTURA DE SCREENSHOT Y OCR")
    print("=" * 60)
    
    resultados = []
    
    # Ejecutar pruebas
    resultados.append(("Importaciones", test_imports()))
    resultados.append(("Estructura de clase", test_class_structure()))
    resultados.append(("Dependencias", test_dependencies()))
    resultados.append(("Lógica de captura", test_simple_capture_without_driver()))
    resultados.append(("Ejemplo de uso", generate_usage_example()))
    resultados.append(("Archivo de dependencias", create_requirements_file()))
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    exit_code = 0
    for nombre, resultado in resultados:
        estado = "✓ PASÓ" if resultado else "✗ FALLÓ"
        print(f"{nombre:30} {estado}")
        if not resultado:
            exit_code = 1
    
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("¡TODAS LAS PRUEBAS PASARON!")
        print("\nPara usar el módulo, instala las dependencias faltantes:")
        print("pip install -r requirements_screenshot.txt")
        print("\nY asegúrate de tener Tesseract OCR instalado en el sistema.")
    else:
        print("ALGUNAS PRUEBAS FALLARON")
        print("\nRevisa los mensajes de error arriba.")
    
    print("\nArchivos creados:")
    print("  - webapp/captura/captura_screenshot.py (módulo principal)")
    print("  - webapp/captura/test_captura_screenshot.py (este script de prueba)")
    print("  - requirements_screenshot.txt (dependencias)")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())