"""
LibreOffice MCP Server

A Model Context Protocol server that provides tools and resources 
for interacting with LibreOffice documents.
"""

from .libremcp import main

__version__ = "2.0.9"
__all__ = ["main"]
