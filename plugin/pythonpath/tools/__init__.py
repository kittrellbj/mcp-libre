"""
LibreOffice MCP Extension - tooling scaffold.

This package holds stub implementations for the tool catalog defined in
LibreOffice_MCP_Complete_Tooling_Specification.md. Currently covers
Implementation Phase A ("Runtime hardening and common document API":
discovery, handles, lifecycle, undo, styles), Phase B - Writer complete
(text/navigation/editing, page layout/publishing, tables/sections/notes),
Phase C - shared drawing/charts + Calc-complete (common drawing objects
and embedded objects; charts and data visualizations; Calc sheets/cells/
ranges/formulas/layout; Calc data management/pivots/validation/external
data; Calc page setup/print/annotations/protection), and Phase D - Impress
and Draw (slides/masters/notes/transitions/animations/slideshow; Draw
pages/masters/layers/vector operations). See
docs/MCP_TOOLING_SCAFFOLD_PLAN.md for the full 484-tool roadmap and what
remains for later phases.

Every tool in this package is a stub: it is registered with the correct
name, priority, and parameter schema, but its body raises no UNO calls and
returns a NOT_IMPLEMENTED response (see .envelope.build_not_implemented).
A senior engineer replaces each stub body with real uno_bridge.UNOBridge
logic; the surrounding scaffolding (registration, response envelope,
document handle contract) is meant to stay as-is.

Nothing here is wired into the live server by default. See registry.py's
merge_into() and mcp_server.py's `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS` opt-in
for how a senior engineer turns this on for local testing.
"""

from . import core_runtime  # noqa: F401  (imported for @register_tool side effects)
from . import document_lifecycle  # noqa: F401
from . import undo_view_selection  # noqa: F401
from . import styles  # noqa: F401
from . import writer_text  # noqa: F401
from . import writer_layout  # noqa: F401
from . import writer_tables  # noqa: F401
from . import drawing_objects  # noqa: F401
from . import charts  # noqa: F401
from . import calc_sheets  # noqa: F401
from . import calc_data  # noqa: F401
from . import calc_page  # noqa: F401
from . import impress  # noqa: F401
from . import draw  # noqa: F401
from .registry import get_registry, merge_into

__all__ = ["get_registry", "merge_into"]
