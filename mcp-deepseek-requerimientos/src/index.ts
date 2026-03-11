#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import axios from "axios";

const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY;
if (!DEEPSEEK_API_KEY) {
  throw new Error("DEEPSEEK_API_KEY environment variable is required");
}

// Create an MCP server
const server = new Server(
  {
    name: "deepseek-requerimientos",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);

// DeepSeek API client
const deepseekApi = axios.create({
  baseURL: "https://api.deepseek.com",
  headers: {
    "Authorization": `Bearer ${DEEPSEEK_API_KEY}`,
    "Content-Type": "application/json",
  },
});

// Schema for tool calls
const ToolCallSchema = z.object({
  method: z.literal("tools/call"),
  params: z.object({
    name: z.string(),
    arguments: z.record(z.any()),
  }),
});

// Helper function to call DeepSeek API
async function callDeepSeek(prompt: string, systemPrompt: string = "Eres un asistente especializado en extracción estructurada de datos de textos inmobiliarios. Siempre respondes con JSON válido.") {
  const response = await deepseekApi.post("/chat/completions", {
    model: "deepseek-chat",
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: prompt }
    ],
    temperature: 0.1,
    max_tokens: 1000,
  });
  return response.data.choices[0].message.content;
}

// Helper to extract JSON from response
function extractJSON(content: string): any {
  try {
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    } else {
      return { error: "No se pudo extraer JSON", raw: content };
    }
  } catch (error) {
    return { error: "Error parseando JSON", raw: content };
  }
}

// Register tool handler
server.setRequestHandler(ToolCallSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  try {
    if (name === "extraer_datos_requerimiento") {
      const texto = args.texto as string;
      const camposSolicitados = args.campos_solicitados as string[] | undefined;
      
      const prompt = `Eres un experto en extracción de datos de requerimientos inmobiliarios. Extrae la información estructurada del siguiente texto y devuélvela en formato JSON válido.

Texto del requerimiento:
${texto}

Campos a extraer (si están presentes en el texto):
${camposSolicitados ? camposSolicitados.join(", ") : "presupuesto, tipo_inmueble, ubicacion, zonas_interes, banos, habitaciones, contacto, cliente, estado_credito, moneda, fecha_requerimiento, notas"}

Instrucciones:
1. Extrae solo los datos que aparecen explícitamente en el texto.
2. Si un campo no está presente, omítelo del JSON.
3. Convierte valores monetarios a números (ej: "USD 130,000" → 130000).
4. Normaliza tipos de inmueble: "Departamento", "Casa", "Oficina", "Local", "Terreno".
5. Para ubicaciones, extrae distrito, ciudad, departamento si están mencionados.
6. Para contactos, extrae teléfono y nombre si están presentes.
7. Devuelve un objeto JSON con los campos extraídos.

Respuesta debe ser SOLO el JSON, sin explicaciones.`;

      const content = await callDeepSeek(prompt);
      const datosExtraidos = extractJSON(content);
      
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(datosExtraidos, null, 2),
          },
        ],
      };
    }
    
    else if (name === "sugerir_campos_desde_muestra") {
      const nombreColumna = args.nombre_columna as string;
      const valoresMuestra = args.valores_muestra as string[];
      
      const prompt = `Analiza los siguientes valores de una columna de Excel y sugiere:
1. Nombre de campo en snake_case apropiado para base de datos
2. Tipo de dato (string, integer, decimal, boolean, date)
3. Descripción del campo
4. Ejemplo de valor normalizado

Nombre de columna: ${nombreColumna}
Valores de muestra: ${JSON.stringify(valoresMuestra)}

Responde en formato JSON con esta estructura:
{
  "nombre_campo": "string",
  "tipo_dato": "string",
  "descripcion": "string",
  "ejemplo_normalizado": "any"
}`;

      const content = await callDeepSeek(prompt, "Eres un experto en diseño de bases de datos y normalización de datos. Siempre respondes con JSON válido.");
      const sugerencia = extractJSON(content);
      
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(sugerencia, null, 2),
          },
        ],
      };
    }
    
    else if (name === "mapear_columna_inteligente") {
      const nombreColumnaExcel = args.nombre_columna_excel as string;
      const valoresCompletos = args.valores_completos as string[];
      const contexto = args.contexto as string | undefined;
      
      const prompt = `Dada una columna de Excel con el nombre "${nombreColumnaExcel}" y los siguientes valores:
${JSON.stringify(valoresCompletos.slice(0, 20), null, 2)} ${valoresCompletos.length > 20 ? `\n(Total: ${valoresCompletos.length} valores, mostrando primeros 20)` : ''}

${contexto ? `Contexto: ${contexto}` : 'Contexto: Requerimientos inmobiliarios'}

Analiza y proporciona:
1. Qué tipo de información contiene esta columna
2. Cómo debería mapearse a campos de base de datos (sugiere 1-3 campos posibles)
3. Reglas de transformación para normalizar los datos
4. Posibles problemas de calidad de datos detectados

Responde en formato JSON con esta estructura:
{
  "analisis": "string",
  "campos_sugeridos": [
    {
      "nombre_campo": "string",
      "tipo_dato": "string",
      "descripcion": "string",
      "ejemplo_transformado": "any"
    }
  ],
  "reglas_transformacion": ["string"],
  "problemas_detectados": ["string"],
  "recomendacion_mapeo": "string"
}`;

      const content = await callDeepSeek(prompt, "Eres un experto en análisis de datos y mapeo de columnas de Excel a esquemas de base de datos.");
      const analisis = extractJSON(content);
      
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(analisis, null, 2),
          },
        ],
      };
    }
    
    else if (name === "validar_datos_extraidos") {
      const datosExtraidos = args.datos_extraidos as Record<string, any>;
      const esquemaEsperado = args.esquema_esperado as Record<string, string> | undefined;
      
      const prompt = `Valida y limpia los siguientes datos extraídos de un requerimiento inmobiliario:

Datos extraídos:
${JSON.stringify(datosExtraidos, null, 2)}

${esquemaEsperado ? `Esquema esperado: ${JSON.stringify(esquemaEsperado)}` : 'Esquema esperado: Campos comunes de requerimientos inmobiliarios'}

Realiza:
1. Validación de tipos de datos
2. Normalización de formatos (moneda, fechas, etc.)
3. Detección de valores inconsistentes o imposibles
4. Sugerencias de corrección

Responde en formato JSON con esta estructura:
{
  "datos_validados": { ... },
  "problemas": ["string"],
  "correcciones_aplicadas": ["string"],
  "campos_faltantes": ["string"],
  "score_calidad": 0-100
}`;

      const content = await callDeepSeek(prompt, "Eres un validador de datos especializado en información inmobiliaria.");
      const validacion = extractJSON(content);
      
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(validacion, null, 2),
          },
        ],
      };
    }
    
    else {
      throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    if (axios.isAxiosError(error)) {
      return {
        content: [
          {
            type: "text",
            text: `Error de API DeepSeek: ${error.response?.data?.message || error.message}`,
          },
        ],
        isError: true,
      };
    }
    throw error;
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("DeepSeek Requerimientos MCP server running on stdio");
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});