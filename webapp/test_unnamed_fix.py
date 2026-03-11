#!/usr/bin/env python
"""
Test para verificar que las columnas 'Unnamed' se eliminan correctamente
en el módulo de requerimientos.
"""
import sys
import os
import pandas as pd
import tempfile

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from requerimientos.services import ProcesadorExcelRequerimiento

def test_leer_archivo_csv_con_unnamed():
    """Test que crea un CSV con columnas Unnamed y verifica que se eliminen."""
    # Crear un CSV temporal con columnas Unnamed
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("col1,Unnamed: 0,Unnamed: 1,col2\n")
        f.write("valor1,valor2,valor3,valor4\n")
        f.write("a,b,c,d\n")
        temp_path = f.name
    
    try:
        # Simular un archivo subido (usando open)
        with open(temp_path, 'rb') as archivo:
            class MockArchivo:
                name = temp_path
                def read(self):
                    return archivo.read()
            
            mock = MockArchivo()
            # Usar el método leer_archivo
            df = ProcesadorExcelRequerimiento.leer_archivo(mock)
            
            print("DataFrame columns:", df.columns.tolist())
            print("DataFrame shape:", df.shape)
            
            # Verificar que no hay columnas que comiencen con 'Unnamed'
            unnamed_cols = [col for col in df.columns if isinstance(col, str) and col.startswith('Unnamed')]
            assert len(unnamed_cols) == 0, f"Se encontraron columnas Unnamed: {unnamed_cols}"
            
            # Verificar que las columnas correctas permanecen
            expected_cols = ['col1', 'col2']
            for col in expected_cols:
                assert col in df.columns, f"Falta columna {col}"
            
            print("✓ Test CSV con Unnamed pasado")
    finally:
        os.unlink(temp_path)

def test_leer_archivo_excel_con_unnamed():
    """Test similar para Excel (requiere openpyxl)."""
    try:
        import openpyxl
    except ImportError:
        print("Openpyxl no instalado, omitiendo test de Excel")
        return
    
    # Crear un DataFrame con columnas Unnamed
    df_input = pd.DataFrame({
        'col1': [1, 2],
        'Unnamed: 0': ['a', 'b'],
        'Unnamed: 1': ['c', 'd'],
        'col2': [3, 4]
    })
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        temp_path = f.name
    
    try:
        df_input.to_excel(temp_path, index=False, engine='openpyxl')
        
        with open(temp_path, 'rb') as archivo:
            class MockArchivo:
                name = temp_path
                def read(self):
                    return archivo.read()
            
            mock = MockArchivo()
            df = ProcesadorExcelRequerimiento.leer_archivo(mock)
            
            print("DataFrame Excel columns:", df.columns.tolist())
            print("DataFrame Excel shape:", df.shape)
            
            unnamed_cols = [col for col in df.columns if isinstance(col, str) and col.startswith('Unnamed')]
            assert len(unnamed_cols) == 0, f"Se encontraron columnas Unnamed en Excel: {unnamed_cols}"
            
            expected_cols = ['col1', 'col2']
            for col in expected_cols:
                assert col in df.columns, f"Falta columna {col} en Excel"
            
            print("✓ Test Excel con Unnamed pasado")
    finally:
        os.unlink(temp_path)

def test_sugerir_campos_ignora_unnamed():
    """Test que SugeridorCamposRequerimiento ignora columnas Unnamed."""
    from requerimientos.services import SugeridorCamposRequerimiento
    
    df = pd.DataFrame({
        'col1': [1, 2, 3],
        'Unnamed: 0': ['a', 'b', 'c'],
        'col2': ['x', 'y', 'z']
    })
    
    sugerencias = SugeridorCamposRequerimiento.sugerir_campos(df)
    print("Sugerencias:", sugerencias)
    
    # Verificar que no hay sugerencias para columnas Unnamed
    for sug in sugerencias:
        assert not sug['nombre_columna'].startswith('Unnamed'), f"Sugerencia para columna Unnamed: {sug}"
    
    # Debería haber solo 2 sugerencias (col1 y col2)
    assert len(sugerencias) == 2, f"Se esperaban 2 sugerencias, se obtuvieron {len(sugerencias)}"
    
    print("✓ Test sugerir_campos ignorando Unnamed pasado")

if __name__ == '__main__':
    print("Ejecutando tests de corrección de columnas 'Unnamed'...")
    test_leer_archivo_csv_con_unnamed()
    test_sugerir_campos_ignora_unnamed()
    test_leer_archivo_excel_con_unnamed()
    print("\nTodos los tests pasaron exitosamente.")