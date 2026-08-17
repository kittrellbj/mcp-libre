"""
Tool registry helpers for the MCP tooling scaffold.

Provides a lightweight decorator-based registry so each stub module can
declare its tools next to their implementation, matching the
{name: {description, parameters, handler}} shape that
plugin/pythonpath/mcp_server.py already uses for the original 32 tools
(see LibreOfficeMCPServer._register_tools). Senior engineers wire a
module's registrations into the live server with merge_into() once the
stub bodies are implemented.

Every registration carries a `status`: "stub" (default -- body returns
envelope.build_not_implemented(), not advertised by default) or
"implemented" (body has real logic backed by live UNO/server state,
advertised unconditionally like the original 32). mcp_server.py merges
these two groups separately -- see _register_implemented_scaffold_tools()
and _register_scaffold_stub_tools().
"""

from typing import Any, Callable, Dict, List, Optional

# Populated by @register_tool as stub modules are imported. Keyed by exact
# MCP tool name; must match LibreOffice_MCP_Complete_Tooling_Specification.md.
_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}

VALID_STATUSES = frozenset({"stub", "implemented"})


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


def register_tool(name: str, priority: str, purpose: str, parameters: Optional[Dict[str, Any]] = None,
                   status: str = "stub") -> Callable:
    """Decorator that records a tool's MCP metadata and registers its handler.

    Args:
        name: MCP tool name; must match the design spec exactly (e.g. "ping_live").
        priority: Spec priority tag ("P0" through "P3").
        purpose: One-line purpose copied from the spec's Purpose column.
        parameters: JSON Schema `parameters` object, normally built with schema().
            Defaults to an empty-object schema when the tool takes no arguments.
        status: "stub" (default) or "implemented" -- see module docstring.

    Returns:
        A decorator that registers the wrapped function unmodified.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown status '{status}' for tool '{name}', expected one of {sorted(VALID_STATUSES)}")
    param_schema = parameters if parameters is not None else schema()

    def decorator(handler: Callable) -> Callable:
        if name in _TOOL_REGISTRY:
            raise ValueError(f"Duplicate tool registration for '{name}'")
        _TOOL_REGISTRY[name] = {
            "description": purpose,
            "parameters": param_schema,
            "priority": priority,
            "status": status,
            "handler": handler,
        }
        return handler

    return decorator


def get_registry(status: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Return the accumulated {tool_name: metadata} registry built so far.

    Args:
        status: When given ("stub" or "implemented"), only tools with that
            status are returned.

    Every stub module under plugin/pythonpath/tools/ must be imported before
    calling this, since registration happens at module import time --
    importing plugin.pythonpath.tools (the package __init__) does this.
    """
    if status is None:
        return dict(_TOOL_REGISTRY)
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown status '{status}', expected one of {sorted(VALID_STATUSES)}")
    return {name: meta for name, meta in _TOOL_REGISTRY.items() if meta["status"] == status}


def merge_into(existing_tools: Dict[str, Dict[str, Any]], overwrite: bool = False,
               registry: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
    """Merge a tool registry into a live server's tool dict.

    Args:
        existing_tools: The target dict, e.g. LibreOfficeMCPServer.tools.
        overwrite: When False (default), a name collision with an existing
            entry is skipped so the original 32 compatibility tools are
            never replaced by a scaffold stub.
        registry: The source {tool_name: metadata} mapping to merge from.
            Defaults to the full module registry; pass get_registry(status=...)
            to merge only implemented or only stub tools.

    Returns:
        The list of tool names actually added.
    """
    source = registry if registry is not None else _TOOL_REGISTRY
    added = []
    for tool_name, metadata in source.items():
        if tool_name in existing_tools and not overwrite:
            continue
        existing_tools[tool_name] = {
            "description": metadata["description"],
            "parameters": metadata["parameters"],
            "handler": metadata["handler"],
        }
        added.append(tool_name)
    return added
