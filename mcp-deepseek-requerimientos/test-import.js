import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

console.log("Import test successful");
console.log("McpServer:", typeof McpServer);
console.log("StdioServerTransport:", typeof StdioServerTransport);
console.log("z:", typeof z);