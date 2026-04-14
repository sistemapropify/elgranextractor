import os
import sys

def generar_arbol(directorio, excluir=None, nivel=0, es_ultimo=True, prefijo=''):
    """
    Genera una representación de árbol del directorio.
    """
    if excluir is None:
        excluir = ['.venv', '.vscode', '__pycache__', '.git', '.github']
    
    nombre = os.path.basename(directorio)
    
    # Determinar prefijo visual
    if nivel == 0:
        linea = nombre + '/'
    else:
        rama = '└── ' if es_ultimo else '├── '
        linea = prefijo + rama + nombre
        if os.path.isdir(directorio):
            linea += '/'
    
    # Excluir carpetas no deseadas
    if nombre in excluir:
        return ''
    
    resultado = [linea] if nivel == 0 or linea else []
    
    if os.path.isdir(directorio):
        try:
            elementos = sorted(os.listdir(directorio))
            # Separar archivos y carpetas
            carpetas = [e for e in elementos if os.path.isdir(os.path.join(directorio, e)) and e not in excluir]
            archivos = [e for e in elementos if os.path.isfile(os.path.join(directorio, e))]
            carpetas.sort()
            archivos.sort()
            todos = carpetas + archivos
            
            for i, elem in enumerate(todos):
                es_ultimo_elem = (i == len(todos) - 1)
                nuevo_prefijo = prefijo + ('    ' if es_ultimo else '│   ')
                subdir = os.path.join(directorio, elem)
                resultado.extend(generar_arbol(subdir, excluir, nivel + 1, es_ultimo_elem, nuevo_prefijo))
        except PermissionError:
            pass
    
    return resultado

def main():
    raiz = '.'
    excluir = ['.venv', '.vscode', '__pycache__', '.git', '.github', 'node_modules', '.idea']
    
    lineas = generar_arbol(raiz, excluir)
    
    # Guardar en archivo
    with open('arbol_completo.md', 'w', encoding='utf-8') as f:
        f.write('# Árbol completo del proyecto Prometeo\n\n')
        f.write('```\n')
        for linea in lineas:
            f.write(linea + '\n')
        f.write('```\n')
    
    print(f"Árbol generado en 'arbol_completo.md' con {len(lineas)} líneas.")

if __name__ == '__main__':
    main()