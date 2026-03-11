import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Crear servidor
const server = new Server(
  {
    name: "test-server",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);

// Intentar agregar una herramienta
// Necesito verificar los métodos disponibles
console.log("Server methods:", Object.getOwnPropertyNames(Object.getPrototypeOf(server)));

// Buscar método 'tool' o similar
const serverProto = Object.getPrototypeOf(server);
for (const key of Object.getOwnPropertyNames(serverProto)) {
  console.log(`- ${key}:`, typeof serverProto[key]);
}

// Verificar si hay un método 'registerTool' o similar
console.log("\nChecking for tool registration methods...");