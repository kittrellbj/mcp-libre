# LibreOffice MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](#versioning)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#requirements)
[![LibreOffice](https://img.shields.io/badge/LibreOffice-24.2%2B-18A303.svg)](#requirements)

**MCP server for LibreOffice** — a native [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) integration that gives AI agents and assistants live, real-time access to Writer, Calc, Impress, and Draw through LibreOffice's UNO API. Point an MCP-aware AI agent at a running LibreOffice session and it can create, read, edit, format, and export documents directly — no file round-trips required.

This fork focuses on making the native LibreOffice extension work cleanly on Windows while preserving the original external MCP server and cross-platform project structure.

---

## Table of Contents

- [What's New in v2.0.0](#whats-new-in-v200)
- [Project Stats](#project-stats)
- [LibreOffice MCP Tools for AI Agents](#libreoffice-mcp-tools-for-ai-agents)
- [Repository Structure](#repository-structure)
- [Requirements](#requirements)
- [Windows Native Extension Installation](#windows-native-extension-installation)
- [Windows Development Workflow](#windows-development-workflow)
- [HTTP API](#http-api)
- [MCP JSON-RPC Transport](#mcp-json-rpc-transport)
- [Concurrency and Reliability](#concurrency-and-reliability)
- [Writer / Calc / Impress / Draw Automation via MCP](#writer--calc--impress--draw-automation-via-mcp)
- [Example: Live Writer Editing](#example-live-writer-editing)
- [Current Architecture](#current-architecture)
- [Windows Fixes Included](#windows-fixes-included)
- [Tooling Roadmap](#tooling-roadmap)
- [External MCP Server](#external-mcp-server)
- [Supported File Formats](#supported-file-formats)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Versioning](#versioning)
- [License](#license)
- [Upstream](#upstream)
- [Links](#links)

---

## What's New in v2.0.0

Version 2.0.0 grows the project from the v1.0.0 Windows native-extension baseline into a full LibreOffice automation surface for AI agents: the tool catalog expanded roughly twelvefold, the embedded HTTP server gained real concurrency safety, and the MCP transport itself was brought into spec conformance.

- **398 registered MCP tools** across Writer, Calc, Impress, Draw, and shared LibreOffice services — up from the 32-tool v1.0.0 baseline. 381 are live by default (the original 32 plus 349 fully implemented since); 17 remain stub-only, opt-in, and return `NOT_IMPLEMENTED` until finished (see [Tooling Roadmap](#tooling-roadmap)).
- **Concurrency control**: a process-wide UNO execution lock plus a bounded admission semaphore protect the embedded HTTP server from PyUNO bridge corruption under concurrent tool calls. Live-verified at 600/600 concurrent round trips with 0 errors.
- **MCP transport protocol conformance**: `Mcp-Session-Id` is now enforced end to end, and `MCP-Protocol-Version` is validated and negotiated per the MCP specification on every request.
- **449 automated tests passing**, plus live install/launch/health-check probes run against a real LibreOffice process for everything that can't be unit-tested outside one.

Full history in [`docs/HARDENING_PLAN.md`](docs/HARDENING_PLAN.md).

### v1.0.0 — Windows Native Extension Baseline

Version 1.0.0 established a known-working Windows baseline for the native LibreOffice extension, validated end-to-end on Windows. It remains a stable compatibility floor: every v1.0.0 tool name and behavior is preserved unconditionally in v2.0.0.

Validated functionality included:

- Native `.oxt` extension installation on Windows
- LibreOffice Tools menu integration
- Custom `mcp:` protocol dispatch
- Embedded HTTP server on `localhost:8765`
- Direct UNO access to active LibreOffice documents
- 32 registered MCP tools
- Live Writer text insertion and editing
- Text selection and formatting
- Comments and annotations
- Search and replace
- Track Changes support
- Document metadata and outline access
- Save and export operations
- Local HTTP health and tool discovery endpoints

---

## Project Stats

Numbers pulled from the project's own history (`docs/MCP_TOOLING_SCAFFOLD_PLAN.md`, `docs/HARDENING_PLAN.md`), not estimated. Where a number is a floor rather than an exact total, that's called out explicitly.

- **449 tests passing, 0 failing** — the current fakes-based `pytest` suite (`uv run pytest`).
- **At least 18 full-suite test runs are individually documented** across the project's history — one recorded at the close of each real-implementation pass, hardening item, and protocol-conformance phase, climbing from the first tracked snapshot (95/95) up to today's 449/449. This is a floor, not the true total: this project has no CI and no captured shell history, so the additional red/green iterations run while writing each test along the way aren't individually counted anywhere.
- **41 real bugs found and fixed** via live verification against a real, running LibreOffice instance — each caught only because a live round trip was run, not by the fakes-based unit suite alone. Every one is documented at its source with root cause and fix.
- **600/600** concurrent tool-call round trips succeeded with 0 errors in the concurrency-safety probe (2 threads × 300 iterations against two live Writer documents).
- **15/15** MCP transport protocol-conformance checks passed live against a real running extension (session-id enforcement, protocol-version negotiation).
- **51 commits** landed since the v1.0.0 baseline (85 commits total across the project's full history).
- **398 registered MCP tools** across Writer (99), Calc (99), Impress (41), Draw (16), and shared services (111), plus the original 32 legacy tools — 381 live by default, 17 stub-only pending (see [Tooling Roadmap](#tooling-roadmap)).

---

## LibreOffice MCP Tools for AI Agents

### Native LibreOffice Extension

The extension runs inside LibreOffice and exposes live document operations to AI agents through a local HTTP interface — both a real MCP JSON-RPC endpoint and a custom REST API.

Benefits:

- Direct access to the currently open document
- Immediate visual feedback in LibreOffice
- No document reload cycle for edits
- Direct UNO API access
- Enumerates all open documents; editing operations target the active document
- Local-only HTTP interface
- Tools menu controls for starting, stopping, restarting, and checking the MCP server

The native extension listens on:

```text
http://localhost:8765
```

Controls are available from:

```text
Tools → MCP Server
```

### External MCP Server

The original external server remains available for file-oriented workflows and traditional MCP/stdio integrations — this is the one usable directly with MCP clients such as Claude Desktop today.

Use it when you want to:

- Automate LibreOffice outside the GUI
- Create or convert files without an active editing session
- Integrate through stdio-based MCP clients
- Run scripted or batch workflows

---

## Repository Structure

```text
mcp-libre/
├── plugin/                 Native LibreOffice extension
│   ├── META-INF/
│   ├── pythonpath/
│   ├── Addons.xcu
│   ├── ProtocolHandler.xcu
│   └── description.xml
├── src/                    External MCP server
├── tests/                  Tests and validation
├── examples/               Usage examples
├── config/                 Integration configuration
├── scripts/                Helper and utility scripts
├── docs/                   Documentation
└── build-oxt-windows.py    Windows OXT builder
```

See `docs/REPOSITORY_STRUCTURE.md` for additional project layout details where available.

---

## Requirements

### Native Extension — Windows

Required:

- LibreOffice 24.2 or newer
- Windows 10 or Windows 11
- Python available to run `build-oxt-windows.py`

The extension itself runs using the Python runtime bundled with LibreOffice.

The working Windows implementation has been tested with LibreOffice's bundled Python 3.12 runtime.

### External MCP Server

Required:

- LibreOffice 24.2+
- Python 3.12+
- `uv`

---

# Windows Native Extension Installation

## 1. Clone the repository

Clone this fork:

```bash
git clone https://github.com/kittrellbj/mcp-libre.git
cd mcp-libre
```

If you are working from the Windows baseline branch:

```bash
git checkout windows-oxt
```

## 2. Build the OXT

From PowerShell or Git Bash:

```bash
python build-oxt-windows.py
```

The extension package is created at:

```text
build/libreoffice-mcp-extension-2.0.0.oxt
```

The Windows builder creates a LibreOffice-compatible ZIP/OXT structure with normalized archive paths.

## 3. Install the extension

Adjust the LibreOffice path if your installation is located elsewhere.

PowerShell example:

```powershell
$RepoDir = "E:\Tools\mcp-libre"  # adjust to your clone location
& "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension
& "E:\LibreOffice\program\unopkg.com" add "$RepoDir\build\libreoffice-mcp-extension-2.0.0.oxt"
```

Removing an extension that is not already installed may report that no matching extension exists. That is harmless.

You can verify installation with:

```powershell
& "E:\LibreOffice\program\unopkg.com" list
```

## 4. Start LibreOffice

Open Writer, Calc, Impress, or Draw.

Then select:

```text
Tools → MCP Server → Start MCP Server
```

The server should start on:

```text
http://localhost:8765
```

## 5. Verify the server

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Tool discovery:

```bash
curl http://127.0.0.1:8765/tools
```

A healthy server should return JSON from both endpoints.

---

# Windows Development Workflow

A convenient rebuild/reinstall command in PowerShell is:

```powershell
$RepoDir = "E:\Tools\mcp-libre"  # adjust to your clone location
python "$RepoDir\build-oxt-windows.py"; Stop-Process -Name soffice,soffice.bin -Force -ErrorAction SilentlyContinue; & "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension; & "E:\LibreOffice\program\unopkg.com" add "$RepoDir\build\libreoffice-mcp-extension-2.0.0.oxt"
```

Then reopen LibreOffice and start the MCP server from the Tools menu.

For console logging:

```powershell
& "E:\LibreOffice\program\soffice.com" --writer 2>&1 |
    Tee-Object -FilePath "$RepoDir\libreoffice-mcp.log"
```

---

# HTTP API

The native extension exposes both a real MCP JSON-RPC endpoint and a small custom REST API on the same local HTTP server.

## Health

```http
GET /health
```

Example:

```bash
curl http://127.0.0.1:8765/health
```

## Server information

```http
GET /
```

## List tools

```http
GET /tools
```

Example:

```bash
curl http://127.0.0.1:8765/tools
```

## Execute a tool

```http
POST /execute
Content-Type: application/json
```

Body:

```json
{
  "tool": "get_document_info_live",
  "parameters": {}
}
```

PowerShell example:

```powershell
$body = @{
    tool = "get_document_info_live"
    parameters = @{}
} | ConvertTo-Json -Compress

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8765/execute" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

Tools can also be called through:

```http
POST /tools/{tool_name}
```

---

# MCP JSON-RPC Transport

`POST /mcp` is a real MCP JSON-RPC 2.0 endpoint (Streamable HTTP, single-JSON-response mode) — separate from the custom REST API above and the recommended path for MCP-native clients. `/sse` and `/messages` are aliases for the same handler.

Supported methods: `initialize`, `tools/list`, `tools/call`, `ping`, `resources/list`, `prompts/list`.

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/mcp` | Dispatch a JSON-RPC 2.0 request |
| `GET` | `/mcp` | `405` — no server-initiated SSE stream |
| `DELETE` | `/mcp` | Terminate the session named by `Mcp-Session-Id` |

**Session lifecycle.** `initialize` mints and registers a session id, returned via the `Mcp-Session-Id` response header. Every later request must carry that header:

- Missing (on a non-`initialize` request) → `400 Bad Request`
- Unknown or already-terminated → `404 Not Found`
- `DELETE /mcp` with a known id actually removes the session; reusing that id afterward gets `404`, not a silent accept

**Protocol version negotiation.** `initialize` echoes back the client's requested `protocolVersion` if the server supports it (`2024-11-05`, `2025-03-26`, `2025-06-18`), otherwise substitutes its own latest supported version — a normal successful result, not an error, per the [MCP lifecycle spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle). Every later request's `MCP-Protocol-Version` header is validated the same way: unsupported → `400 Bad Request`; absent → falls back to the spec's own backwards-compatibility default (`2025-03-26`) rather than rejecting the request.

This server implements the MCP spec's **legacy** transport era (initialize-handshake, versions `2025-11-25` and earlier). The newer **modern** era (`2026-07-28`+, per-request version via `_meta`, no handshake) is a separate, larger architectural change and is not implemented.

See the [Streamable HTTP transport spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) for the full MUST/SHOULD rules this implementation follows.

---

# Concurrency and Reliability

The embedded HTTP server accepts concurrent connections (`ThreadingTCPServer`), which exposed a real bug: PyUNO's bridge layer corrupts under concurrent access — not a per-document data race, but the bridge proxy itself failing mid-call under overlapping tool executions. Two safeguards close that gap:

- **`_UNO_EXECUTION_LOCK`** — a single process-wide lock around the entire tool-execution sequence (object resolution through mutation). Live-verified at 600/600 concurrent round trips (2 threads × 300 iterations against two different Writer documents) with 0 errors; a finer-grained per-document lock was tried first and left 95/600 calls still failing, because it didn't cover object resolution.
- **`_ADMISSION_SEMAPHORE`** — a bounded semaphore (`MAX_CONCURRENT_TOOL_CALLS = 4`) acquired with a timeout (`ADMISSION_TIMEOUT_SECONDS = 30`) before the lock, so a burst of concurrent requests can't spin up unbounded threads waiting on it. A caller that can't be admitted in time gets a `503` with `Retry-After` on the REST path.

Full write-up, including the empirical test that found the actual bug, in [`docs/HARDENING_PLAN.md`](docs/HARDENING_PLAN.md).

---

# Writer / Calc / Impress / Draw Automation via MCP

The v2.0.0 catalog registers **398 MCP tools**: the 32-tool v1.0.0 compatibility baseline (always live, Writer-focused) plus 366 tools added since, organized by LibreOffice application area. 381 tools are live by default; 17 remain stub-only until implemented (enable them for development with `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS=1` — each returns a `NOT_IMPLEMENTED` error until finished).

| Area | Tools | Live by default | Stub-only |
|---|---:|---:|---:|
| Writer (v1.0.0 baseline) | 32 | 32 | 0 |
| Writer (layout, tables, text) | 99 | 97 | 2 |
| Calc (sheets, cells, ranges, external data) | 99 | 96 | 3 |
| Impress (slides, animation, slideshow) | 41 | 34 | 7 |
| Draw (pages, shapes, connectors) | 16 | 16 | 0 |
| Shared services (charts, drawing objects, styles, undo/view/selection, document lifecycle, core runtime) | 111 | 106 | 5 |
| **Total** | **398** | **381** | **17** |

<details>
<summary><strong>v1.0.0 baseline — Document lifecycle</strong></summary>

- `create_document_live`
- `get_document_info_live`
- `list_open_documents`
- `save_document_live`
- `export_document_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Text and content</strong></summary>

- `insert_text_live`
- `get_text_content_live`
- `format_text_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Document structure</strong></summary>

- `get_paragraph_count_live`
- `get_document_outline_live`
- `get_paragraph_live`
- `get_paragraphs_range_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Cursor navigation</strong></summary>

- `goto_paragraph_live`
- `goto_position_live`
- `get_cursor_position_live`
- `get_context_around_cursor_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Selection and editing</strong></summary>

- `select_paragraph_live`
- `select_text_range_live`
- `delete_selection_live`
- `replace_selection_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Search and replace</strong></summary>

- `find_text_live`
- `find_and_replace_live`
- `find_and_replace_all_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Comments</strong></summary>

- `get_comments_live`
- `add_comment_live`

</details>

<details>
<summary><strong>v1.0.0 baseline — Track Changes</strong></summary>

- `get_track_changes_status_live`
- `set_track_changes_live`
- `get_tracked_changes_live`
- `accept_tracked_change_live`
- `reject_tracked_change_live`
- `accept_all_changes_live`
- `reject_all_changes_live`

</details>

The v1.0.0 tool names remain backward-compatible as the interface expands.

<details>
<summary><strong>v2.0.0 — Writer (99 tools: writer_layout.py, writer_tables.py, writer_text.py)</strong></summary>

Page styles and layout, custom page sizes, margins, headers/footers, sections, columns, paragraph/character styles, lists and numbering, tables, frames, images, fields, footnotes/endnotes, bookmarks, cross-references, indexes/TOC, advanced typography, page numbering, document properties.

Stub-only: `set_chapter_numbering_live`, `mail_merge_live`.

See `plugin/pythonpath/tools/writer_layout.py`, `writer_tables.py`, `writer_text.py` for the full tool list.

</details>

<details>
<summary><strong>v2.0.0 — Calc (99 tools: calc_data.py, calc_page.py, calc_sheets.py)</strong></summary>

Sheet creation/deletion, cell and range access, formatting, formulas, named ranges, sorting/filtering, conditional formatting, validation, freeze panes, print areas, page styles, data import/export.

Stub-only: `create_external_link_live`, `refresh_external_link_live`, `delete_external_link_live`.

See `plugin/pythonpath/tools/calc_data.py`, `calc_page.py`, `calc_sheets.py` for the full tool list.

</details>

<details>
<summary><strong>v2.0.0 — Impress (41 tools: impress.py)</strong></summary>

Slides, layouts, master slides, text boxes, images, shapes, tables, notes, transitions, slide ordering, presentation settings, export.

Stub-only: `add_animation_live`, `update_animation_live`, `delete_animation_live`, `reorder_animations_live`, `next_slideshow_effect_live`, `previous_slideshow_effect_live`, `goto_slideshow_slide_live`.

See `plugin/pythonpath/tools/impress.py` for the full tool list.

</details>

<details>
<summary><strong>v2.0.0 — Draw (16 tools: draw.py)</strong></summary>

Pages, shapes, connectors, grouping, alignment, distribution, layers, text, images, geometry, export.

No stub-only tools remaining in this area.

See `plugin/pythonpath/tools/draw.py` for the full tool list.

</details>

<details>
<summary><strong>v2.0.0 — Shared LibreOffice services (111 tools: charts.py, drawing_objects.py, styles.py, undo_view_selection.py, document_lifecycle.py, core_runtime.py)</strong></summary>

Charts, drawing objects/shapes, styles, undo/redo, view and selection state, document lifecycle (create/open/save/export across all four applications), and core runtime tools (server info, capability discovery, diagnostics).

Stub-only: `add_chart_series_live`, `insert_embedded_object_live`, `activate_embedded_object_live`, `get_document_events_live`, `wait_for_document_event_live`.

See `plugin/pythonpath/tools/` for the full tool list.

</details>

The design is a semantic MCP layer with a guarded advanced UNO escape hatch for capabilities that don't justify dedicated first-class tools.

---

# Example: Live Writer Editing

With Writer open and the MCP server started:

```powershell
$body = @{
    tool = "insert_text_live"
    parameters = @{
        text = "Hello from LibreOffice MCP on Windows."
    }
} | ConvertTo-Json -Compress

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8765/execute" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

The text should appear immediately in the active Writer document.

---

# Current Architecture

The Windows native extension uses the following flow:

```text
AI / MCP Client
      │
      │ HTTP localhost:8765
      ▼
LibreOffice MCP HTTP Interface
      │
      ▼
Embedded MCP Tool Server
      │
      ▼
UNO Bridge
      │
      ▼
Writer / Calc / Impress / Draw
```

LibreOffice menu commands use a dedicated protocol:

```text
mcp:
```

Examples:

```text
mcp:start_mcp_server
mcp:stop_mcp_server
mcp:restart_mcp_server
mcp:get_status
```

This protocol is registered through `ProtocolHandler.xcu` and dispatched by the Python extension component.

---

# Windows Fixes Included

Fixes required for reliable native extension operation on Windows, carried forward from the v1.0.0 baseline.

## OXT packaging

The Windows build process:

- Uses normalized `/` archive paths
- Avoids invalid ZIP entry names
- Produces the required LibreOffice extension layout

## Manifest cleanup

The extension manifest no longer references unavailable package entries such as `types.rdb`.

## Python import compatibility

LibreOffice's Python extension environment requires explicit handling of its module path.

The Windows implementation:

- Adds the extension `pythonpath` directory to `sys.path`
- Uses absolute imports between extension modules
- Guards optional UNO interface imports with `try/except ImportError`

## Protocol dispatch

The extension uses a dedicated `mcp:` protocol instead of attempting to use `service:` URLs as protocol-handler commands.

This allows LibreOffice to correctly call:

```text
initialize()
queryDispatch()
dispatch()
```

for MCP menu actions.

## HTTP server lifetime

The HTTP server instance remains alive after startup rather than being destroyed when a context manager exits.

## HTTP request handling

The Windows implementation uses:

- Threaded request handling
- Explicit response lengths
- Explicit connection close behavior
- Safer client-disconnect handling

These changes prevent a slow or abandoned client request from blocking the entire local API.

---

# Tooling Roadmap

Most of the v1.0.0 roadmap is now implemented — see [Writer / Calc / Impress / Draw Automation via MCP](#writer--calc--impress--draw-automation-via-mcp) for the live catalog. 17 tools remain stub-only, opt-in behind `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS=1`, each returning `NOT_IMPLEMENTED` until a senior engineer fills in a real body:

- **Writer**: `set_chapter_numbering_live`, `mail_merge_live`
- **Calc**: `create_external_link_live`, `refresh_external_link_live`, `delete_external_link_live`
- **Impress**: `add_animation_live`, `update_animation_live`, `delete_animation_live`, `reorder_animations_live`, `next_slideshow_effect_live`, `previous_slideshow_effect_live`, `goto_slideshow_slide_live`
- **Shared services**: `add_chart_series_live`, `insert_embedded_object_live`, `activate_embedded_object_live`, `get_document_events_live`, `wait_for_document_event_live`

Beyond finishing those 17, longer-term goals include:

- Adopting the MCP spec's modern (2026-07-28+) transport era, if a real client requirement emerges (see [MCP JSON-RPC Transport](#mcp-json-rpc-transport))
- A dedicated JSON-RPC busy/backpressure error code, rather than routing admission-timeout rejections through `mcp_jsonrpc.py`'s generic `INTERNAL_ERROR`
- Continued separation of safe read-only operations from destructive or privileged operations as the tool surface grows

See `docs/MCP_TOOLING_SCAFFOLD_PLAN.md` and `docs/HARDENING_PLAN.md` for the detailed scaffold and hardening history.

---

# External MCP Server

The original external MCP server remains available.

## Install dependencies

```bash
uv sync
```

## Start the server

```bash
python src/main.py
```

or:

```bash
uv run python src/main.py
```

Help:

```bash
python src/main.py --help
```

Tests:

```bash
python src/main.py --test
```

The external server remains useful for automation scenarios that do not require live access to an already-open LibreOffice GUI session.

---

# Supported File Formats

LibreOffice supports a broad range of document formats.

Common inputs include:

- `.odt`
- `.ods`
- `.odp`
- `.odg`
- `.doc`
- `.docx`
- `.xls`
- `.xlsx`
- `.ppt`
- `.pptx`
- `.txt`
- `.rtf`

Common outputs include:

- PDF
- DOCX
- XLSX
- PPTX
- HTML
- TXT
- ODT
- ODS
- ODP
- ODG

Actual import/export capabilities depend on the installed LibreOffice version and available filters.

---

# Security

The native extension is designed for local use.

Current security characteristics:

- HTTP interface binds to `localhost`
- No public network listener is required
- Operations execute with the permissions of the current user
- File access is limited by the operating system permissions of the LibreOffice process
- No external cloud service is required
- AI clients should be treated as trusted local software because MCP tools can modify documents and write files
- Trusted-localhost-only: the server validates Host/Origin headers and rejects non-localhost requests (DNS-rebinding protection), but has no authentication of its own — any process on the local machine can call every tool

Do not expose port `8765` directly to untrusted networks.

Future tooling should continue to separate safe read-only operations from destructive or privileged operations.

---

# Troubleshooting

## Confirm the extension is installed

Windows:

```powershell
& "E:\LibreOffice\program\unopkg.com" list
```

## Confirm the server is listening

```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
```

or:

```bash
curl http://127.0.0.1:8765/health
```

## Start LibreOffice with extension logging

```powershell
& "E:\LibreOffice\program\soffice.com" --writer 2>&1 |
    Tee-Object -FilePath "libreoffice-mcp.log"
```

Expected startup messages include:

```text
MCPProtocolHandler initialized with frame
queryDispatch: mcp:start_mcp_server
dispatch called: mcp:start_mcp_server
Starting MCP server...
MCP HTTP server started successfully
UNO Bridge initialized successfully
Registered 381 MCP tools
```

(381 by default — the 32-tool v1.0.0 baseline plus the 349 implemented v2.0.0 tools. Set `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS=1` before starting LibreOffice to also register the 17 remaining stub-only tools, for a total of 398.)

## Tools menu appears but commands do nothing

Verify that:

- `ProtocolHandler.xcu` registers `mcp:*`
- `Addons.xcu` uses `mcp:` command URLs
- `registration.py` handles the `mcp:` protocol

## UNO import errors on Windows

Some UNO interfaces are not available as direct Python imports in every LibreOffice configuration.

Optional imports should be guarded:

```python
try:
    from com.sun.star.presentation import XPresentationDocument
except ImportError:
    XPresentationDocument = None
```

Feature detection should be preferred over assuming every UNO interface is importable.

---

# Development

Contributions are welcome.

Recommended workflow:

1. Fork the repository
2. Create a feature branch
3. Make focused changes
4. Add or update tests
5. Validate the native extension and/or external server
6. Submit a pull request

For Windows native extension changes, verify at minimum:

```text
[ ] OXT builds
[ ] OXT installs
[ ] MCP Server menu appears
[ ] Start command dispatches
[ ] /health responds
[ ] /tools responds
[ ] Writer text insertion works
[ ] Document readback works
[ ] Save works
[ ] PDF export works
```

Run the automated test suite (449 tests):

```bash
uv run pytest
```

---

# Versioning

## v2.0.0

Full tool catalog, concurrency control, and MCP transport protocol conformance, built on the v1.0.0 Windows baseline.

Includes:

- 398 registered MCP tools (381 live by default) across Writer, Calc, Impress, Draw, and shared services — up from the 32-tool v1.0.0 baseline
- Process-wide UNO execution lock and bounded admission semaphore for concurrency safety, live-verified at 600/600 concurrent round trips
- `Mcp-Session-Id` enforcement and `MCP-Protocol-Version` negotiation/validation on the real MCP JSON-RPC (`/mcp`) transport, per spec
- Systematic PyUNO robustness sweep and centralized error-code/UNO→JSON conversion handling
- 449 automated tests passing, plus live install/launch/health-check probes

## v1.0.0

Known-working Windows native extension baseline, validated end-to-end on Windows.

Includes:

- Windows-compatible OXT packaging
- Native LibreOffice protocol handler
- Local HTTP server
- UNO bridge
- 32 live MCP tools
- Live Writer manipulation
- Save and export
- Comments
- Search and replace
- Track Changes
- HTTP request handling fixes

Every v1.0.0 tool name and behavior is preserved unconditionally in v2.0.0.

---

# License

This project is licensed under the MIT License.

See:

```text
LICENSE
```

The MIT License permits commercial use, modification, distribution, and private use subject to its terms.

---

# Upstream

This project is based on:

```text
patrup/mcp-libre
```

This fork extends the original project with a working Windows native-extension implementation and continued development toward comprehensive LibreOffice MCP coverage.

---

# Links

- LibreOffice: https://www.libreoffice.org/
- Model Context Protocol: https://modelcontextprotocol.io/
- MCP specification (Streamable HTTP transport): https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP specification (lifecycle): https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Upstream project: https://github.com/patrup/mcp-libre

---

**LibreOffice MCP v2.0.0 — Native AI-driven document control inside LibreOffice, via the Model Context Protocol.**
