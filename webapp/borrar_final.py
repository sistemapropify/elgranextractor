#!/usr/bin/env python
"""
Script FINAL para borrar propiedadraw - USA DELETE en lugar de TRUNCATE
"""
import os
import sys
import django
from django.db import connection

print("=== BORRADO FINAL DE PROPIEDADRAW ===")
print("")

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

try:
    with connection.cursor() as cursor:
        # 1. Contar registros
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        print(f"1. Registros encontrados: {count}")
        
        if count == 0:
            print("   La tabla ya está vacía.")
            sys.exit(0)
        
        # 2. Mostrar información de restricciones
        print("\n2. Verificando restricciones de clave foránea...")
        cursor.execute("""
            SELECT 
                fk.name AS constraint_name,
                OBJECT_NAME(fk.parent_object_id) AS referencing_table,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS referencing_column,
                OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
            FROM sys.foreign_keys fk
            INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            WHERE OBJECT_NAME(fk.referenced_object_id) = 'ingestas_propiedadraw'
        """)
        
        fks = cursor.fetchall()
        if fks:
            print("   Se encontraron las siguientes restricciones:")
            for fk in fks:
                print(f"   - {fk[0]}: {fk[1]}.{fk[2]} → {fk[3]}.{fk[4]}")
        else:
            print("   No se encontraron restricciones de clave foránea.")
        
        # 3. Confirmación automática (SIEMPRE SI)
        print(f"\n3. CONFIRMACIÓN: Borrando {count} registros...")
        print("   Esta acción usará DELETE (más lento pero seguro con FK).")
        
        # 4. Usar DELETE en lugar de TRUNCATE
        print("\n4. Ejecutando DELETE...")
        
        # Opción A: DELETE simple (puede fallar si hay FK con CASCADE)
        try:
            cursor.execute("DELETE FROM ingestas_propiedadraw")
            print(f"   ✓ DELETE ejecutado. Filas afectadas: {cursor.rowcount}")
        except Exception as e:
            print(f"   ✗ Error con DELETE simple: {e}")
            print("   Intentando con DELETE en lotes...")
            
            # Opción B: DELETE en lotes
            try:
                batch_size = 100
                total_deleted = 0
                
                while True:
                    cursor.execute(f"""
                        DELETE TOP ({batch_size}) 
                        FROM ingestas_propiedadraw
                    """)
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    
                    if deleted == 0:
                        break
                    
                    print(f"   Lote: {total_deleted}/{count} registros borrados")
                
                print(f"   ✓ DELETE por lotes completado. Total: {total_deleted}")
            except Exception as e2:
                print(f"   ✗ Error con DELETE por lotes: {e2}")
                print("   Intentando deshabilitar constraints temporalmente...")
                
                # Opción C: Deshabilitar constraints
                try:
                    cursor.execute("ALTER TABLE ingestas_propiedadraw NOCHECK CONSTRAINT ALL")
                    cursor.execute("DELETE FROM ingestas_propiedadraw")
                    cursor.execute("ALTER TABLE ingestas_propiedadraw CHECK CONSTRAINT ALL")
                    print(f"   ✓ DELETE con constraints deshabilitadas.")
                except Exception as e3:
                    print(f"   ✗ Error crítico: {e3}")
                    print("   No se pudo borrar. Necesitas revisar manualmente las FK.")
                    sys.exit(1)
        
        # 5. Verificar
        print("\n5. Verificando borrado...")
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        final_count = cursor.fetchone()[0]
        
        if final_count == 0:
            print(f"   ✓ BORRADO COMPLETO. Tabla vacía confirmada.")
        else:
            print(f"   ✗ Quedan {final_count} registros.")
        
        print("\n" + "="*50)
        print("RESUMEN:")
        print(f"- Registros iniciales: {count}")
        print(f"- Registros finales: {final_count}")
        print(f"- Estado: {'VACÍO' if final_count == 0 else 'PARCIAL'}")
        print("="*50)
        
except Exception as e:
    print(f"Error general: {e}")
    import traceback
    traceback.print_exc()

print("\nScript finalizado.")