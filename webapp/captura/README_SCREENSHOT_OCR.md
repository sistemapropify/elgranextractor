# Módulo de Captura de Screenshot y OCR

Este módulo permite capturar screenshots completos de páginas web y extraer texto mediante OCR (Reconocimiento Óptico de Caracteres). Es ideal para capturar contenido dinámico, páginas con scroll infinito, o cualquier página web que necesites convertir a texto.

## Características principales

- **Captura completa de página**: Captura desde arriba hasta el final, incluyendo contenido lazy-loaded
- **Scroll automático**: Detecta y carga todo el contenido de la página
- **Guardado en JPG**: Imágenes comprimidas con calidad configurable
- **OCR integrado**: Extracción de texto usando Tesseract OCR
- **Preprocesamiento de imágenes**: Mejora la precisión del OCR
- **Manejo de errores**: Robustez ante páginas problemáticas
- **Context manager**: Uso seguro con `with` statement

## Requisitos

### Dependencias de Python

```bash
pip install selenium Pillow pytesseract opencv-python webdriver-manager
```

### Dependencias del sistema

- **Chrome/Chromium**: Navegador Chrome instalado
- **ChromeDriver**: Automáticamente manejado por `webdriver-manager`
- **Tesseract OCR**: Motor de OCR instalado en el sistema
  - **Windows**: Descargar de [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng`
  - **macOS**: `brew install tesseract tesseract-lang`

## Uso básico

### Ejemplo 1: Captura simple con función de conveniencia

```python
from webapp.captura.captura_screenshot import capturar_pagina_completa

resultado = capturar_pagina_completa("https://example.com")

if resultado['exito']:
    print(f"✓ Captura exitosa: {resultado['captura']['ruta_imagen']}")
    print(f"✓ Dimensiones: {resultado['captura']['dimensiones'][0]}x{resultado['captura']['dimensiones'][1]}")
    print(f"✓ Texto extraído: {len(resultado['texto_completo'])} caracteres")
    print(f"✓ Confianza OCR: {resultado['ocr']['confianza_promedio']:.2f}")
    
    # Guardar texto en archivo
    with open("texto_extraido.txt", "w", encoding="utf-8") as f:
        f.write(resultado['texto_completo'])
else:
    print(f"✗ Error: {resultado['error']}")
```

### Ejemplo 2: Uso avanzado con clase

```python
from webapp.captura.captura_screenshot import CapturaScreenshot

# Usar context manager para manejo automático del driver
with CapturaScreenshot(
    output_dir="mis_capturas",
    jpg_quality=90,
    ocr_language="spa+eng"  # Español + inglés
) as capturador:
    
    # Capturar screenshot sin OCR
    resultado_captura = capturador.capturar_screenshot_completo(
        url="https://news.ycombinator.com",
        nombre_archivo="hacker_news"
    )
    
    if resultado_captura['exito']:
        print(f"Imagen guardada: {resultado_captura['ruta_imagen']}")
        
        # Extraer texto con OCR después
        resultado_ocr = capturador.extraer_texto_ocr(
            ruta_imagen=resultado_captura['ruta_imagen'],
            preprocesar=True  # Mejorar imagen para OCR
        )
        
        if resultado_ocr['exito']:
            print(f"Texto extraído ({len(resultado_ocr['texto'])} caracteres):")
            print(resultado_ocr['texto'][:500] + "...")
```

### Ejemplo 3: Desde línea de comandos

```bash
# Capturar página y extraer texto
python -m webapp.captura.captura_screenshot https://example.com

# O usando el script directamente
python webapp/captura/captura_screenshot.py https://news.ycombinator.com
```

## API de la clase `CapturaScreenshot`

### Constructor

```python
CapturaScreenshot(
    driver_path: Optional[str] = None,  # Ruta a ChromeDriver (opcional)
    output_dir: str = "capturas_screenshots",  # Directorio de salida
    jpg_quality: int = 85,  # Calidad JPG (1-100)
    ocr_language: str = "spa+eng"  # Idioma para OCR
)
```

### Métodos principales

#### `capturar_screenshot_completo(url, nombre_archivo=None)`
Captura un screenshot completo de una página web.

**Parámetros:**
- `url`: URL de la página a capturar
- `nombre_archivo`: Nombre del archivo (sin extensión). Si es None, se genera automáticamente.

**Retorna:** Diccionario con:
```python
{
    'exito': bool,
    'ruta_imagen': str,  # Ruta al archivo guardado
    'tamaño_bytes': int,
    'dimensiones': (ancho, alto),
    'error': str,  # None si no hay error
    'metadatos': dict  # Información adicional
}
```

#### `extraer_texto_ocr(ruta_imagen, preprocesar=True)`
Extrae texto de una imagen usando OCR.

**Parámetros:**
- `ruta_imagen`: Ruta a la imagen (JPG/PNG)
- `preprocesar`: Si es True, aplica preprocesamiento para mejorar OCR

**Retorna:** Diccionario con:
```python
{
    'exito': bool,
    'texto': str,  # Texto extraído
    'confianza_promedio': float,  # Confianza promedio del OCR
    'idioma_detectado': str,
    'error': str,
    'metadatos': dict
}
```

#### `capturar_y_extraer_texto(url, guardar_imagen=True)`
Combina captura y OCR en un solo paso.

**Parámetros:**
- `url`: URL de la página a capturar
- `guardar_imagen`: Si es False, elimina la imagen después del OCR

**Retorna:** Diccionario combinado con resultados de captura y OCR.

## Configuración avanzada

### Idiomas de OCR

El parámetro `ocr_language` acepta códigos de idioma de Tesseract:

- `"spa"`: Español
- `"eng"`: Inglés
- `"spa+eng"`: Español e inglés (recomendado para páginas bilingües)
- `"fra"`: Francés
- `"deu"`: Alemán
- `"por"`: Portugués

Para usar múltiples idiomas, sepáralos con `+`: `"spa+eng+fra"`

### Calidad de imagen

- `jpg_quality=85`: Calidad buena, tamaño moderado (recomendado)
- `jpg_quality=95`: Alta calidad, archivos más grandes
- `jpg_quality=70`: Calidad aceptable, archivos pequeños

### Directorio de salida

Las capturas se guardan en el directorio especificado en `output_dir`. Si no existe, se crea automáticamente.

## Solución de problemas

### Error: "ChromeDriver not found"
El módulo usa `webdriver-manager` para manejar ChromeDriver automáticamente. Si falla:

1. Asegúrate de tener Chrome instalado
2. Instala `webdriver-manager`: `pip install webdriver-manager`
3. O descarga ChromeDriver manualmente y especifica la ruta en `driver_path`

### Error: "Tesseract is not installed"
Instala Tesseract OCR en tu sistema:

**Windows:**
1. Descarga el instalador de [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Durante la instalación, selecciona los idiomas que necesites
3. Agrega Tesseract al PATH del sistema

**Linux:**
```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-spa  # Para español
sudo apt install tesseract-ocr-eng  # Para inglés
```

### Error: "Timeout al cargar la página"
- Aumenta el timeout en el código fuente si es necesario
- Verifica que la URL sea accesible
- Considera páginas con mucho JavaScript que puedan requerir más tiempo

### Baja precisión de OCR
- Activa el preprocesamiento: `preprocesar=True`
- Aumenta la calidad de la imagen: `jpg_quality=95`
- Verifica que el idioma esté configurado correctamente
- Considera páginas con fuentes muy decorativas o imágenes complejas

## Integración con el proyecto existente

Este módulo se integra con la estructura existente de `webapp/captura/`:

- **`mejorador_captura.py`**: Captura HTML con Selenium
- **`captura_screenshot.py`**: Captura imágenes y extrae texto con OCR
- **`extractor_pdf.py`**: Extrae texto de PDFs (similar funcionalidad para documentos)

Puedes combinar estos módulos para un pipeline completo de captura de contenido.

## Ejemplos de casos de uso

### 1. Monitoreo de cambios en páginas web
```python
# Capturar página hoy
resultado1 = capturar_pagina_completa("https://mi-sitio.com")
texto_hoy = resultado1['texto_completo']

# Capturar mañana y comparar
resultado2 = capturar_pagina_completa("https://mi-sitio.com")
texto_manana = resultado2['texto_completo']

# Comparar cambios
if texto_hoy != texto_manana:
    print("¡La página ha cambiado!")
```

### 2. Archivo de páginas web importantes
```python
urls_importantes = [
    "https://noticias.com/ultima-hora",
    "https://blog.tecnologia.com",
    "https://documentos.oficiales.gob"
]

for url in urls_importantes:
    resultado = capturar_pagina_completa(url)
    if resultado['exito']:
        print(f"Archivado: {url} -> {resultado['captura']['ruta_imagen']}")
```

### 3. Extracción de datos de páginas sin API
```python
# Capturar página de productos
resultado = capturar_pagina_completa("https://tienda.com/productos")

# Analizar texto extraído
texto = resultado['texto_completo']
# Buscar patrones, precios, nombres de productos, etc.
```

## Limitaciones

1. **Páginas con autenticación**: No maneja login automático
2. **Captchas**: No puede resolver captchas
3. **Contenido en video/audio**: Solo extrae texto visible
4. **JavaScript muy complejo**: Algunas páginas pueden requerir tiempo adicional
5. **Tamaño de página**: Páginas muy largas (>10,000px) pueden tener problemas de memoria

## Contribución

Para reportar problemas o sugerir mejoras:

1. Revisa los logs de error
2. Verifica que todas las dependencias estén instaladas
3. Proporciona la URL que causa el problema
4. Incluye el mensaje de error completo

## Licencia

Parte del proyecto Prometeo - Sistema de captura y análisis web.