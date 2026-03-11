"""
Script de prueba para el módulo de procesamiento IA.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestas.procesamiento_ia import procesar_excel_con_ia

def test_con_csv_existente():
    """Prueba con el archivo CSV de requerimientos existente."""
    ruta = 'test_requerimientos.csv'
    if not os.path.exists(ruta):
        print(f"Archivo {ruta} no encontrado. Creando uno de prueba...")
        crear_csv_prueba(ruta)
    
    try:
        print("=== INICIANDO PRUEBA DE PROCESAMIENTO IA ===")
        resultado = procesar_excel_con_ia(ruta, max_filas=5)
        
        print("\n=== MÉTRICAS ===")
        metricas = resultado['metricas']
        for k, v in metricas.items():
            print(f"{k}: {v}")
        
        print("\n=== CAMPOS ÚNICOS DETECTADOS ===")
        for campo, info in resultado['campos_unicos'].items():
            print(f"- {campo}: {info['ocurrencias']} ocurrencias")
        
        print("\n=== PRIMER RESULTADO ===")
        if resultado['resultados']:
            primer = resultado['resultados'][0]
            print(f"ID: {primer['id']}")
            print(f"Datos base: {primer['datos_base']}")
            print(f"Campos dinámicos: {primer['campos_dinamicos']}")
        
        print("\n=== ERRORES ===")
        print(f"Filas con error: {resultado['errores']}")
        
        print("\n=== PRUEBA EXITOSA ===")
        return True
    except Exception as e:
        print(f"ERROR en prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

def crear_csv_prueba(ruta: str):
    """Crea un CSV de prueba con columnas estándar."""
    import pandas as pd
    data = {
        'fuente': ['web', 'web', 'oficina'],
        'fecha': ['2025-01-01', '2025-01-02', '2025-01-03'],
        'hora': ['10:00', '11:30', '09:15'],
        'agente': ['Juan', 'María', 'Carlos'],
        'requerimiento': [
            'Necesito alquilar departamento en Miraflores con 2 dormitorios, 1 baño, presupuesto 1500 USD',
            'Venta de casa en Surco, 3 dormitorios, 200 m2, precio 300000 soles',
            'Busco oficina en San Isidro, amoblada, 100 m2'
        ],
        'tipo': ['ALQUILER', 'VENTA', 'ALQUILER']
    }
    df = pd.DataFrame(data)
    df.to_csv(ruta, index=False, encoding='utf-8')
    print(f"Archivo de prueba creado: {ruta}")

if __name__ == '__main__':
    success = test_con_csv_existente()
    sys.exit(0 if success else 1)