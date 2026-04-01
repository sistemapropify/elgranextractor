#!/usr/bin/env python
"""
Script SIMPLE para borrar propiedadraw - Solo DELETE sin complicaciones
"""
import os
import sys
import django
from django.db import connection

print("=== BORRADO SIMPLE DE PROPIEDADRAW ===")
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
        
        # 2. Deshabilitar constraints temporalmente
        print("\n2. Deshabilitando constraints de FK...")
        try:
            cursor.execute("ALTER TABLE ingestas_propiedadraw NOCHECK CONSTRAINT ALL")
            print("   ✓ Constraints deshabilitadas")
        except Exception as e:
            print(f"   Nota: No se pudieron deshabilitar constraints: {e}")
        
        # 3. Ejecutar DELETE
        print(f"\n3. Ejecutando DELETE de {count} registros...")
        try:
            # DELETE en lotes para evitar timeout
            batch_size = 500
            total_deleted = 0
            remaining = count
            
            while remaining > 0:
                delete_count = min(batch_size, remaining)
                cursor.execute(f"DELETE TOP ({delete_count}) FROM ingestas_propiedadraw")
                deleted = cursor.rowcount
                total_deleted += deleted
                remaining = count - total_deleted
                
                if deleted == 0:
                    break
                    
                print(f"   Progreso: {total_deleted}/{count} ({total_deleted*100//count}%)")
            
            print(f"   ✓ DELETE completado: {total_deleted} registros borrados")
            
        except Exception as e:
            print(f"   ✗ Error con DELETE: {e}")
            print("   Intentando DELETE simple...")
            try:
                cursor.execute("DELETE FROM ingestas_propiedadraw")
                print(f"   ✓ DELETE simple: {cursor.rowcount} registros borrados")
            except Exception as e2:
                print(f"   ✗ Error crítico: {e2}")
                sys.exit(1)
        
        # 4. Rehabilitar constraints
        print("\n4. Rehabilitando constraints...")
        try:
            cursor.execute("ALTER TABLE ingestas_propiedadraw CHECK CONSTRAINT ALL")
            print("   ✓ Constraints rehabilitadas")
        except Exception as e:
            print(f"   Nota: No se pudieron rehabilitar constraints: {e}")
        
        # 5. Verificar
        print("\n5. Verificando borrado...")
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        final_count = cursor.fetchone()[0]
        
        if final_count == 0:
            print(f"   ✓ BORRADO COMPLETO. Tabla vacía confirmada.")
        else:
            print(f"   ✗ Quedan {final_count} registros.")
        
        print("\n" + "="*50)
        print("RESULTADO FINAL:")
        print(f"- Registros iniciales: {count}")
        print(f"- Registros finales: {final_count}")
        print(f"- Estado: {'VACÍO' if final_count == 0 else 'PARCIAL'}")
        print("="*50)
        
except Exception as e:
    print(f"Error general: {e}")
    import traceback
    traceback.print_exc()

print("\nScript finalizado.")