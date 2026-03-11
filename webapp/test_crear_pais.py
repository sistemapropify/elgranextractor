#!/usr/bin/env python
"""
Script para probar la creación de una zona de tipo "país".
"""

import os
import sys
import django
import json

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
    print("✅ Django configurado correctamente")
    
    from cuadrantizacion.models import ZonaValor
    from cuadrantizacion.serializers import ZonaValorSerializer
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request
    
    # Crear datos de prueba para una zona "país"
    test_data = {
        'nombre_zona': 'Perú',
        'descripcion': 'País de prueba',
        'nivel': 'pais',
        'parent': None,
        'codigo': 'PE',
        'nombre_oficial': 'República del Perú',
        'coordenadas': [],  # Array vacío permitido ahora
        'color_fill': '#2196F3',
        'color_borde': '#1976D2',
        'opacidad': 0.3,
        'activo': True
    }
    
    print("\n🧪 Probando creación de zona 'país'...")
    print(f"Datos de prueba: {json.dumps(test_data, indent=2)}")
    
    # Probar el serializador
    serializer = ZonaValorSerializer(data=test_data)
    
    if serializer.is_valid():
        print("✅ Serializador válido")
        print(f"   Datos validados: {serializer.validated_data}")
        
        # Intentar guardar
        try:
            zona = serializer.save()
            print(f"✅ Zona creada exitosamente:")
            print(f"   ID: {zona.id}")
            print(f"   Nombre: {zona.nombre_zona}")
            print(f"   Nivel: {zona.get_nivel_display()}")
            print(f"   Código: {zona.codigo}")
            print(f"   Coordenadas: {zona.coordenadas}")
            
            # Limpiar: eliminar la zona de prueba
            zona.delete()
            print("✅ Zona de prueba eliminada")
            
        except Exception as e:
            print(f"❌ Error al guardar: {e}")
            import traceback
            traceback.print_exc()
            
    else:
        print("❌ Serializador inválido")
        print(f"   Errores: {serializer.errors}")
        
    # Verificar si ya existen zonas "país"
    print("\n📊 Verificando zonas existentes...")
    zonas_pais = ZonaValor.objects.filter(nivel='pais', activo=True)
    print(f"   Zonas 'país' existentes: {zonas_pais.count()}")
    
    for zona in zonas_pais[:3]:
        print(f"   - {zona.nombre_zona} (ID: {zona.id})")
        
    # Verificar estructura jerárquica
    print("\n🌳 Verificando estructura jerárquica...")
    for nivel_codigo, nivel_nombre in ZonaValor.NIVELES:
        count = ZonaValor.objects.filter(nivel=nivel_codigo, activo=True).count()
        print(f"   {nivel_nombre}: {count} zonas")
        
except Exception as e:
    print(f"❌ Error general: {e}")
    import traceback
    traceback.print_exc()