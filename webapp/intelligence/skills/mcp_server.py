"""
MCP Server para Skills.

Servidor MCP (Model Context Protocol) que expone skills como herramientas.
Permite que clientes externos (como VS Code, Claude, etc.) usen las skills del sistema.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from mcp import Tool
from mcp.server import Server
from mcp.types import (
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

from ..services.skill_base import SkillResult
from ..services.metrics import log
from .orchestrator import SkillOrchestrator, ExecutionContext


@dataclass
class MCPTool:
    """Herramienta MCP que envuelve una skill."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    skill_name: str

    def to_mcp_tool(self) -> Tool:
        """Convierte a objeto Tool de MCP."""
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema
        )


class MCPSkillServer:
    """
    Servidor MCP que expone skills como herramientas.

    Permite integración con:
    - VS Code extensions
    - Claude Desktop
    - Otros clientes MCP

    Arquitectura:
    - Skills se convierten automáticamente en herramientas MCP
    - Parámetros se mapean a schemas JSON
    - Resultados se convierten a contenido MCP
    - Manejo de errores y logging integrado
    """

    def __init__(self, orchestrator: SkillOrchestrator):
        """
        Inicializa el servidor MCP.

        Args:
            orchestrator: SkillOrchestrator para ejecutar skills
        """
        self.orchestrator = orchestrator
        self.server = Server("prometeo-skills")

        # Registrar handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Configura los handlers MCP."""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """Lista todas las skills disponibles como herramientas."""
            try:
                skills = self.orchestrator.list_available_skills()
                tools = []

                for skill_info in skills:
                    tool = self._skill_to_mcp_tool(skill_info)
                    if tool:
                        tools.append(tool.to_mcp_tool())

                log.info(f"Listado {len(tools)} herramientas MCP")
                return [tool.to_mcp_tool() for tool in tools if tool]

            except Exception as e:
                log.error(f"Error listando herramientas: {e}")
                return []

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent | ImageContent | EmbeddedResource]:
            """Ejecuta una skill a través de MCP."""
            try:
                log.info(f"Ejecutando herramienta MCP: {name}", arguments=arguments)

                # Mapear nombre de herramienta a nombre de skill
                skill_name = self._tool_name_to_skill_name(name)

                # Crear contexto de ejecución
                context = ExecutionContext(
                    user_id="mcp_client",
                    session_id=f"mcp_{name}",
                    environment="mcp"
                )

                # Ejecutar skill
                result = self.orchestrator.execute_skill(
                    skill_name=skill_name,
                    parameters=arguments,
                    context=context
                )

                # Convertir resultado a contenido MCP
                content = self._result_to_mcp_content(result)

                log.info(f"Herramienta MCP ejecutada: {name}, éxito: {result.success}")
                return content

            except Exception as e:
                log.error(f"Error ejecutando herramienta MCP {name}: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error interno: {str(e)}"
                    )
                ]

        @self.server.set_logging_level()
        async def handle_set_logging_level(level: LoggingLevel) -> None:
            """Configura nivel de logging."""
            # Mapear niveles MCP a niveles Python
            level_map = {
                LoggingLevel.DEBUG: "DEBUG",
                LoggingLevel.INFO: "INFO",
                LoggingLevel.WARNING: "WARNING",
                LoggingLevel.ERROR: "ERROR",
                LoggingLevel.CRITICAL: "CRITICAL"
            }

            log_level = level_map.get(level, "INFO")
            log.info(f"Nivel de logging MCP configurado: {log_level}")

    def _skill_to_mcp_tool(self, skill_info: Dict[str, Any]) -> Optional[MCPTool]:
        """
        Convierte información de skill a herramienta MCP.

        Args:
            skill_info: Información de la skill desde el registry

        Returns:
            MCPTool o None si no se puede convertir
        """
        try:
            name = skill_info.get('name', '')
            description = skill_info.get('description', '')
            parameters = skill_info.get('parameters', {})

            if not name or not description:
                return None

            # Crear schema JSON para parámetros
            input_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }

            for param_name, param_info in parameters.items():
                param_schema = {
                    "type": self._map_type_to_json_schema(param_info.get('type', 'str')),
                    "description": param_info.get('description', ''),
                }

                # Agregar opciones si existen
                if param_info.get('options'):
                    param_schema["enum"] = param_info['options']

                # Agregar valor por defecto si existe
                if param_info.get('default') is not None:
                    param_schema["default"] = param_info['default']

                input_schema["properties"][param_name] = param_schema

                # Agregar a required si es requerido
                if param_info.get('required', True):
                    input_schema["required"].append(param_name)

            return MCPTool(
                name=self._skill_name_to_tool_name(name),
                description=description,
                input_schema=input_schema,
                skill_name=name
            )

        except Exception as e:
            log.warning(f"Error convirtiendo skill {skill_info.get('name')} a herramienta MCP: {e}")
            return None

    def _skill_name_to_tool_name(self, skill_name: str) -> str:
        """Convierte nombre de skill a nombre de herramienta MCP."""
        # Reemplazar caracteres no válidos para nombres de herramientas
        return skill_name.replace('_', '-').replace(' ', '-').lower()

    def _tool_name_to_skill_name(self, tool_name: str) -> str:
        """Convierte nombre de herramienta MCP a nombre de skill."""
        return tool_name.replace('-', '_')

    def _map_type_to_json_schema(self, skill_type: str) -> str:
        """Mapea tipos de skill a tipos JSON Schema."""
        type_mapping = {
            'str': 'string',
            'int': 'integer',
            'float': 'number',
            'bool': 'boolean',
            'list': 'array',
            'dict': 'object'
        }
        return type_mapping.get(skill_type, 'string')

    def _result_to_mcp_content(self, result: SkillResult) -> List[TextContent | ImageContent | EmbeddedResource]:
        """
        Convierte resultado de skill a contenido MCP.

        Args:
            result: Resultado de la skill

        Returns:
            Lista de contenido MCP
        """
        content = []

        if result.success:
            # Resultado exitoso
            if result.data:
                # Formatear datos como JSON
                try:
                    data_text = json.dumps(result.data, indent=2, ensure_ascii=False)
                    content.append(TextContent(
                        type="text",
                        text=f"Resultado:\n{data_text}"
                    ))
                except Exception as e:
                    content.append(TextContent(
                        type="text",
                        text=f"Resultado: {str(result.data)}"
                    ))

            # Agregar metadata si existe
            if result.metadata:
                try:
                    meta_text = json.dumps(result.metadata, indent=2, ensure_ascii=False)
                    content.append(TextContent(
                        type="text",
                        text=f"Metadata:\n{meta_text}"
                    ))
                except Exception as e:
                    content.append(TextContent(
                        type="text",
                        text=f"Metadata: {str(result.metadata)}"
                    ))

            # Si no hay datos ni metadata, mensaje genérico
            if not result.data and not result.metadata:
                content.append(TextContent(
                    type="text",
                    text="Operación completada exitosamente"
                ))

        else:
            # Resultado con error
            error_text = result.error or "Error desconocido"
            content.append(TextContent(
                type="text",
                text=f"Error: {error_text}"
            ))

            # Incluir metadata de error si existe
            if result.metadata:
                try:
                    meta_text = json.dumps(result.metadata, indent=2, ensure_ascii=False)
                    content.append(TextContent(
                        type="text",
                        text=f"Detalles del error:\n{meta_text}"
                    ))
                except Exception as e:
                    content.append(TextContent(
                        type="text",
                        text=f"Detalles del error: {str(result.metadata)}"
                    ))

        return content

    async def serve_stdio(self):
        """Ejecuta el servidor en modo stdio (para integración con clientes MCP)."""
        log.info("Iniciando servidor MCP en modo stdio")

        try:
            async with self.server:
                await self.server.serve_stdio()
        except KeyboardInterrupt:
            log.info("Servidor MCP detenido por usuario")
        except Exception as e:
            log.error(f"Error en servidor MCP: {e}")
            raise

    def run_stdio(self):
        """Ejecuta el servidor de forma síncrona."""
        asyncio.run(self.serve_stdio())


# Función de conveniencia para crear y ejecutar servidor
def create_mcp_server(orchestrator: SkillOrchestrator) -> MCPSkillServer:
    """
    Crea un servidor MCP con el orchestrator dado.

    Args:
        orchestrator: SkillOrchestrator configurado

    Returns:
        Servidor MCP listo para usar
    """
    return MCPSkillServer(orchestrator)


# Para ejecutar como script independiente
if __name__ == "__main__":
    # Aquí iría la lógica para inicializar el orchestrator
    # y ejecutar el servidor cuando se llame como script
    print("Servidor MCP para Skills - ejecutar desde aplicación principal")