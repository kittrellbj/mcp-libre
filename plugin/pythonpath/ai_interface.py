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
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict
from urllib.parse import urlparse

import mcp_server


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
                    self._send_response(
                        400,
                        {"error": "Invalid JSON"}
                    )
                    return

            else:
                data = {}

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

        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

        self.close_connection = True

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

            result = self.mcp_server.execute_tool(
                tool_name,
                parameters
            )

            # Support both the current async implementation and a
            # future synchronous execute_tool() implementation.
            if inspect.isawaitable(result):
                result = asyncio.run(result)

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

    def _get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            "name": "LibreOffice MCP Extension",
            "version": "1.0.0",
            "description": (
                "MCP server integrated into LibreOffice"
            ),
            "endpoints": {
                "GET /": "Server information",
                "GET /tools": "List available tools",
                "GET /health": "Health check",
                "POST /tools/{tool_name}": (
                    "Execute specific tool"
                ),
                "POST /execute": (
                    "Execute tool specified in request body"
                )
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
        """Send CORS headers."""
        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization"
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