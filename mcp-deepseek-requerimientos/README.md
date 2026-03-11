# MCP Server: DeepSeek Requerimientos

Servidor MCP (Model Context Protocol) para extracción inteligente de datos de requerimientos inmobiliarios utilizando la API de DeepSeek.

## Características

- **Extracción estructurada de textos no estructurados**: Analiza textos como "🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 ..." y extrae campos como presupuesto, tipo de inmueble, ubicación, etc.
- **Sugerencia de campos dinámicos**: Analiza columnas de Excel y sugiere nombres de campos, tipos de datos y reglas de transformación.
- **Validación de datos**: Valida y limpia datos extraídos, detectando inconsistencias.
- **Integración con Django**: Clase `ExtractorInteligenteRequerimientos` para usar directamente en el módulo de requerimientos.

## Herramientas disponibles

1. **extraer_datos_requerimiento**: Extrae datos estructurados de un texto no estructurado.
2. **sugerir_campos_desde_muestra**: Sugiere campos basados en valores de muestra de una columna.
3. **mapear_columna_inteligente**: Analiza una columna completa y sugiere mapeos a campos de base de datos.
4. **validar_datos_extraidos**: Valida y limpia datos extraídos.

## Configuración

### 1. Instalación

```bash
cd mcp-deepseek-requerimientos
npm install
npm run build
```

### 2. Configurar API Key

La API key de DeepSeek se configura en el archivo `mcp_settings.json`:

```json
{
  "mcpServers": {
    "deepseek-requerimientos": {
      "command": "node",
      "args": ["D:/proyectos/prometeo/mcp-deepseek-requerimientos/build/index.js"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-460d28e38c7e4b05a13fa2bebd27159c"
      }
    }
  }
}
```

### 3. Integración con Django

El módulo `requerimientos` ahora incluye la clase `ExtractorInteligenteRequerimientos` en `services.py` que permite:

```python
from requerimientos.services import ExtractorInteligenteRequerimientos

# Extraer datos de un texto
texto = "🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 ..."
datos = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto)

# Procesar una columna de Excel
resultado = ExtractorInteligenteRequerimientos.procesar_columna_texto(df, "detalle_requerimiento")
```

## Uso del MCP Server

Una vez configurado en Roo Code, las herramientas estarán disponibles para su uso a través del agente.

### Ejemplo de uso con el agente:

```
Usa la herramienta "extraer_datos_requerimiento" para analizar este texto: "🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 🔎 Cliente bien filtrado 🏦 Crédito hipotecario aprobado 💰 Presupuesto: hasta USD 130,000 📍 Zonas de interés: ✔️ Michell ✔️ La Pradera ✔️ Casa Bella ✔️ La Fonda 🏠 Tipo de inmueble: Departamento 🤝 Cliente listo para comprar – cierre inmediato 📲 Propietarios y colegas inmobiliarios: Enviar propuestas con precio, ubicación, metraje y fotos. 👉📲995880505 Elby Bouroncle"
```

## Estructura del proyecto

```
mcp-deepseek-requerimientos/
├── src/
│   └── index.ts          # Implementación del servidor MCP
├── build/
│   └── index.js          # Código compilado
├── package.json          # Dependencias
├── tsconfig.json         # Configuración TypeScript
└── README.md             # Este archivo
```

## Notas importantes

- La API key de DeepSeek está embebida en el código; en producción debería manejarse mediante variables de entorno.
- El servidor MCP usa el SDK versión 0.6.1, que tiene una API diferente a versiones anteriores.
- La integración con Django permite usar la extracción inteligente directamente en el proceso de importación de Excel.