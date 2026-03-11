import pandas as pd
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from requerimientos.models import Requerimiento, FuenteChoices

path = 'data/requerimientos_completo.xlsx'
hoja = 'Todos los Registros'
empezar_fila = 2

print("=== SIMULACIÓN DE IMPORTACIÓN ===")
print(f"Archivo: {path}")
print(f"Hoja: {hoja}")
print(f"Fila inicio: {empezar_fila}")

try:
    df = pd.read_excel(path, sheet_name=hoja, header=empezar_fila-1)
    print(f"DataFrame shape: {df.shape}")
    print(f"Columnas detectadas: {list(df.columns)}")
    
    # Mapeo igual que en admin.py
    mapeo_columnas = {
        'fuente': 'Fuente',
        'fecha': 'Fecha',
        'hora': 'Hora',
        'agente': 'Agente',
        'agente_telefono': 'Tel Agente',
        'tipo_original': 'Tipo Original',
        'condicion': 'Condicion',
        'tipo_propiedad': 'Tipo Propiedad',
        'distritos': 'Distritos',
        'requerimiento': 'Requerimiento',
        'presupuesto_monto': 'Presupuesto Monto',
        'presupuesto_moneda': 'Moneda',
        'presupuesto_forma_pago': 'Forma Pago',
        'habitaciones': 'Habitaciones',
        'banos': 'Banos',
        'cochera': 'Cochera',
        'ascensor': 'Ascensor',
        'amueblado': 'Amueblado',
        'area_m2': 'Area m2',
        'piso_preferencia': 'Piso Preferencia',
        'caracteristicas_extra': 'Caracteristicas Extra',
    }
    
    def convertir_valor(campo, valor):
        if pd.isna(valor):
            return None
        if isinstance(valor, str):
            valor = valor.strip()
            if valor == '':
                return None
        if campo == 'es_urgente':
            if isinstance(valor, bool):
                return valor
            if isinstance(valor, (int, float)):
                return bool(valor)
            if isinstance(valor, str):
                lower = valor.lower()
                if lower in ('si', 'sí', 'true', 'verdadero', '1', 'yes'):
                    return True
                elif lower in ('no', 'false', 'falso', '0'):
                    return False
        if campo in ('habitaciones', 'banos', 'cochera', 'ascensor', 'piso_preferencia'):
            if valor is None:
                return None
            try:
                return int(float(valor))
            except:
                return None
        if campo == 'area_m2':
            if valor is None:
                return None
            try:
                return float(valor)
            except:
                return None
        if campo == 'presupuesto_monto':
            if valor is None:
                return None
            try:
                return float(valor)
            except:
                return None
        if campo == 'fecha' and isinstance(valor, pd.Timestamp):
            return valor.date()
        if campo == 'hora' and isinstance(valor, pd.Timestamp):
            return valor.time()
        # Normalizar fuente a choices
        if campo == 'fuente' and isinstance(valor, str):
            valor = valor.strip().lower()
            if 'inmobiliarias unidas' in valor:
                return 'inmobiliarias_unidas'
            elif 'éxito' in valor or 'exito' in valor:
                return 'exito_inmobiliario'
            else:
                return 'otro'
        return valor
    
    # Procesar solo las primeras 3 filas
    for idx, row in df.head(3).iterrows():
        print(f"\n--- Procesando fila {idx} (fila Excel {idx + empezar_fila + 1}) ---")
        datos = {}
        for campo_modelo, col_excel in mapeo_columnas.items():
            if col_excel in df.columns:
                valor = row[col_excel]
                datos[campo_modelo] = convertir_valor(campo_modelo, valor)
                print(f"  {campo_modelo} ({col_excel}): {repr(row[col_excel])} -> {repr(datos[campo_modelo])}")
            else:
                datos[campo_modelo] = None
                print(f"  {campo_modelo} ({col_excel}): COLUMNA NO ENCONTRADA")
        
        # Verificar fuente
        print(f"  fuente final: {datos.get('fuente')}")
        
        # Intentar crear (pero no guardar)
        try:
            # Simular creación sin guardar
            print("  Validando campos...")
            # Solo mostrar si hay error
            req = Requerimiento(**datos)
            req.full_clean()
            print("  ✅ Datos válidos")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n=== Fin de simulación ===")
    
except Exception as e:
    print(f"Error general: {e}")
    import traceback
    traceback.print_exc()