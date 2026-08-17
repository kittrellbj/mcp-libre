"""
LibreOffice MCP Extension - AI Interface Module

This module provides an HTTP API interface for external AI assistants to
communicate with the LibreOffice MCP server.
"""

import asyncio
import inspect
import json
import logging
import socketserver
import threading
import uuid
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict
from urllib.parse import urlparse

import mcp_jsonrpc
import mcp_server
from host_trust import is_trusted_host

# Real MCP JSON-RPC 2.0 endpoint (mandated item #4) accepts POSTs on any
# of these paths -- /mcp is the canonical Streamable HTTP route; /sse and
# /messages are aliases for MCP clients hardcoded to the older
# split-SSE-transport path names, dispatched through the exact same
# handler (see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's transport pass).
MCP_JSONRPC_PATHS = ("/mcp", "/sse", "/messages")


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    """Threaded TCP server suitable for the embedded MCP HTTP API."""

    allow_reuse_address = True
    daemon_threads = True


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP API."""

    def __init__(self, *args, **kwargs):
        self.mcp_server = mcp_server.get_mcp_server()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        logger.info(f"HTTP GET {path}")

        if not self._reject_untrusted_host():
            return

        try:
            if path == "/":
                self._send_response(
                    200,
                    self._get_server_info()
                )

            elif path == "/tools":
                self._send_response(
                    200,
                    self._get_tools_list()
                )

            elif path == "/health":
                self._send_response(
                    200,
                    {
                        "status": "healthy",
                        "server": "LibreOffice MCP Extension"
                    }
                )

            elif path in MCP_JSONRPC_PATHS:
                # Streamable HTTP allows a server-initiated SSE stream on
                # GET; this server has nothing to push (no server-
                # initiated notifications), so per spec a server that
                # doesn't support that MAY reply 405 rather than
                # implementing an always-idle stream.
                self.send_response(405)
                self.send_header("Allow", "POST, DELETE, OPTIONS")
                self._send_cors_headers()
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

            else:
                self._send_response(
                    404,
                    {"error": "Not found"}
                )

        except (
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError
        ) as e:
            logger.warning(
                f"Client disconnected during GET {path}: {e}"
            )

        except Exception as e:
            logger.exception(
                f"Error handling GET {path}"
            )

            self._try_send_error_response(e)

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        logger.info(f"HTTP POST {path}")

        if not self._reject_untrusted_host():
            return

        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            if content_length > 0:
                raw_body = self.rfile.read(content_length)

                try:
                    body = raw_body.decode("utf-8")
                    data = json.loads(body)

                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError
                ):
                    if path in MCP_JSONRPC_PATHS:
                        # JSON-RPC 2.0 has its own reserved shape for this
                        # (id is necessarily null -- the request couldn't
                        # even be parsed far enough to find one).
                        self._send_json_rpc_response(
                            mcp_jsonrpc.build_error(None, mcp_jsonrpc.PARSE_ERROR, "Parse error: invalid JSON"),
                            400,
                        )
                    else:
                        self._send_response(
                            400,
                            {"error": "Invalid JSON"}
                        )
                    return

            else:
                data = {} if path not in MCP_JSONRPC_PATHS else None

            if path.startswith("/tools/"):
                tool_name = path[len("/tools/"):]

                if not tool_name:
                    self._send_response(
                        400,
                        {"error": "Missing tool name"}
                    )
                    return

                self._handle_tool_execution(
                    tool_name,
                    data
                )

            elif path == "/execute":
                if "tool" not in data:
                    self._send_response(
                        400,
                        {"error": "Missing 'tool' parameter"}
                    )
                    return

                tool_name = data["tool"]
                parameters = data.get(
                    "parameters",
                    {}
                )

                self._handle_tool_execution(
                    tool_name,
                    parameters
                )

            elif path in MCP_JSONRPC_PATHS:
                self._handle_mcp_jsonrpc(data)

            else:
                self._send_response(
                    404,
                    {"error": "Not found"}
                )

        except (
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError
        ) as e:
            logger.warning(
                f"Client disconnected during POST {path}: {e}"
            )

        except Exception as e:
            logger.exception(
                f"Error handling POST {path}"
            )

            self._try_send_error_response(e)

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        logger.info(f"HTTP OPTIONS {self.path}")

        if not self._reject_untrusted_host():
            return

        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

        self.close_connection = True

    def do_DELETE(self):
        """Handle DELETE requests -- only meaningful for /mcp session
        termination. This server has no per-session state to actually
        tear down yet (see _handle_mcp_jsonrpc()'s Mcp-Session-Id note),
        so this just acknowledges the client's intent to end the session
        rather than rejecting the request outright."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        logger.info(f"HTTP DELETE {path}")

        if not self._reject_untrusted_host():
            return

        if path in MCP_JSONRPC_PATHS:
            self._send_response(200, {"status": "session terminated"})
        else:
            self._send_response(404, {"error": "Not found"})

    def _reject_untrusted_host(self) -> bool:
        """Send 403 and return False for a request whose Host header isn't localhost.

        v1.0.0 has no authentication, so this is the only thing standing
        between "any localhost process can call every tool" (intended, see
        TRUSTED_HOSTNAMES) and a DNS-rebinding attack, where a page the
        browser navigated to for an attacker-controlled domain resolves
        that domain to 127.0.0.1 and issues requests carrying that domain
        in the Host header instead of "localhost"/"127.0.0.1". Callers
        should check this before doing any other request handling.
        """
        host_header = self.headers.get("Host")
        if is_trusted_host(host_header):
            return True
        logger.warning(f"Rejecting request with untrusted Host header: {host_header!r}")
        self._send_response(403, {"error": "Untrusted Host header; this server only accepts localhost requests"})
        return False

    def _execute_tool_sync(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Run self.mcp_server.execute_tool() to completion and return its
        result, whether execute_tool() is async (current implementation)
        or a future synchronous one. Shared by the REST bridge's
        _handle_tool_execution() and the real MCP JSON-RPC tools/call
        path (_handle_mcp_jsonrpc()) so there's exactly one place that
        knows how to run it."""
        result = self.mcp_server.execute_tool(tool_name, parameters)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        return result

    def _handle_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ):
        """Execute an MCP tool and return its result."""
        try:
            logger.info(
                f"HTTP tool execution starting: {tool_name}"
            )

            result = self._execute_tool_sync(tool_name, parameters)

            logger.info(
                f"HTTP tool execution completed: {tool_name}"
            )

            self._send_response(
                200,
                result
            )

        except (
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError
        ) as e:
            logger.warning(
                f"Client disconnected while executing "
                f"{tool_name}: {e}"
            )

        except Exception as e:
            logger.exception(
                f"Error executing tool {tool_name}"
            )

            self._try_send_error_response(
                e,
                tool_name=tool_name
            )

    def _handle_mcp_jsonrpc(self, data: Any):
        """Real MCP JSON-RPC 2.0 endpoint (mandated item #4) -- POST
        /mcp, /sse, /messages all land here. `data` is whatever
        json.loads() produced: a dict (single message), a list (JSON-RPC
        batch), or None (empty POST body, invalid for this endpoint).
        Message-level parsing/routing lives in mcp_jsonrpc.py, kept
        separate so it's unit-testable without an HTTP server or UNO;
        this method only handles the HTTP-transport concerns (session
        header, status code, response framing).
        """
        if data is None:
            self._send_json_rpc_response(
                mcp_jsonrpc.build_error(None, mcp_jsonrpc.INVALID_REQUEST, "Invalid Request: empty body"),
                400,
            )
            return

        is_initialize = isinstance(data, dict) and data.get("method") == "initialize"

        response_body, status = mcp_jsonrpc.dispatch(
            data,
            self.mcp_server.tools,
            self._execute_tool_sync,
        )

        # Mint an Mcp-Session-Id on initialize and echo it on every
        # response (including this one) -- permissive, not yet validated
        # against subsequent requests (see mcp_jsonrpc.py's module
        # docstring for the same scope note on protocol-version
        # negotiation). There is no per-session state to isolate today;
        # this exists so clients that expect the header to be present
        # get it, without this server pretending to enforce a guarantee
        # it doesn't actually provide yet.
        session_id = self.headers.get("Mcp-Session-Id")
        protocol_version = None
        if is_initialize and not session_id:
            session_id = uuid.uuid4().hex
        if is_initialize and isinstance(response_body, dict):
            protocol_version = (response_body.get("result") or {}).get("protocolVersion")

        self._send_json_rpc_response(response_body, status, session_id=session_id, protocol_version=protocol_version)

    def _send_json_rpc_response(self, body: Any, status: int, session_id: str = None, protocol_version: str = None):
        """Send a JSON-RPC response (or an empty 202/204 body) with the
        headers a Streamable HTTP MCP client expects."""
        if body is None:
            payload = b""
        else:
            payload = json.dumps(body, default=str).encode("utf-8")

        self.send_response(status)
        if payload:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        if protocol_version:
            self.send_header("Mcp-Protocol-Version", protocol_version)
        self._send_cors_headers()
        self.send_header("Connection", "close")
        self.end_headers()

        if payload:
            self.wfile.write(payload)
            self.wfile.flush()

        self.close_connection = True

    def _get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            "name": "LibreOffice MCP Extension",
            "version": "1.0.0",
            "description": (
                "LibreOffice-native HTTP tool bridge. POST /mcp is real MCP "
                "JSON-RPC 2.0 (Streamable HTTP, single-JSON-response mode); "
                "the GET/POST /tools, /execute endpoints are a separate, "
                "pre-existing custom REST API kept for backward compatibility."
            ),
            "endpoints": {
                "GET /": "Server information",
                "GET /tools": "List available tools (custom REST API)",
                "GET /health": "Health check",
                "POST /tools/{tool_name}": (
                    "Execute specific tool (custom REST API)"
                ),
                "POST /execute": (
                    "Execute tool specified in request body (custom REST API)"
                ),
                "POST /mcp": (
                    "Real MCP JSON-RPC 2.0 endpoint (initialize, tools/list, "
                    "tools/call, ping, resources/list, prompts/list). "
                    "/sse and /messages are aliases for the same handler."
                ),
                "GET /mcp": "405 (no server-initiated SSE stream)",
                "DELETE /mcp": "Acknowledge MCP session termination",
            },
            "tools_count": len(
                self.mcp_server.tools
            )
        }

    def _get_tools_list(self) -> Dict[str, Any]:
        """Get list of available tools."""
        tools = self.mcp_server.get_tool_list()

        logger.info(
            f"Returning {len(tools)} MCP tools"
        )

        return {
            "tools": tools,
            "count": len(tools)
        }

    def _send_response(
        self,
        status_code: int,
        data: Dict[str, Any]
    ):
        """Send a complete JSON HTTP response."""
        response = json.dumps(
            data,
            indent=2,
            default=str
        ).encode("utf-8")

        logger.debug(
            f"Sending HTTP {status_code}, "
            f"{len(response)} bytes"
        )

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(response))
        )

        self.send_header(
            "Connection",
            "close"
        )

        self._send_cors_headers()
        self.end_headers()

        if response:
            self.wfile.write(response)
            self.wfile.flush()

        self.close_connection = True

        logger.debug(
            f"HTTP {status_code} response completed"
        )

    def _try_send_error_response(
        self,
        error: Exception,
        tool_name: str = None
    ):
        """
        Attempt to return an error response without creating a second
        exception if the client has already disconnected.
        """
        data = {
            "success": False,
            "error": str(error)
        }

        if tool_name:
            data["tool"] = tool_name

        try:
            self._send_response(
                500,
                data
            )

        except (
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError
        ):
            logger.warning(
                "Unable to send error response because "
                "the client disconnected"
            )

    def _send_cors_headers(self):
        """Send CORS headers, scoped to a trusted local Origin instead of a wildcard.

        Only echoes back Origin values that pass _is_trusted_host() (i.e.
        localhost/127.0.0.1/::1, any scheme/port); an untrusted or missing
        Origin gets no Access-Control-Allow-Origin header at all, so a
        browser will block the cross-origin read. "*" is deliberately not
        used -- it would let any page in any origin call every tool with no
        authentication.
        """
        origin = self.headers.get("Origin")

        if is_trusted_host(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, DELETE, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, Mcp-Session-Id, Mcp-Protocol-Version"
        )

        # So a browser-hosted MCP client's JS can read these two
        # response headers on a cross-origin request -- without this,
        # CORS hides them even though Access-Control-Allow-Origin lets
        # the response body through.
        self.send_header(
            "Access-Control-Expose-Headers",
            "Mcp-Session-Id, Mcp-Protocol-Version"
        )

    def log_message(self, format, *args):
        """Route HTTP server logging through Python logging."""
        logger.info(
            f"{self.client_address[0]} - "
            f"{format % args}"
        )


class AIInterface:
    """
    Interface for AI assistants to communicate with the
    LibreOffice MCP server.
    """

    def __init__(
        self,
        port: int = 8765,
        host: str = "localhost"
    ):
        """
        Initialize the AI interface.

        Args:
            port: Port to listen on.
            host: Host to bind to.
        """
        self.port = port
        self.host = host
        self.server = None
        self.server_thread = None
        self.running = False

        logger.info(
            f"AI Interface initialized for "
            f"{host}:{port}"
        )

    def start(self):
        """Start the HTTP server."""
        try:
            if self.running:
                logger.warning(
                    "Server is already running"
                )
                return

            self.server = ReusableThreadingTCPServer(
                (self.host, self.port),
                MCPRequestHandler
            )

            self.running = True

            logger.info(
                f"Started MCP HTTP server on "
                f"{self.host}:{self.port}"
            )

            self.server_thread = threading.Thread(
                target=self._run_server,
                name="LibreOfficeMCPHTTPServer",
                daemon=True
            )

            self.server_thread.start()

            logger.info(
                "MCP HTTP server started successfully"
            )

        except Exception as e:
            logger.exception(
                f"Failed to start HTTP server: {e}"
            )

            self.running = False

            if self.server:
                try:
                    self.server.server_close()
                except Exception:
                    pass

                self.server = None

            raise

    def stop(self):
        """Stop the HTTP server."""
        try:
            if not self.running:
                logger.warning(
                    "Server is not running"
                )
                return

            self.running = False

            if self.server:
                logger.info(
                    "Stopping MCP HTTP server"
                )

                self.server.shutdown()
                self.server.server_close()
                self.server = None

            if (
                self.server_thread
                and self.server_thread.is_alive()
                and self.server_thread
                is not threading.current_thread()
            ):
                self.server_thread.join(
                    timeout=5
                )

            self.server_thread = None

            logger.info(
                "MCP HTTP server stopped"
            )

        except Exception as e:
            logger.exception(
                f"Error stopping HTTP server: {e}"
            )

    def _run_server(self):
        """Run the HTTP server."""
        try:
            logger.info(
                f"HTTP server listening on "
                f"{self.host}:{self.port}"
            )

            self.server.serve_forever(
                poll_interval=0.25
            )

        except Exception as e:
            if self.running:
                logger.exception(
                    f"HTTP server error: {e}"
                )

        finally:
            self.running = False

    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.running

    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "url": (
                f"http://{self.host}:{self.port}"
            ),
            "thread_alive": (
                self.server_thread.is_alive()
                if self.server_thread
                else False
            )
        }


# Global instance
ai_interface = None


def get_ai_interface(
    port: int = 8765,
    host: str = "localhost"
) -> AIInterface:
    """Get or create the global AI interface instance."""
    global ai_interface

    if ai_interface is None:
        ai_interface = AIInterface(
            port,
            host
        )

    return ai_interface


def start_ai_interface(
    port: int = 8765,
    host: str = "localhost"
) -> AIInterface:
    """Start the AI interface HTTP server."""
    interface = get_ai_interface(
        port,
        host
    )

    if not interface.is_running():
        interface.start()

    return interface


def stop_ai_interface():
    """Stop the AI interface HTTP server."""
    global ai_interface

    if ai_interface:
        ai_interface.stop()
        ai_interface = None