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

// Register a tool using setRequestHandler
// We need to understand the correct schema for tool calls
// For now, create a simple ping tool

const ToolCallSchema = z.object({
  method: z.literal("tools/call"),
  params: z.object({
    name: z.string(),
    arguments: z.record(z.any()),
  }),
});

server.setRequestHandler(ToolCallSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  if (name === "extraer_datos_requerimiento") {
    const texto = args.texto as string;
    // Simple extraction logic
    const response = await deepseekApi.post("/chat/completions", {
      model: "deepseek-chat",
      messages: [
        { role: "system", content: "Extrae datos estructurados del texto." },
        { role: "user", content: `Extrae datos de: ${texto}` }
      ],
      temperature: 0.1,
      max_tokens: 500,
    });
    
    const content = response.data.choices[0].message.content;
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ extracted: content }, null, 2),
        },
      ],
    };
  }
  
  throw new Error(`Unknown tool: ${name}`);
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