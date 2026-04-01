#!/usr/bin/env python
"""
Script para verificar si matplotlib y seaborn están instalados correctamente.
"""

import sys
import subprocess

print("=== Verificación de dependencias para el dashboard de calidad de datos ===\n")

# Verificar Python
print("1. Versión de Python:")
print(f"   Python {sys.version}\n")

# Verificar matplotlib
print("2. Verificando matplotlib...")
try:
    import matplotlib
    print(f"   ✓ matplotlib {matplotlib.__version__} instalado")
    
    # Verificar backend
    import matplotlib.pyplot as plt
    backend = matplotlib.get_backend()
    print(f"   ✓ Backend: {backend}")
    
    # Verificar si puede crear una figura
    import io
    import base64
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.plot([1, 2, 3], [1, 4, 2])
    ax.set_title('Prueba')
    plt.tight_layout()
    
    # Guardar a buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)
    
    print(f"   ✓ Puede generar gráficos PNG (tamaño base64: {len(img_str)} bytes)")
    
except ImportError as e:
    print(f"   ✗ matplotlib NO está instalado: {e}")
except Exception as e:
    print(f"   ⚠ Error con matplotlib: {e}")

# Verificar seaborn
print("\n3. Verificando seaborn...")
try:
    import seaborn as sns
    print(f"   ✓ seaborn {sns.__version__} instalado")
    
    # Verificar estilos
    available_styles = plt.style.available
    print(f"   ✓ Estilos disponibles: {len(available_styles)}")
    
except ImportError as e:
    print(f"   ✗ seaborn NO está instalado: {e}")
except Exception as e:
    print(f"   ⚠ Error con seaborn: {e}")

# Verificar otras dependencias
print("\n4. Otras dependencias:")
try:
    import numpy as np
    print(f"   ✓ numpy {np.__version__} instalado")
except ImportError:
    print("   ✗ numpy NO está instalado")

try:
    import pandas as pd
    print(f"   ✓ pandas {pd.__version__} instalado")
except ImportError:
    print("   ✗ pandas NO está instalado")

# Verificar desde línea de comandos
print("\n5. Verificación con pip:")
try:
    result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                          capture_output=True, text=True, timeout=5)
    packages = result.stdout.lower()
    
    if 'matplotlib' in packages:
        print("   ✓ matplotlib encontrado en pip list")
    else:
        print("   ✗ matplotlib NO encontrado en pip list")
        
    if 'seaborn' in packages:
        print("   ✓ seaborn encontrado en pip list")
    else:
        print("   ✗ seaborn NO encontrado en pip list")
        
except Exception as e:
    print(f"   ⚠ Error al ejecutar pip: {e}")

# Recomendaciones
print("\n=== Recomendaciones ===")
print("Si matplotlib o seaborn no están instalados:")
print("1. Ejecute: pip install matplotlib seaborn")
print("2. Reinicie el servidor Django")
print("3. Actualice la página del dashboard")

print("\nSi están instalados pero no funcionan:")
print("1. Verifique que estén en el PATH de Python correcto")
print("2. Intente importarlos en la consola de Django: python manage.py shell")
print("3. Revise los logs del servidor para errores de importación")

print("\n=== Fin de la verificación ===")