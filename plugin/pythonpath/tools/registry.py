"""
Tool registry helpers for the MCP tooling scaffold.

Provides a lightweight decorator-based registry so each stub module can
declare its tools next to their implementation, matching the
{name: {description, parameters, handler}} shape that
plugin/pythonpath/mcp_server.py already uses for the original 32 tools
(see LibreOfficeMCPServer._register_tools). Senior engineers wire a
module's registrations into the live server with merge_into() once the
stub bodies are implemented.
"""

from typing import Any, Callable, Dict, List, Optional

# Populated by @register_tool as stub modules are imported. Keyed by exact
# MCP tool name; must match LibreOffice_MCP_Complete_Tooling_Specification.md.
_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def schema(properties: Optional[Dict[str, Any]] = None, required: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build a minimal JSON Schema `parameters` object for register_tool.

    Args:
        properties: JSON Schema `properties` map, one entry per parameter.
        required: Names of required properties, if any.
    """
    built: Dict[str, Any] = {"type": "object", "properties": properties or {}}
    if required:
        built["required"] = required
    return built


def register_tool(name: str, priority: str, purpose: str, parameters: Optional[Dict[str, Any]] = None) -> Callable:
    """Decorator that records a tool's MCP metadata and registers its handler.

    Args:
        name: MCP tool name; must match the design spec exactly (e.g. "ping_live").
        priority: Spec priority tag ("P0" through "P3").
        purpose: One-line purpose copied from the spec's Purpose column.
        parameters: JSON Schema `parameters` object, normally built with schema().
            Defaults to an empty-object schema when the tool takes no arguments.

    Returns:
        A decorator that registers the wrapped function unmodified.
    """
    param_schema = parameters if parameters is not None else schema()

    def decorator(handler: Callable) -> Callable:
        if name in _TOOL_REGISTRY:
            raise ValueError(f"Duplicate tool registration for '{name}'")
        _TOOL_REGISTRY[name] = {
            "description": purpose,
            "parameters": param_schema,
            "priority": priority,
            "handler": handler,
        }
        return handler

    return decorator


def get_registry() -> Dict[str, Dict[str, Any]]:
    """Return the accumulated {tool_name: metadata} registry built so far.

    Every stub module under plugin/pythonpath/tools/ must be imported before
    calling this, since registration happens at module import time --
    importing plugin.pythonpath.tools (the package __init__) does this.
    """
    return dict(_TOOL_REGISTRY)


def merge_into(existing_tools: Dict[str, Dict[str, Any]], overwrite: bool = False) -> List[str]:
    """Merge the scaffold registry into a live server's tool dict.

    Args:
        existing_tools: The target dict, e.g. LibreOfficeMCPServer.tools.
        overwrite: When False (default), a name collision with an existing
            entry is skipped so the original 32 compatibility tools are
            never replaced by a scaffold stub.

    Returns:
        The list of tool names actually added.
    """
    added = []
    for tool_name, metadata in _TOOL_REGISTRY.items():
        if tool_name in existing_tools and not overwrite:
            continue
        existing_tools[tool_name] = {
            "description": metadata["description"],
            "parameters": metadata["parameters"],
            "handler": metadata["handler"],
        }
        added.append(tool_name)
    return added
