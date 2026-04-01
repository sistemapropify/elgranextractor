#!/usr/bin/env python
"""
Script para verificar automáticamente propiedades y marcar 'propiedad_verificada'
si cumplen los criterios para el análisis del ACM (Análisis Comparativo de Mercado).
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from ingestas.models import PropiedadRaw

def es_coordenada_valida(coordenadas):
    """Verifica que las coordenadas tengan formato lat, lng y sean números válidos."""
    if not coordenadas:
        return False
    try:
        partes = coordenadas.split(',')
        if len(partes) < 2:
            return False
        lat = float(partes[0].strip())
        lng = float(partes[1].strip())
        # Rango aproximado de Perú
        if -20 <= lat <= 0 and -85 <= lng <= -68:
            return True
        # Si está fuera de Perú pero son números, igual lo aceptamos
        return True
    except (ValueError, AttributeError):
        return False

def verificar_propiedad(propiedad):
    """Evalúa si una propiedad cumple los criterios para el ACM."""
    errores = []
    
    # 1. Tipo de propiedad
    if not propiedad.tipo_propiedad:
        errores.append("Tipo de propiedad vacío")
    
    # 2. Precio positivo
    if not propiedad.precio_usd or propiedad.precio_usd <= 0:
        errores.append("Precio USD no válido")
    
    # 3. Área construida o terreno
    if not propiedad.area_construida and not propiedad.area_terreno:
        errores.append("Falta área construida y terreno")
    
    # 4. Ubicación básica
    if not propiedad.departamento or not propiedad.distrito:
        errores.append("Falta departamento o distrito")
    
    # 5. Condición especificada
    if propiedad.condicion == 'no_especificado':
        errores.append("Condición no especificada")
    
    # 6. Coordenadas válidas
    if not es_coordenada_valida(propiedad.coordenadas):
        errores.append("Coordenadas no válidas")
    
    # 7. (Opcional) Descripción no vacía
    if not propiedad.descripcion or len(propiedad.descripcion.strip()) < 10:
        errores.append("Descripción muy corta")
    
    return errores

def verificar_y_marcar(todas=False, limite=100):
    """
    Verifica propiedades y actualiza el campo 'propiedad_verificada'.
    
    Args:
        todas: Si True, verifica todas las propiedades (puede ser lento).
        limite: Número máximo de propiedades a verificar si no son todas.
    """
    if todas:
        propiedades = PropiedadRaw.objects.all()
    else:
        propiedades = PropiedadRaw.objects.all()[:limite]
    
    total = propiedades.count()
    print(f"Verificando {total} propiedades...")
    
    verificadas = 0
    no_verificadas = 0
    for i, prop in enumerate(propiedades, 1):
        errores = verificar_propiedad(prop)
        if not errores:
            if not prop.propiedad_verificada:
                prop.propiedad_verificada = True
                prop.save()
                verificadas += 1
        else:
            if prop.propiedad_verificada:
                prop.propiedad_verificada = False
                prop.save()
            no_verificadas += 1
            if i <= 10:  # Mostrar solo primeros errores
                print(f"  Propiedad {prop.id} no verificada: {', '.join(errores)}")
        
        if i % 100 == 0:
            print(f"  Procesadas {i}/{total}")
    
    print(f"\nResumen:")
    print(f"  Total propiedades: {total}")
    print(f"  Verificadas (cumplen criterios): {verificadas}")
    print(f"  No verificadas: {no_verificadas}")
    print(f"  Campo 'propiedad_verificada' actualizado.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Verificar propiedades para el ACM')
    parser.add_argument('--todas', action='store_true', help='Verificar todas las propiedades (sin límite)')
    parser.add_argument('--limite', type=int, default=100, help='Límite de propiedades a verificar (por defecto 100)')
    args = parser.parse_args()
    
    verificar_y_marcar(todas=args.todas, limite=args.limite)