import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

console.log("Server:", Server);
console.log("StdioServerTransport:", StdioServerTransport);
console.log("z:", z);

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

console.log("Server created successfully");