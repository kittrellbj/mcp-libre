"""
Response envelope helpers implementing the tool contract from
LibreOffice_MCP_Complete_Tooling_Specification.md section 5
("Required return/error contract").

Every mutating (and, per section 2, every) tool response should be built
with build_success()/build_error() so the shape stays uniform:

    {success, result?, warnings?, error?, document_id, elapsed_ms}
"""

import time
from typing import Any, Dict, List, Optional

# Stable error codes from spec section 5. NOT_IMPLEMENTED is a scaffold-only
# addition for stub tools -- it is not part of the spec's official contract.
# Replace it with a real spec code once a tool is implemented.
ERROR_CODES = frozenset({
    "NO_ACTIVE_DOCUMENT",
    "WRONG_DOCUMENT_TYPE",
    "OBJECT_NOT_FOUND",
    "AMBIGUOUS_SELECTOR",
    "UNSUPPORTED_CAPABILITY",
    "INVALID_RANGE",
    "INVALID_PARAMETER",
    "FILE_EXISTS",
    "PERMISSION_DENIED",
    "UNO_EXCEPTION",
    "DATABASE_ERROR",
    "TIMEOUT",
    "SECURITY_POLICY_DENIED",
    "NOT_IMPLEMENTED",
})


def start_timer() -> float:
    """Return a monotonic start time for elapsed_ms measurement."""
    return time.monotonic()


def elapsed_ms_since(start_time: float) -> int:
    """Return whole milliseconds elapsed since start_time."""
    return int((time.monotonic() - start_time) * 1000)


def build_success(result: Any = None, document_id: Optional[str] = None,
                   warnings: Optional[List[str]] = None,
                   elapsed_ms: Optional[int] = None) -> Dict[str, Any]:
    """Build the spec's success envelope.

    Args:
        result: Tool-specific payload; defaults to an empty object.
        document_id: The resolved document the operation applied to, if any.
        warnings: Non-fatal warnings surfaced alongside a successful result.
        elapsed_ms: Server-measured duration; pass elapsed_ms_since(start_timer()).
    """
    return {
        "success": True,
        "result": result if result is not None else {},
        "warnings": warnings or [],
        "document_id": document_id,
        "elapsed_ms": elapsed_ms if elapsed_ms is not None else 0,
    }


def build_error(code: str, message: str, document_id: Optional[str] = None,
                 elapsed_ms: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the spec's error envelope.

    Args:
        code: One of ERROR_CODES.
        message: Human-readable summary; include original UNO exception text
            in `details`, not folded into this message (spec section 5).
        document_id: The resolved document, if any, at the point of failure.
        elapsed_ms: Server-measured duration; pass elapsed_ms_since(start_timer()).
        details: Structured diagnostic payload (e.g. {"uno_exception": "..."}).
    """
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code '{code}', expected one of {sorted(ERROR_CODES)}")
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details or {}},
        "warnings": [],
        "document_id": document_id,
        "elapsed_ms": elapsed_ms if elapsed_ms is not None else 0,
    }


def build_not_implemented(tool_name: str, start_time: Optional[float] = None) -> Dict[str, Any]:
    """Standard stub response for a scaffolded-but-unimplemented tool."""
    return build_error(
        "NOT_IMPLEMENTED",
        f"'{tool_name}' is scaffolded but not yet implemented. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.",
        elapsed_ms=elapsed_ms_since(start_time) if start_time is not None else 0,
    )
