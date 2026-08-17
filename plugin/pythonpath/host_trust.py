"""
Trusted-host checking for the MCP HTTP bridge (ai_interface.py).

Split out of ai_interface.py so it can be unit-tested without a live UNO
context -- ai_interface.py itself is only importable inside LibreOffice
(it imports mcp_server -> uno_bridge -> uno), but this module has no such
dependency.

v1.0.0 has no authentication: any process that can reach the HTTP port can
call every tool. TRUSTED_HOSTNAMES is the only thing standing between that
(intended for a trusted-localhost-only interface) and a DNS-rebinding
attack, where a browser page for an attacker-controlled domain that
resolves to 127.0.0.1 issues requests carrying that domain in the Host/
Origin header instead of "localhost"/"127.0.0.1".
"""

from typing import Optional
from urllib.parse import urlparse

TRUSTED_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def is_trusted_host(header_value: Optional[str]) -> bool:
    """Return True if a Host/Origin header names an allowed local address.

    Accepts both a bare Host-header value ("localhost:8765") and a full
    Origin value with scheme ("http://localhost:8765"); strips the scheme,
    a trailing port, and IPv6 brackets before comparing against
    TRUSTED_HOSTNAMES. Missing/unparseable headers are rejected.
    """
    if not header_value:
        return False
    hostname = urlparse(header_value if "//" in header_value else f"//{header_value}").hostname
    return hostname in TRUSTED_HOSTNAMES
