import pandas as pd
import os

def main():
    ruta = os.path.join('webapp', 'requerimientos', 'data', 'requerimientos_inmobiliarios.xlsx')
    print(f"Leyendo {ruta}")
    
    df = pd.read_excel(ruta, sheet_name=0, header=0)
    print(f"Filas: {len(df)}")
    
    # Valores únicos en columna Fuente
    if 'Fuente' in df.columns:
        fuentes = df['Fuente'].dropna().unique()
        print(f"Valores únicos en columna 'Fuente' ({len(fuentes)}):")
        for f in fuentes:
            print(f"  '{f}'")
    else:
        print("No hay columna 'Fuente'")
        
    # También verificar columna 'Tipo Original'
    if 'Tipo Original' in df.columns:
        tipos = df['Tipo Original'].dropna().unique()
        print(f"\nValores únicos en 'Tipo Original' ({len(tipos)}):")
        for t in tipos[:10]:
            print(f"  '{t}'")
        if len(tipos) > 10:
            print(f"  ... y {len(tipos) - 10} más")

if __name__ == '__main__':
    main()