# 🚀 INICIO RÁPIDO - SISTEMA DE CAPTURA CRUDO

## Instalación en 5 Pasos

### 1. Instalar Dependencias

```bash
cd webapp
pip install azure-storage-blob pdfplumber PyPDF2
```

### 2. Configurar Variables de Entorno

Editar `.env`:
```bash
# Azure Storage (REQUERIDO)
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=tunombre;AccountKey=tukey;EndpointSuffix=core.windows.net"
AZURE_STORAGE_CONTAINER_NAME="documentos-crudos"

# O alternativamente
AZURE_STORAGE_ACCOUNT_NAME="tunombre"
AZURE_STORAGE_ACCOUNT_KEY="tukey"
```

### 3. Aplicar Migraciones

```bash
python manage.py migrate
```

### 4. Crear Semillas Iniciales

```python
python manage.py shell

from semillas.models import FuenteWeb

# Semilla 1: Listado de búsqueda
FuenteWeb.objects.create(
    nombre='Construir Arequipa Inmobiliaria',
    url='https://construir.com.pe/?s=arequipa+inmobiliaria',
    tipo='semilla_listado',
    categoria='inteligencia',
    estado='activa',
    prioridad=4,
    frecuencia_revision_horas=12,
    es_semilla_activa=True
)

# Semilla 2: El Peruano - Normas Legales
FuenteWeb.objects.create(
    nombre='El Peruano Normas Legales',
    url='https://elperuano.pe/seccion/normas-legales/',
    tipo='semilla_listado',
    categoria='legal',
    frecuencia_revision_horas=24
)

# Semilla 3: PDF Directo (ejemplo)
FuenteWeb.objects.create(
    nombre='Ley 27287 Títulos Valores',
    url='https://www.leyes.congreso.gob.pe/documentos/leyes/27287.pdf',
    tipo='documento_directo_pdf',
    categoria='legal',
    frecuencia_revision_horas=168  # 1 semana (contenido estático)
)

print("✅ Semillas creadas exitosamente")
```

### 5. Procesar Primera Fuente

```python
from colas.tareas_captura import procesar_fuente_completa

# Procesar fuente ID 1
resultado = procesar_fuente_completa.delay(1)

print(f"Tarea iniciada: {resultado.id}")
print(f"Estado: {resultado.state}")

# Esperar resultado (opcional)
resultado.get(timeout=120)
print("✅ Procesamiento completado")
```

---

## Verificar Resultados

### Ver Capturas Creadas

```python
from captura.models import CapturaCruda

# Todas las capturas
capturas = CapturaCruda.objects.all()
for c in capturas:
    print(f"{c.id}: {c.fuente.nombre} - {c.estado_procesamiento}")

# Capturas listas
listas = CapturaCruda.objects.filter(estado_procesamiento='texto_extraido_ok')
print(f"\n✅ {listas.count()} capturas con texto extraído")

# PDFs que requieren OCR
pdfs_ocr = CapturaCruda.objects.filter(estado_procesamiento='requiere_ocr')
print(f"⚠️  {pdfs_ocr.count()} PDFs requieren OCR")
```

### Ver Fuentes Descubiertas (de semillas)

```python
from semillas.models import FuenteWeb

# Fuentes hijo creadas desde semillas
hijos = FuenteWeb.objects.exclude(descubierta_por=None)
print(f"🌱 {hijos.count()} fuentes descubiertas desde semillas")

for h in hijos[:5]:
    print(f"  - {h.nombre[:60]} (de {h.descubierta_por.nombre})")
```

---

## Ejemplos de Semillas Sugeridas

### OFERTA ACTIVA (Portales Inmobiliarios)

```python
# Urbania Arequipa
FuenteWeb.objects.create(
    nombre='Urbania Arequipa Departamentos',
    url='https://urbania.pe/buscar/departamentos-en-venta/arequipa',
    tipo='semilla_listado',
    categoria='oferta',
    frecuencia_revision_horas=2
)

# AdondeVivir
FuenteWeb.objects.create(
    nombre='AdondeVivir Arequipa',
    url='https://www.adondevivir.com/propiedades/venta/departamento/arequipa',
    tipo='semilla_listado',
    categoria='oferta',
    frecuencia_revision_horas=3
)
```

### LEGAL (Normas y Leyes)

```python
# El Peruano
FuenteWeb.objects.create(
    nombre='El Peruano Normas Legales',
    url='https://elperuano.pe/seccion/normas-legales/',
    tipo='semilla_listado',
    categoria='legal',
    frecuencia_revision_horas=24
)

# Congreso - Resultados de búsqueda
FuenteWeb.objects.create(
    nombre='Leyes Congreso',
    url='https://www.leyes.congreso.gob.pe/ResultadoLeyes.aspx',
    tipo='semilla_listado',
    categoria='legal',
    frecuencia_revision_horas=24
)
```

### INFRAESTRUCTURA (Obras Públicas)

```python
# Construir - Proyectos Arequipa
FuenteWeb.objects.create(
    nombre='Construir Proyectos Arequipa',
    url='https://construir.com.pe/?s=arequipa+proyectos',
    tipo='semilla_listado',
    categoria='infraestructura',
    frecuencia_revision_horas=12
)

# MTC - Proyectos de Inversión
FuenteWeb.objects.create(
    nombre='MTC Proyectos',
    url='https://www.gob.pe/mtc',
    tipo='semilla_listado',
    categoria='infraestructura',
    frecuencia_revision_horas=24
)
```

### INTELIGENCIA (Análisis de Mercado)

```python
# Construir - Inmobiliaria Arequipa
FuenteWeb.objects.create(
    nombre='Construir Análisis Inmobiliario',
    url='https://construir.com.pe/?s=arequipa+inmobiliaria',
    tipo='semilla_listado',
    categoria='inteligencia',
    frecuencia_revision_horas=12
)
```

---

## Comandos Útiles

### Procesar Todas las Fuentes Activas

```python
from semillas.models import FuenteWeb
from colas.tareas_captura import procesar_fuente_completa

fuentes = FuenteWeb.objects.filter(estado='activa')
for fuente in fuentes:
    procesar_fuente_completa.delay(fuente.id)
    print(f"✅ Procesando: {fuente.nombre}")
```

### Limpiar Capturas Antiguas

```python
from django.utils import timezone
from datetime import timedelta
from captura.models import CapturaCruda

# Eliminar capturas de más de 30 días
fecha_limite = timezone.now() - timedelta(days=30)
capturas_antiguas = CapturaCruda.objects.filter(fecha_captura__lt=fecha_limite)
count = capturas_antiguas.count()
capturas_antiguas.delete()
print(f"🗑️  {count} capturas antiguas eliminadas")
```

### Ver Estadísticas

```python
from captura.models import CapturaCruda
from semillas.models import FuenteWeb

print("📊 ESTADÍSTICAS DEL SISTEMA")
print("-" * 50)
print(f"Fuentes totales: {FuenteWeb.objects.count()}")
print(f"Fuentes activas: {FuenteWeb.objects.filter(estado='activa').count()}")
print(f"Semillas: {FuenteWeb.objects.filter(tipo='semilla_listado').count()}")
print(f"Capturas totales: {CapturaCruda.objects.count()}")
print(f"Texto extraído OK: {CapturaCruda.objects.filter(estado_procesamiento='texto_extraido_ok').count()}")
print(f"PDFs nativos: {CapturaCruda.objects.filter(tipo_documento='pdf_nativo').count()}")
print(f"PDFs escaneados: {CapturaCruda.objects.filter(tipo_documento='pdf_escaneado').count()}")
print(f"Requieren OCR: {CapturaCruda.objects.filter(estado_procesamiento='requiere_ocr').count()}")
```

---

## Solución de Problemas Comunes

### ❌ Error: "azure-storage-blob no está instalado"

```bash
pip install azure-storage-blob
```

### ❌ Error: "pdfplumber no está instalado"

```bash
pip install pdfplumber PyPDF2
```

### ❌ Error: "AZURE_STORAGE_CONNECTION_STRING requerida"

Configurar en `.env`:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
```

### ❌ Semilla no crea fuentes hijo

Verificar:
```python
fuente = FuenteWeb.objects.get(id=1)
fuente.tipo = 'semilla_listado'  # Debe ser este tipo
fuente.es_semilla_activa = True  # Debe estar activo
fuente.save()
```

---

## Siguiente Fase (NO INCLUIDA)

Una vez que tienes documentos con `estado_procesamiento='texto_extraido_ok'`, puedes proceder con:

1. **Chunking**: Dividir texto en fragmentos
2. **Embeddings**: Generar vectores con OpenAI/DeepSeek
3. **Vector Store**: Almacenar en Pinecone/Qdrant
4. **RAG**: Queries con contexto
5. **NER**: Extraer entidades (direcciones, precios, etc.)
6. **Knowledge Graph**: Relacionar entidades

---

## Recursos

- 📄 **Documentación Completa**: [`SISTEMA_CAPTURA_CRUDO.md`](SISTEMA_CAPTURA_CRUDO.md)
- 🔧 **Modelos**: [`semillas/models.py`](semillas/models.py), [`captura/models.py`](captura/models.py)
- ⚙️ **Tareas Celery**: [`colas/tareas_captura.py`](colas/tareas_captura.py)
- 🔍 **Detector**: [`captura/detector_tipos.py`](captura/detector_tipos.py)
- 📑 **Extractor PDF**: [`captura/extractor_pdf.py`](captura/extractor_pdf.py)

---

## ✅ Lista de Verificación

Antes de usar en producción:

- [ ] Dependencias instaladas (`pip install ...`)
- [ ] Variables de entorno configuradas (`.env`)
- [ ] Migraciones aplicadas (`python manage.py migrate`)
- [ ] Azure Blob Storage configurado y accesible
- [ ] Al menos 3-5 semillas creadas
- [ ] Primera prueba de procesamiento exitosa
- [ ] Celery workers corriendo (para tareas asíncronas)
- [ ] Verificar permisos de escritura en Azure Storage

---

**¡Sistema listo para capturar y almacenar contenido crudo! 🎉**
