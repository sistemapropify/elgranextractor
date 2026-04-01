#!/usr/bin/env python
"""
Diagnóstico del problema de dos barras por día en el gráfico.
"""
import re

def analizar_template():
    print("=== ANÁLISIS DEL TEMPLATE HTML ===")
    
    # Leer el template
    try:
        with open('webapp/analisis_crm/templates/analisis_crm/dashboard.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error leyendo template: {e}")
        return
    
    # Buscar la sección JavaScript donde se crea el gráfico
    chart_start = content.find('new Chart(ctx, {')
    if chart_start == -1:
        print("No se encontró la creación del gráfico")
        return
    
    # Extraer una porción del código
    snippet = content[chart_start:chart_start+2000]
    
    # Buscar la configuración de labels
    labels_match = re.search(r'labels:\s*(\w+)', snippet)
    if labels_match:
        labels_var = labels_match.group(1)
        print(f"Variable de labels: {labels_var}")
    
    # Buscar datos de ejemplo
    example_match = re.search(r"chartDays\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if example_match:
        example_data = example_match.group(1)
        print(f"\nDatos de ejemplo en JavaScript:")
        print(f"  chartDays = [{example_data[:100]}...]")
    
    # Verificar si hay múltiples llamadas a Chart
    chart_calls = content.count('new Chart(')
    print(f"\nNúmero de llamadas a Chart: {chart_calls}")
    
    if chart_calls > 1:
        print("⚠️  ADVERTENCIA: Hay múltiples gráficos en la página, podría causar duplicación")
    
    # Buscar problemas con comillas en títulos
    title_matches = re.findall(r'title:\s*{[^}]*text:\s*([^,}]+)', content)
    if title_matches:
        print(f"\nTítulos encontrados:")
        for title in title_matches:
            print(f"  - {title}")
            if '"' in title or "'" in title:
                print(f"    ⚠️  Contiene comillas: {title}")

def simular_problema_comillas():
    print("\n=== SIMULACIÓN DE PROBLEMA DE COMILLAS ===")
    print("Si el título de la barra tiene comillas, podría causar problemas de visualización.")
    print("Ejemplo de título problemático: 'Día \"5\"' o \"Día '5'\"")
    
    # Verificar el template actual
    with open('webapp/analisis_crm/templates/analisis_crm/dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar tooltip callbacks
    tooltip_matches = re.findall(r'tooltip:\s*{([^}]+)}', content, re.DOTALL)
    for tooltip in tooltip_matches:
        if 'label' in tooltip:
            print("\nConfiguración de tooltip encontrada:")
            print(tooltip[:200])

def main():
    analizar_template()
    simular_problema_comillas()
    
    print("\n=== POSIBLES CAUSAS DE DOS BARRAS POR DÍA ===")
    print("1. Datos duplicados en la base de datos para el mismo día")
    print("2. Múltiples gráficos superpuestos")
    print("3. Problema de formato en las etiquetas (comillas)")
    print("4. Error en la generación de días (duplicados en days_of_month)")
    print("5. Chart.js interpretando mal las etiquetas")

if __name__ == "__main__":
    main()