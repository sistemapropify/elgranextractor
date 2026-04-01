#!/usr/bin/env python
"""
Script para verificar que los campos 'condicion' y 'propiedad_verificada' tienen datos
después de la reimportación.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== VERIFICACIÓN DE CAMPOS NUEVOS ===\n")
    
    # 1. Contar registros totales
    print("1. Estadísticas generales:")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        total = cursor.fetchone()[0]
        print(f"   Total de registros en PropiedadRaw: {total}")
    
    if total == 0:
        print("\n   ⚠️  La tabla está vacía. Ejecuta primero la reimportación.")
        return
    
    # 2. Verificar campo 'condicion'
    print("\n2. Verificando campo 'condicion':")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(condicion) as con_valor,
                SUM(CASE WHEN condicion IS NULL OR condicion = '' THEN 1 ELSE 0 END) as sin_valor
            FROM ingestas_propiedadraw
        """)
        total, con_valor, sin_valor = cursor.fetchone()
        
        print(f"   Registros con valor en 'condicion': {con_valor}")
        print(f"   Registros sin valor en 'condicion': {sin_valor}")
        
        if con_valor > 0:
            porcentaje = (con_valor / total) * 100
            print(f"   Porcentaje con valor: {porcentaje:.1f}%")
            
            # Mostrar valores únicos
            cursor.execute("SELECT DISTINCT condicion FROM ingestas_propiedadraw WHERE condicion IS NOT NULL AND condicion != ''")
            valores = [row[0] for row in cursor.fetchall()]
            print(f"   Valores únicos encontrados: {', '.join(valores[:10])}")
            if len(valores) > 10:
                print(f"   ... y {len(valores) - 10} más")
        else:
            print("   ⚠️  Ningún registro tiene valor en 'condicion'")
    
    # 3. Verificar campo 'propiedad_verificada'
    print("\n3. Verificando campo 'propiedad_verificada':")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(propiedad_verificada) as con_valor,
                SUM(CASE WHEN propiedad_verificada = 1 THEN 1 ELSE 0 END) as verificadas,
                SUM(CASE WHEN propiedad_verificada = 0 THEN 1 ELSE 0 END) as no_verificadas
            FROM ingestas_propiedadraw
        """)
        total, con_valor, verificadas, no_verificadas = cursor.fetchone()
        
        print(f"   Registros con valor en 'propiedad_verificada': {con_valor}")
        print(f"   Propiedades verificadas (True/1): {verificadas}")
        print(f"   Propiedades no verificadas (False/0): {no_verificadas}")
        
        if con_valor > 0:
            porcentaje_verificadas = (verificadas / total) * 100 if total > 0 else 0
            print(f"   Porcentaje verificadas: {porcentaje_verificadas:.1f}%")
        else:
            print("   ⚠️  Ningún registro tiene valor en 'propiedad_verificada'")
    
    # 4. Ejemplo de algunos registros
    print("\n4. Ejemplo de 5 registros (mostrando campos nuevos):")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TOP 5 
                id, 
                titulo,
                condicion,
                propiedad_verificada
            FROM ingestas_propiedadraw
            ORDER BY id
        """)
        registros = cursor.fetchall()
        
        for i, (id_, titulo, condicion, verificada) in enumerate(registros, 1):
            titulo_display = titulo[:30] + "..." if titulo and len(titulo) > 30 else titulo or "(sin título)"
            condicion_display = condicion if condicion else "(vacío)"
            verificada_display = "Sí" if verificada == 1 else "No" if verificada == 0 else "(NULL)"
            
            print(f"   {i}. ID {id_}: {titulo_display}")
            print(f"      Condición: {condicion_display}")
            print(f"      Verificada: {verificada_display}")
    
    print("\n=== RESUMEN ===")
    if con_valor > 0 and verificadas + no_verificadas > 0:
        print("✅ Los campos nuevos tienen datos.")
        print("   Puedes verificar en el admin de Django y en los templates.")
    else:
        print("⚠️  Algunos campos pueden no tener datos.")
        print("   Revisa el archivo Excel para asegurarte de que las columnas 'condicion' y 'propiedad_verificada' existen.")
    
    print("\nPara verificar visualmente:")
    print("1. Admin Django: http://localhost:8000/admin/ingestas/propiedadraw/")
    print("2. Templates: http://localhost:8000/propiedades/")

if __name__ == "__main__":
    main()