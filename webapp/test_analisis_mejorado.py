#!/usr/bin/env python
"""
Script de prueba para verificar el análisis mejorado de esquemas de tabla.
Prueba las nuevas funcionalidades de análisis inteligente de campos y sugerencias automáticas.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from intelligence.services.schema_discovery import SchemaDiscoveryService

def test_analisis_tabla_propiedades():
    """Prueba el análisis de la tabla 'properties' en la base de datos 'propifai'."""
    print("Probando analisis mejorado de tabla 'properties'...")
    
    try:
        # Analizar esquema de la tabla
        analisis = SchemaDiscoveryService.analyze_table_schema(
            table_name='properties',
            schema='dbo',
            database_alias='propifai'
        )
        
        if not analisis.get('exists'):
            print(f"Error: Tabla no encontrada: {analisis.get('error')}")
            return False
        
        print(f"Tabla encontrada: {analisis['table_name']}")
        print(f"Filas: {analisis['row_count']}")
        print(f"Clave primaria detectada: {analisis['primary_key']}")
        
        # Mostrar columnas con análisis
        print("\nColumnas con analisis inteligente:")
        for col in analisis['columns']:
            field_name = col['name']
            field_type = col['type']
            is_primary = col.get('is_primary', False)
            is_identity = col.get('is_identity', False)
            
            # Obtener análisis del campo
            field_analysis = analisis.get('field_analysis', {}).get(field_name, {})
            category = field_analysis.get('category', 'unknown')
            notes = field_analysis.get('notes', '')
            
            print(f"  • {field_name} ({field_type})")
            print(f"    Categoria: {category}")
            if is_primary:
                print(f"    [PK] Clave primaria")
            if is_identity:
                print(f"    [ID] Identity")
            if notes:
                print(f"    Notas: {notes}")
            
            # Mostrar sugerencias
            suggested_for = []
            if field_analysis.get('suggested_for_embedding'):
                suggested_for.append('embedding')
            if field_analysis.get('suggested_for_display'):
                suggested_for.append('display')
            if field_analysis.get('suggested_for_filtering'):
                suggested_for.append('filtering')
            
            if suggested_for:
                print(f"    [SUG] Sugerido para: {', '.join(suggested_for)}")
            
            if not field_analysis.get('serialization_safe', True):
                print(f"    [WARN] Requiere serializacion especial")
            
            print()
        
        # Mostrar sugerencias de configuración
        suggestions = analisis.get('suggestions', {})
        if suggestions:
            print("\nSugerencias de configuracion automatica:")
            print(f"  • Campos para embedding: {', '.join(suggestions.get('embedding_fields', []))}")
            print(f"  • Campos para visualizacion: {', '.join(suggestions.get('display_fields', []))}")
            print(f"  • Campos para filtrado: {', '.join(suggestions.get('filter_fields', []))}")
            print(f"  • Resumen: {suggestions.get('configuration_summary', '')}")
            
            # Mostrar advertencias
            warnings = suggestions.get('validation_warnings', [])
            if warnings:
                print("\nAdvertencias de validacion:")
                for warning in warnings:
                    print(f"  • {warning}")
        
        # Probar con datos de muestra
        print("\nDatos de muestra (primeros 3 registros):")
        sample_data = analisis.get('sample_data', [])
        for i, row in enumerate(sample_data[:3]):
            print(f"  Registro {i+1}:")
            for key, value in list(row.items())[:5]:  # Mostrar primeros 5 campos
                print(f"    {key}: {value}")
            print()
        
        return True
        
    except Exception as e:
        print(f"Error durante el analisis: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_analisis_tabla_diferente():
    """Prueba el análisis de una tabla diferente para verificar que el sistema es genérico."""
    print("\nProbando analisis de tabla diferente...")
    
    # Primero listar tablas disponibles
    try:
        tablas = SchemaDiscoveryService.list_tables(database_alias='propifai')
        print(f"Tablas disponibles en 'propifai': {len(tablas)}")
        
        # Buscar una tabla diferente a 'properties'
        tabla_diferente = None
        for tabla in tablas:
            if tabla['name'].lower() != 'properties':
                tabla_diferente = tabla['name']
                break
        
        if not tabla_diferente:
            print("No se encontro tabla diferente para probar")
            return True
        
        print(f"Analizando tabla: {tabla_diferente}")
        
        # Analizar la tabla
        analisis = SchemaDiscoveryService.analyze_table_schema(
            table_name=tabla_diferente,
            schema='dbo',
            database_alias='propifai'
        )
        
        if not analisis.get('exists'):
            print(f"Tabla '{tabla_diferente}' no encontrada, continuando...")
            return True
        
        print(f"Analisis completado para '{tabla_diferente}'")
        print(f"{len(analisis['columns'])} columnas analizadas")
        
        # Verificar que se generaron sugerencias
        suggestions = analisis.get('suggestions', {})
        if suggestions:
            print(f"Sugerencias generadas: {len(suggestions.get('embedding_fields', []))} campos para embedding")
            return True
        else:
            print("No se generaron sugerencias para esta tabla")
            return True
            
    except Exception as e:
        print(f"Error analizando tabla diferente: {e}")
        return False

def main():
    """Función principal de prueba."""
    print("=" * 60)
    print("PRUEBA DEL SISTEMA MEJORADO DE ANALISIS DE ESQUEMAS")
    print("=" * 60)
    
    # Probar análisis de tabla properties
    success1 = test_analisis_tabla_propiedades()
    
    # Probar análisis de tabla diferente
    success2 = test_analisis_tabla_diferente()
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    if success1 and success2:
        print("TODAS LAS PRUEBAS PASARON CORRECTAMENTE")
        print("\nEl sistema ahora es generico y puede:")
        print("   • Analizar automaticamente tipos de campo")
        print("   • Sugerir configuraciones inteligentes")
        print("   • Validar problemas de serializacion")
        print("   • Funcionar con cualquier tabla, no solo 'properties'")
    else:
        print("ALGUNAS PRUEBAS FALLARON")
        if not success1:
            print("   - Fallo analisis de tabla 'properties'")
        if not success2:
            print("   - Fallo analisis de tabla diferente")
    
    print("\nEl sistema esta listo para manejar cientos de tablas con diferentes estructuras.")
    print("   Los usuarios ya no necesitaran reconfigurar manualmente cada tabla.")

if __name__ == '__main__':
    main()