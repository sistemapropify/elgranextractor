#!/usr/bin/env python
"""
Verificar si hay duplicación de datos en la generación del gráfico.
"""
import json

def verificar_datos_vista():
    print("=== VERIFICACIÓN DE DATOS EN VISTA ===")
    
    # Leer el archivo de vista para ver la lógica
    with open('webapp/analisis_crm/views.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar la sección donde se generan days_of_month y counts_per_day
    import re
    
    # Buscar el bucle while
    pattern = r'while current_day\.date\(\) <= now\.date\(\):.*?days_of_month\.append\((.*?)\).*?counts_per_day\.append\((.*?)\)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        print("Lógica encontrada:")
        print(f"  days_of_month.append({match.group(1)})")
        print(f"  counts_per_day.append({match.group(2)})")
    
    # Buscar si hay múltiples datasets
    print("\n=== VERIFICACIÓN DE DATASETS EN TEMPLATE ===")
    with open('webapp/analisis_crm/templates/analisis_crm/dashboard.html', 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Contar datasets en el gráfico
    datasets = template.count('datasets:')
    print(f"Número de datasets en template: {datasets}")
    
    if datasets > 1:
        print("⚠️  ADVERTENCIA: Puede haber múltiples datasets en el gráfico")
    
    # Extraer la configuración del dataset
    dataset_start = template.find('datasets: [')
    if dataset_start != -1:
        dataset_end = template.find(']', dataset_start)
        dataset_section = template[dataset_start:dataset_end+1]
        
        # Contar llaves {} para ver cuántos datasets hay
        dataset_count = dataset_section.count('{')
        print(f"Número de objetos dataset: {dataset_count}")
        
        if dataset_count > 1:
            print("⚠️  ADVERTENCIA: Hay múltiples datasets en el gráfico, lo que podría causar barras duplicadas")
            # Mostrar los datasets
            datasets_matches = re.findall(r'\{[^}]+\}', dataset_section)
            for i, ds in enumerate(datasets_matches[:2]):
                print(f"\nDataset {i+1}:")
                print(ds[:200])
    
    # Verificar tooltips
    print("\n=== VERIFICACIÓN DE TOOLTIPS ===")
    tooltip_match = re.search(r'tooltip:\s*\{[^}]+\}', template)
    if tooltip_match:
        tooltip_config = tooltip_match.group(0)
        print("Configuración de tooltip encontrada:")
        print(tooltip_config[:300])
        
        # Verificar si hay callbacks que puedan causar problemas
        if 'callback' in tooltip_config:
            print("⚠️  Hay callbacks en tooltips, podrían causar problemas")

def simular_datos_duplicados():
    print("\n=== SIMULACIÓN DE DATOS DUPLICADOS ===")
    
    # Datos de ejemplo que podrían causar dos barras por día
    # Si hay dos datasets con los mismos labels pero diferentes datos
    ejemplo = """
    data: {
        labels: ['1', '2', '3', '4', '5'],
        datasets: [
            {
                label: 'Leads por día',
                data: [12, 8, 15, 20, 10]
            },
            {
                label: 'Otro dataset',
                data: [5, 3, 7, 8, 4]
            }
        ]
    }
    """
    
    print("Ejemplo de dos datasets que causarían dos barras por día:")
    print(ejemplo)
    
    print("\nEn el template actual, verificar si hay más de un dataset.")

def main():
    verificar_datos_vista()
    simular_datos_duplicados()
    
    print("\n=== RECOMENDACIONES ===")
    print("1. Asegurarse de que solo hay un dataset en el gráfico.")
    print("2. Verificar que los datos no tengan duplicados en la base de datos.")
    print("3. Revisar que las etiquetas (labels) sean únicas.")
    print("4. Comprobar que no haya múltiples gráficos superpuestos.")

if __name__ == "__main__":
    main()