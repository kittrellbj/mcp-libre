# LibreOffice MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.22-blue.svg)](#versioning)
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

- **398 registered MCP tools** across Writer, Calc, Impress, Draw, and shared LibreOffice services — up from the 32-tool v1.0.0 baseline. 392 are live by default (the original 32 plus 360 fully implemented since); 6 remain stub-only, opt-in, and return `NOT_IMPLEMENTED` until finished (see [Tooling Roadmap](#tooling-roadmap)).
- **Concurrency control**: a process-wide UNO execution lock plus a bounded admission semaphore protect the embedded HTTP server from PyUNO bridge corruption under concurrent tool calls. Live-verified at 600/600 concurrent round trips with 0 errors.
- **MCP transport protocol conformance**: `Mcp-Session-Id` is now enforced end to end, and `MCP-Protocol-Version` is validated and negotiated per the MCP specification on every request.
- **451 automated tests passing**, plus live install/launch/health-check probes run against a real LibreOffice process for everything that can't be unit-tested outside one.

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

- **451 tests passing, 0 failing** — the current fakes-based `pytest` suite (`uv run pytest`).
- **At least 19 full-suite test runs are individually documented** across the project's history — one recorded at the close of each real-implementation pass, hardening item, and protocol-conformance phase, climbing from the first tracked snapshot (95/95) up to today's 451/451. This is a floor, not the true total: this project has no CI and no captured shell history, so the additional red/green iterations run while writing each test along the way aren't individually counted anywhere.
- **42 real bugs found and fixed** via live verification against a real, running LibreOffice instance — each caught only because a live round trip was run, not by the fakes-based unit suite alone. Every one is documented at its source with root cause and fix.
- **600/600** concurrent tool-call round trips succeeded with 0 errors in the concurrency-safety probe (2 threads × 300 iterations against two live Writer documents).
- **15/15** MCP transport protocol-conformance checks passed live against a real running extension (session-id enforcement, protocol-version negotiation).
- **51 commits** landed since the v1.0.0 baseline (85 commits total across the project's full history).
- **398 registered MCP tools** across Writer (99), Calc (99), Impress (41), Draw (16), and shared services (111), plus the original 32 legacy tools — 393 live by default, 5 stub-only pending (see [Tooling Roadmap](#tooling-roadmap)).

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
build/libreoffice-mcp-extension-2.0.22.oxt
```

The Windows builder creates a LibreOffice-compatible ZIP/OXT structure with normalized archive paths.

## 3. Install the extension

Adjust the LibreOffice path if your installation is located elsewhere.

PowerShell example:

```powershell
$RepoDir = "E:\Tools\mcp-libre"  # adjust to your clone location
& "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension
& "E:\LibreOffice\program\unopkg.com" add "$RepoDir\build\libreoffice-mcp-extension-2.0.22.oxt"
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
python "$RepoDir\build-oxt-windows.py"; Stop-Process -Name soffice,soffice.bin -Force -ErrorAction SilentlyContinue; & "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension; & "E:\LibreOffice\program\unopkg.com" add "$RepoDir\build\libreoffice-mcp-extension-2.0.22.oxt"
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

The v2.0.0 catalog registers **398 MCP tools**: the 32-tool v1.0.0 compatibility baseline (always live, Writer-focused) plus 366 tools added since, organized by LibreOffice application area. 393 tools are live by default; 5 remain stub-only until implemented (enable them for development with `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS=1` — each returns a `NOT_IMPLEMENTED` error until finished).

| Area | Tools | Live by default | Stub-only |
|---|---:|---:|---:|
| Writer (v1.0.0 baseline) | 32 | 32 | 0 |
| Writer (layout, tables, text) | 99 | 97 | 2 |
| Calc (sheets, cells, ranges, external data) | 99 | 99 | 0 |
| Impress (slides, animation, slideshow) | 41 | 38 | 3 |
| Draw (pages, shapes, connectors) | 16 | 16 | 0 |
| Shared services (charts, drawing objects, styles, undo/view/selection, document lifecycle, core runtime) | 111 | 111 | 0 |
| **Total** | **398** | **393** | **5** |

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

Stub-only, both blocked on a genuine UNO API limitation, not a scheduling gap — see [Tooling Roadmap](#tooling-roadmap): `set_chapter_numbering_live`, `mail_merge_live`.

See `plugin/pythonpath/tools/writer_layout.py`, `writer_tables.py`, `writer_text.py` for the full tool list.

</details>

<details>
<summary><strong>v2.0.0 — Calc (99 tools: calc_data.py, calc_page.py, calc_sheets.py)</strong></summary>

Sheet creation/deletion, cell and range access, formatting, formulas, named ranges, sorting/filtering, conditional formatting, validation, freeze panes, print areas, page styles, data import/export, external linked data areas (`create_external_link_live`/`refresh_external_link_live`/`delete_external_link_live`, built on `com.sun.star.sheet.XAreaLinks` — a genuinely different, CRUD-capable mechanism from the pre-existing read-only `ExternalDocLinks` enumeration `list_external_links_live` also reports).

No stub-only tools remaining in this area.

See `plugin/pythonpath/tools/calc_data.py`, `calc_page.py`, `calc_sheets.py` for the full tool list.

</details>

<details>
<summary><strong>v2.0.0 — Impress (41 tools: impress.py)</strong></summary>

Slides, layouts, master slides, text boxes, images, shapes, tables, notes, transitions, slide ordering, presentation settings, export, animations (`add_animation_live`/`update_animation_live`/`delete_animation_live`/`reorder_animations_live`, built on the generic `com.sun.star.animations` module — an `AnimateSet` effect wrapped in a `ParallelTimeContainer`, tagged with its trigger via LibreOffice's own `UserData`-based `node-type` mechanism, and appended to the slide's main sequence; scoped to a small honest effect set (`appear`/`disappear`), not LibreOffice's full preset library, which is internal C++ not reachable from the public UNO API at all — see [Tooling Roadmap](#tooling-roadmap)).

Stub-only: `next_slideshow_effect_live`, `previous_slideshow_effect_live`, `goto_slideshow_slide_live` (blocked — headless mode's `XSlideShowController` is always `None`, see [Tooling Roadmap](#tooling-roadmap)).

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

No stub-only tools remaining in this area. `activate_embedded_object_live` is live-verified but scoped to `LOADED`/`RUNNING` — its `ACTIVE`/`UI_ACTIVE`/`INPLACE_ACTIVE` verbs are confirmed to hang the whole process in headless mode (v2.0.6, see [Versioning](#versioning)).

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

Most of the v1.0.0 roadmap is now implemented — see [Writer / Calc / Impress / Draw Automation via MCP](#writer--calc--impress--draw-automation-via-mcp) for the live catalog. 5 tools remain stub-only, opt-in behind `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS=1`, each returning `NOT_IMPLEMENTED` until finished — all five are genuinely blocked, live-verified against real LibreOffice, not a scheduling gap:

- `set_chapter_numbering_live` — `ChapterNumberingRules.replaceByIndex()` raises `IllegalArgumentException` even when passed back the exact unmodified sequence `getByIndex()` returned. A real UNO API limitation, not a usage bug on our side. (`get_chapter_numbering_live`, read-only, works fine.)
- `mail_merge_live` — the real `com.sun.star.text.MailMerge` service needs a `DataSourceName` registered through `DatabaseContext`, which live-verified refuses to register an ad hoc `DataSource` without first persisting it to a real `.odb` file via `XStorable`. (`preview_mail_merge_live` works today via an unregistered ad hoc SDBC connection over a CSV folder.)
- `next_slideshow_effect_live`, `previous_slideshow_effect_live`, `goto_slideshow_slide_live` — all three need a live `XSlideShowController`, confirmed via live verification to always be `None` in headless mode (no window manager to render a slideshow view to). (`start_slideshow_live`/`stop_slideshow_live` don't need the controller and work fine.)

Calc's 3 external-link tools, Impress's 4 animation-mutation tools, and `add_chart_series_live` were finished and live-verified end to end in earlier passes — see the Calc entry (built on `com.sun.star.sheet.XAreaLinks`), the Impress entry (built on the generic `com.sun.star.animations` module), and the Charts entry (built on `XDataProvider.createDataSequenceByRangeRepresentation`) under [Writer / Calc / Impress / Draw Automation via MCP](#writer--calc--impress--draw-automation-via-mcp) above. The document-events pair `get_document_events_live`/`wait_for_document_event_live` (built on a process-wide `com.sun.star.document.XDocumentEventListener` registered against `GlobalEventBroadcaster`), `insert_embedded_object_live`, and `activate_embedded_object_live` also moved out of stub status and are now live-verified (v2.0.6, see [Versioning](#versioning)) — with two real, live-verified caveats worth knowing before relying on them: `wait_for_document_event_live` can't observe an event triggered by another tool call through this same HTTP server (only from outside it, e.g. a human editing in a GUI session — the process-wide concurrency lock serializes tool calls, so a blocked wait starves the very call that would trigger it), and `activate_embedded_object_live` is scoped to `LOADED`/`RUNNING` only — its `ACTIVE`/`UI_ACTIVE`/`INPLACE_ACTIVE` verbs are confirmed to hang the entire process in headless mode, not just the call.

Beyond finishing those five, longer-term goals include:

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
Registered 392 MCP tools
```

(392 by default — the 32-tool v1.0.0 baseline plus the 360 implemented v2.0.0 tools. Set `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS=1` before starting LibreOffice to also register the 6 remaining stub-only tools, for a total of 398.)

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

Run the automated test suite (474 tests):

```bash
uv run pytest
```

---

# Versioning

## v2.0.22

Step 5 of the typeset-run remediation, twelfth item: `get_sheet_summary_live`,
Brian's new-tools assignment priority #13 — an at-a-glance summary
(name, visibility, protection, used-range dimensions, freeze-panes
state) in one call instead of `get_active_sheet_live` +
`get_used_range_live` + `get_freeze_panes_live` + reading protection
separately.

Guards against a real edge case: `gotoStartOfUsedArea()`/
`gotoEndOfUsedArea()` both collapse to cell A1 on a sheet with no
content at all, so a single-cell result is checked for real content
before being trusted as an actual used range. A genuinely blank sheet
reports `used_range: null`, `row_count: 0`, `column_count: 0`, not a
misleading "1x1 used."

New `UNOBridge.get_sheet_summary()` plus the `get_sheet_summary_live`
tool wrapper in `calc_sheets.py`. `frozen` reuses `get_freeze_panes()`
(#12) as-is — composing the two new tools instead of duplicating logic
between them.

Live-verified against real headless LibreOffice Calc with a new probe,
`get-sheet-summary-probe-windows.py` — 10 checks, all passing: a
genuinely blank sheet reports the correct empty state; a sheet with
real content spanning B2:D5, a real freeze at B2, and real protection
reports all four fields correctly and consistently.

- 510 automated tests passing (507 + 3 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the last 2 new tools (`get_document_snapshot_live`,
  `extract_document_text_live`) and the `get_document_statistics_live`
  rewrite still queued after them.

## v2.0.21

Step 5 of the typeset-run remediation, eleventh item: `get_freeze_panes_live`,
Brian's new-tools assignment priority #12 — the getter
`freeze_panes_live`/`unfreeze_panes_live` never had. `sheet` omitted ->
the active sheet; reading a non-active sheet's freeze state does not
leave it active afterward.

Live-verified quirk, not a guess, and the main finding of this pass:
this LibreOffice build's `controller.SplitRow` reads back one higher
than the row actually passed to `freezeAtPosition()` whenever any row
is really frozen (`SplitColumn` has no such offset). Confirmed against
freezes at every combination — row-only, column-only, both, neither —
via direct `curl` probing against a live running instance before
finalizing the implementation. Corrected in `UNOBridge.get_freeze_panes()`
so `columns`/`rows`/`cell` all agree with what `freeze_panes_live` was
actually given.

Live-verified against real headless LibreOffice Calc with a new probe,
`get-freeze-panes-probe-windows.py` — 10 checks, all passing: a fresh
sheet reports `frozen: false, columns: 0, rows: 0`; freezing at C3
reports the real, corrected `columns: 2, rows: 2, cell: "C3"`; reading
a second sheet's freeze state succeeds without leaving it active; a
real unfreeze reports `frozen: false` again; column-only and row-only
freezes each independently confirm the row correction.

- 507 automated tests passing (505 + 2 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (2 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.20

Step 5 of the typeset-run remediation, tenth item: `update_cell_comment_live`,
Brian's new-tools assignment priority #11 — distinct from the existing
`add_cell_comment_live`'s upsert semantics. This one requires the
comment to already exist (`OBJECT_NOT_FOUND` if there's none at the
target cell) and is the only cell-comment tool that can toggle
`IsVisible` (the "always shown, not just on hover" display flag).
`text`/`author`/`visible` are all independently optional — only the
fields actually given are touched, reported back in an `updated` list.

New `UNOBridge.update_cell_comment()` plus the `update_cell_comment_live`
tool wrapper in `calc_page.py`. Same author-readonly handling as
`add_cell_comment` (live-verified this LibreOffice build won't let
`Author` be set): caught so a caller-supplied author that can't be
honored doesn't take an otherwise-successful text/visible update down
with it.

Live-verified against real headless LibreOffice Calc with a new probe,
`update-cell-comment-probe-windows.py` — 6 checks, all passing: a
text-only update reports `updated: ["text"]` and `list_cell_comments_live`
confirms the real comment text changed; a visibility-only update
reports `updated: ["visible"]` without touching text; updating a cell
with no existing comment reports a clean `OBJECT_NOT_FOUND` failure.

- 505 automated tests passing (502 + 3 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (3 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.19

Step 5 of the typeset-run remediation, ninth item: `get_draw_page_live`,
Brian's new-tools assignment priority #10 — the Draw counterpart to
Impress's `get_slide_content_live` (#3). `page` omitted -> the active
page. Deliberately narrower than `get_slide_content_live`'s result:
Draw pages don't carry Impress's hidden/notes concepts anywhere in
this tool catalog, so the result is just `{index, name, text: [...]}`.

New `UNOBridge.get_draw_page()` plus the `get_draw_page_live` tool
wrapper in `draw.py`. Same shape-text extraction loop as
`get_slide_content()` (only shapes with non-empty text are included),
reused rather than re-derived.

Live-verified against real headless LibreOffice Draw with a new probe,
`get-draw-page-probe-windows.py` — 8 checks against a real 2-page
document, all passing: omitted `page` defaults to the real active
page; addressing page 2 by name returns page 2's real text, not page
1's; an empty shape contributes nothing; `include_shape_metadata=true`
adds real type/geometry; an unknown page name fails cleanly.

- 502 automated tests passing (498 + 4 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (5 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.18

Step 5 of the typeset-run remediation, eighth item: `activate_draw_page_live`,
Brian's new-tools assignment priority #9 — the Draw counterpart to
Impress's `activate_slide_live`, an omission `draw.py`'s own page tools
never grew despite covering every other page operation. `page` (index
or name) in, `{index, name}` out — same shape `get_active_draw_page_live`
already reports.

New `UNOBridge.activate_draw_page()` plus the `activate_draw_page_live`
tool wrapper in `draw.py`. Same `setCurrentPage()` mechanism
`activate_slide()` uses for Impress, resolved through Draw's own
`_resolve_draw_page()`.

Live-verified against real headless LibreOffice Draw with a new probe,
`activate-draw-page-probe-windows.py` — 8 checks against a real 3-page
document, all passing: activating by name and by index both move the
real active page (confirmed against `get_active_draw_page_live`'s own
read afterward); activating an unknown page name reports a clean
failure.

- 498 automated tests passing (495 + 3 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (6 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.17

Step 5 of the typeset-run remediation, seventh item: `list_fonts_live`,
Brian's new-tools assignment priority #8. Unlike every other tool in
this batch, it isn't document-scoped at all — font availability is a
property of the LibreOffice installation, same category as
`get_server_info_live`/`get_capabilities_live`, so it lives in
`core_runtime.py` and takes no `document_id`.

New `UNOBridge.list_fonts()` uses the standard UNO idiom for font
enumeration — a throwaway screen-compatible `XDevice`'s
`getFontDescriptors()`, the same technique OOo Basic "list installed
fonts" macros have used since UNO's font APIs never grew a simpler
call. Returns one `FontDescriptor` per (name, style) combination
actually installed; grouped by name into `{name, styles: [...]}` rather
than a flat list with the same name repeated once per style variant.

Live-verified against real headless LibreOffice with a new probe,
`list-fonts-probe-windows.py` — 7 checks against the real bundled font
set (no document even open), all passing: the real fonts list is
non-empty and its `count` matches; no duplicate names; at least one
real bundled family (Liberation/DejaVu) is present; at least one font
reports more than one real installed style; every font's `styles` list
comes back sorted.

- 495 automated tests passing (493 + 2 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (7 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.16

Step 5 of the typeset-run remediation, sixth item: `goto_page_live`,
Brian's new-tools assignment priority #7 — the write-side companion to
`get_view_state_live`'s `current_page_number` addition (#6). `page`
(1-based, same numbering `current_page_number` reports) in, `{page}`
out. New `UNOBridge.goto_page()` plus the `goto_page_live` tool wrapper
in `undo_view_selection.py`, navigating through the same view cursor's
`com.sun.star.text.XPageCursor` interface `get_view_state_live` reads
from (`jumpToPage()`), not a second mechanism.

Live-verified finding, not a guess: `jumpToPage()` past the document's
real last page does not raise and does not leave the cursor where it
was — it silently clamps to the last real page. Reported back via a
warning naming both the requested and the real page reached.

Live-verified against real headless LibreOffice Writer with a new
probe, `goto-page-probe-windows.py` — 9 checks against a real 3-page
document (2 forced page breaks), all passing: jumping back to page 1
and forward to page 3 both actually move the real view cursor (checked
against `get_view_state_live`'s own read); jumping to page 99 clamps to
page 3 and reports a warning naming both numbers; `page=0` reports a
clean `INVALID_PARAMETER` failure.

- 493 automated tests passing (489 + 4 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (8 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.15

Step 5 of the typeset-run remediation, fifth item: Writer page number
on `get_view_state_live`, Brian's new-tools assignment priority #6.
Not a new tool — an enrichment to an existing one. `get_view_state_live`
already reported a document-type-specific position for calc
(`active_sheet`) and impress/draw (`current_page_name`), but Writer
fell through both branches and reported no page position at all. Added
a `writer` branch to `UNOBridge.get_view_state()`: `controller.
getViewCursor()` implements `com.sun.star.text.XPageCursor`, whose
`getPage()` returns the 1-based page the cursor is currently on — the
same number Writer's own status bar shows. Same best-effort try/except-
with-warning pattern the calc/impress branches already use.

Live-verified against real headless LibreOffice Writer with a new
probe, `view-state-page-number-probe-windows.py` — 6 checks, all
passing: a fresh single-page document reports `current_page_number:
1`; after `set_paragraph_text_live` + a real `insert_page_break_live`
(which resyncs the view cursor to the new paragraph per the BUG #5
fix), the same call reports `current_page_number: 2` — a real page
break moving a real cursor, not a stale or cached value — while
`zoom_value`/`has_selection` are still reported alongside it.

- 489 automated tests passing (487 + 2 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (9 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.14

Step 5 of the typeset-run remediation, fourth tool: `get_presentation_content_live`,
Brian's new-tools assignment priority #5 — the bulk counterpart to
`get_slide_content_live` (#3). Schema was already fixed by #3's own
design note: the per-slide entry shape `{index, name, hidden, text:
[{shape, text}], notes}` was built to be reused here, so this tool is a
loop over `get_slide_content`, not a new read path — `{slides: [...],
count}`. New `UNOBridge.get_presentation_content()` (`uno_bridge.py`,
right after `get_slide_content()`) plus the
`get_presentation_content_live` tool wrapper in `impress.py`, right
after `get_slide_content_live`. `slides` omitted → every slide in the
deck, in order; `slides` given → just those, in the order given, same
index-or-name resolution `get_slide_content()` already does, so there's
no second resolution path to keep in sync. `include_notes`/
`include_shape_metadata` pass straight through unchanged.
`include_hidden=false` is the one genuinely new behavior over a
hand-rolled loop of `get_slide_content_live` calls: it drops any slide
whose own `hidden` comes back `true`, so a caller wanting "what the
audience actually sees" doesn't need a second round-trip per slide to
check first.

Live-verified against real headless LibreOffice Impress with a new
probe, `presentation-content-probe-windows.py` — 11 checks against a
real 3-slide deck (slide 1 titled + notes, slide 2 hidden and empty,
slide 3 titled), all passing: omitted `slides` returns all 3 in deck
order with each slide's real text/notes; `include_hidden=false` drops
the hidden slide and keeps `count` honest for what's left; `slides=[0,
2]` scopes to just those two, in the order given; `include_notes=false`
omits the `notes` key on every slide, not just null; `include_shape_
metadata=true` adds type/geometry to every slide's text entries.

- 487 automated tests passing (483 + 4 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (10 more) and the
  `get_document_statistics_live` rewrite still queued after it.

## v2.0.13

Step 5 of the typeset-run remediation, third tool: `find_shape_text_live`,
Brian's new-tools assignment priority #4 ("shared search across
Impress/Draw shapes, optionally Writer/Calc drawing objects") — the
shape-level counterpart to `find_cells_live`'s cell-level search. No
exact schema was given for this one; `query`/`match`/`case_sensitive`/
`max_results` reuse `find_cells_live`'s established search-tool shape.
New `UNOBridge.find_shape_text()` (`uno_bridge.py`, right after
`get_shape_details`) plus the `find_shape_text_live` tool wrapper in
`drawing_objects.py`, placed right after `list_shapes_live` since both
are container-scoped shape enumeration primitives. Container scoping
mirrors `find_cells_live`'s "container given → just that one; omitted →
every candidate, each match reporting which one it came from" discipline
across all four shape-capable doc types (Writer's single document-wide
draw page, a Calc sheet's own draw page, an Impress/Draw page). Stops as
soon as `max_results` matches are found or a 5000-shape scan backstop is
hit — the same runaway-scan pattern `find_cells` established, scaled
down since a document's shape count is normally orders of magnitude
below its cell count.

Live-verified against real headless LibreOffice Impress with a new
probe, `find-shape-text-probe-windows.py` — 10 checks against real data
(matching shapes on two different slides, a deliberately empty shape,
duplicate text across slides), all passing, including negative checks
(container scopes the search to one slide, `match=exact` rejects a
non-exact substring, an invalid regex reports `INVALID_PARAMETER`
cleanly, `max_results` truncation is reported honestly). Writer/Calc
container resolution shares the same `_resolve_shape_container()`-family
helpers already live-verified across all four doc types by
`list_shapes_live`/`get_shape_live`/`insert_shape_live` in the original
`drawing_objects.py` pass — not independently re-verified by this probe,
which is scoped to Impress (the doc type Brian's assignment names
first).

- 483 automated tests passing (480 + 3 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (11 more) and the
  `get_document_statistics_live` rewrite still queued.

---

## v2.0.12

Step 5 of the typeset-run remediation, second tool: `get_slide_content_live`,
Brian's new-tools assignment priority #3 ("give me all the content of
slide 7" instead of `list_shapes_live` + N `get_shape_live` calls). New
`UNOBridge.get_slide_content()` (placed right after `get_speaker_notes`/
`set_speaker_notes`, whose `_find_notes_shape` it reuses) returns the
same per-slide shape the still-queued `get_presentation_content_live`
(priority #5) will wrap in bulk — built once so that tool can reuse it
via a loop rather than duplicating the logic. Only shapes with non-empty
text are included; `include_shape_metadata=true` adds each entry's
short type name and geometry; `include_notes=false` omits the `notes`
key entirely rather than reporting it as `null`, so callers can tell
"didn't ask" apart from "asked, page genuinely has no notes".
Live-verified against real headless LibreOffice Impress with a new
probe, `slide-content-probe-windows.py` — 10 checks against real data
(a titled shape, a deliberately empty shape, real speaker notes, a
hidden second slide), all passing, including negative checks (the empty
shape contributes nothing to `text`, `include_shape_metadata=false`
omits type/geometry, an unknown slide name fails cleanly rather than a
raw traceback).

- 480 automated tests passing (476 + 4 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s "Phase 6" section, which also
  tracks the rest of the new-tools list (12 more) and the
  `get_document_statistics_live` rewrite still queued.
- Flagged, not fixed this pass: `tests/test_client.py`, `plugin/
  test_plugin.py`, and `tests/test_insert_fix.py` fail at collection
  (pre-existing `mcp` package/venv drift — `ImportError`/
  `ModuleNotFoundError` on `mcp.shared.memory`/`mcp.server.fastmcp`,
  confirmed via `git stash` to predate this commit, not a regression
  from this pass). The 480 count above is the fakes-based suite these
  three files sit outside of; `uv run pytest` alone currently aborts
  collection before reaching it — a real environment issue worth its
  own pass, not something to silently work around here.

## v2.0.11

Step 5 of the typeset-run remediation, first tool: `find_cells_live`,
Brian's new-tools assignment priority #2 ("the biggest obvious Calc
hole") — Calc had no basic find-this-value/formula/comment-anywhere
primitive despite full range/formula/sort/filter manipulation. Built to
Brian's exact schema. Scope deliberately bounded (given range, else each
searched sheet's own used range, never the full grid; given sheet, else
every sheet in the workbook). Live-verified against real headless
LibreOffice Calc with a new probe, `find-cells-probe-windows.py` — 12
checks against real data, all passing, including negative checks
(values mode correctly does NOT match formula/comment text, `match=
"exact"` correctly rejects a partial substring `"contains"` would
accept, an invalid regex reports `INVALID_PARAMETER` cleanly rather than
a raw traceback).

- 476 automated tests passing (474 + 2 new fakes-based plumbing tests).
- Full writeup: `docs/HARDENING_PLAN.md`'s new "Phase 6" section, which
  also tracks the rest of the new-tools list (13 more) and the
  `get_document_statistics_live` rewrite still queued.

## v2.0.10

Step 4 of the 2026-08-19 typeset-run remediation: implemented Morgan's
capped-wait decision for `wait_for_document_event_live`
(`docs/EVENT_WAIT_CONCURRENCY_DECISION.md`) exactly as specified —
`uno_bridge.py`'s `wait_for_document_event()` clamps its actual wait to
`min(timeout_ms, _MAX_WAIT_LOCK_HOLD_MS)`. The cap (500ms) is measured,
not guessed, per the decision's explicit ask: `edit-latency-probe-
windows.py`, 100 real HTTP round trips of the typeset-run's dominant
call shape (`append_paragraph_live`/`insert_heading_live`) against a
real headless LibreOffice instance — min 5.0ms, median 29.1ms, p95
44.8ms, max 62.7ms. (First measurement attempt returned a suspicious
uniform ~2000ms per call — traced to `urllib.request` resolving
`"localhost"` adding a large, constant connection delay on this Windows
box, unrelated to any server-side work; switching to `127.0.0.1`
dropped every sample ~40x to the real numbers above.)

**Re-verified with the same positive/negative pair per Morgan's
instruction — and the result diverges from what the decision doc
predicted.** New probe, `event-wait-concurrency-probe-windows.py`. The
cap mechanics work exactly as specified (every wait call now holds the
lock for ~500ms max, confirmed live, never the full requested
`timeout_ms`), and the negative control (an event from outside this
tool's own lock) is still correctly observed, no regression. But the
positive pair — the tool's own primary use case, one agent's edit and
wait through the same HTTP surface — still fails, even across 8 poll
attempts, for a cap-independent reason: a diagnostic read confirms the
edit's event genuinely fires and is captured, it's just never seen as
"new" by any wait call's per-call snapshot, because the wait and the
edit fully serialize on the same lock with no overlap window where a
wait call could be both past-snapshot and still-blocked when the event
lands. This holds for any positive cap size, not specifically 500ms.

Corrected the tool's own `purpose` string and docstring (written before
this evidence existed) to state this plainly rather than leave an
overclaim standing. Full mechanism, evidence, and the open question
routed back to Morgan: `docs/HARDENING_PLAN.md`'s "Phase 5" section.

- 474 automated tests passing (no count change — no fakes-based
  regression test possible, same UNO-only constraint as the rest of this
  remediation).

## v2.0.9

Phase 4 of the 2026-08-19 typeset-run remediation: corrected the bug
count (13 real defects, not 15 — #8 and #11 were misdiagnoses, see
v2.0.8 below) and wrote up durable guidance in `docs/HARDENING_PLAN.md`
for the six standing-decision bullets Buddy's original assignment asked
for. Auditing bullet 3 (batching safe-or-unsafe) against the actual code
rather than the fix already landed found a real, previously-undocumented
gap: BUG #5's view-cursor resync fix (`insert_paragraph`/
`insert_heading`/`insert_page_break`) never reached two structurally
identical functions, `apply_page_style_live` and `remove_page_break_live`
— both resolve an omitted position through the same stale view cursor
with nothing to resync it. Fixed with the identical pattern. Live-verified
with a new probe, `batch-page-style-probe-windows.py`, mutation-tested
both directions: reverting the fix, the same repro's `remove_page_break`
resolves paragraph 4 (a stale, unrelated position) instead of the
expected 1; with the fix, 1.

- 474 automated tests passing (no count change — no fakes-based
  regression test possible for this fix, same `UNOBridge`-can't-
  instantiate-outside-LibreOffice constraint every other UNO-only fix in
  this project has hit).
- Full findings, the corrected-count table, and each of the six bullets'
  concrete status: `docs/HARDENING_PLAN.md`'s "Phase 4" section.

## v2.0.8

Investigated BUGs #8 and #11 from 2026-08-19's typeset-run log. **Neither was a real defect** — both were misdiagnoses by the original testing agent, settled with live evidence rather than assumed clean and dropped silently.

**BUG #8 — "catalog/dispatcher divergence: `create_paragraph_style_live` advertised but rejected."** Not real. `create_paragraph_style_live` has never existed in this project's history (`git log -S` across all commits returns zero results) — the tool for creating a paragraph style is `create_style_live` with `family="ParagraphStyles"`, unchanged since it was first scaffolded. Decisively confirmed against the original tester's own captured `GET /tools` catalog snapshot from that exact session: it never contained `create_paragraph_style_live` either. The catalog (`GET /tools`) and dispatcher (`POST /execute`/`/tools/<name>`) read the same `self.tools` dict off the same server singleton — there is no code path where they could diverge. The tester guessed a plausible-but-nonexistent name by analogy with the real `create_page_style_live` and got a correct rejection, then misreported it as a catalog/dispatcher mismatch. Two small hardening improvements made anyway, since the underlying failure class (a caller guessing a wrong tool name) is real even though this instance wasn't a bug: `execute_tool`'s "Unknown tool" error now includes a `did_you_mean` field (`difflib.get_close_matches` against the real registry — live-verified: querying the nonexistent name surfaces `create_style_live` as a top match), and `create_style_live`'s `purpose` string now explicitly says it's the tool a caller might otherwise look for as `create_paragraph_style_live`, with the full list of supported `family` values.

**BUG #11 — "`set_shape_geometry_live` doesn't actually resize."** Not real. `set_shape_geometry`'s UNO code (`uno_bridge.py`) sets `shape.Size` directly on the resolved shape object — exactly what the bug report itself recommended as the fix — and has been unchanged since it was first written, before the bug was even logged. Confirmed two ways: (1) the saved output artifact from that exact test session has 23 image frames from differently-sized source PNGs all showing the *one* uniform width the calling script requested, which is only possible if the resize took effect; (2) live-verified fresh this pass — inserted a rectangle at 3000×2000 (1/100mm), called `set_shape_geometry_live` to resize it to 9000×6000, and read it back independently via `get_shape_live` (which queries the live UNO object, not an echo of the request): came back 8999×6001, real resize confirmed end to end. The original ~12:07 observation of an unchanged exported image size most likely reflects that same session's separate, already-documented stale-document-reference problem (see the v2.0.x entries on `save_as_document_live`/export resolving a stale frame), not this function.

- 474 automated tests passing (no count change — no new tests added; `MCPServer.execute_tool`'s `did_you_mean` addition has no existing test harness to extend, since every current test exercises tool handlers directly through the `tools/` registry rather than through the `MCPServer` class — flagged as a real coverage gap, not silently left uncovered)
- Live-verified both investigation conclusions and both hardening additions end to end on a fresh headless LibreOffice instance: `create_paragraph_style_live` rejection now includes `did_you_mean: [..., "create_style_live", ...]`; `create_style_live`'s schema reflects the clarified description; a real shape's `Size` round-tripped correctly through `set_shape_geometry_live` → `get_shape_live`

## v2.0.7

Six of the fifteen bugs from 2026-08-19's extended agentic typeset-run log (P2/P3 tier), fixed and live-verified end to end against a fresh headless LibreOffice instance before this push, per standing policy.

**BUG #7 — `insert_paragraph_live`/`insert_heading_live`/`insert_page_break_live`'s shared anchor contract was undocumented.** An omitted `at_paragraph`/`at_position` anchors off wherever the *last* insert-family call (single or batched) left off, not a fixed "current selection" — this was real, working behavior the whole time, just never written down, so it read as flaky under `batch_execute_live`. Doc-only fix: all three tools' `purpose` strings now state the contract explicitly and cross-reference each other.

**BUG #9 — `append_paragraph_live` could partially apply on an unknown `style_name`.** The style-name lookup used to run *after* the text was already inserted, so an unknown style raised `success: false` while the paragraph landed anyway, unstyled — a caller that only checks `success` silently drops content that's actually there. Fixed by validating `style_name` before touching the document at all: an unknown style now fails atomically, nothing inserted. Live-verified both directions (unknown style rejected with zero document-length change; valid append with no style still succeeds).

**BUG #10 — `soffice.exe --version` hangs instead of exiting on this project's own Windows dev environment.** It launches the full app rather than printing a version and returning. Doc-only fix: `docs/PREREQUISITES.md` now recommends a file-existence check (`Test-Path`) as the Windows verification method instead, matching `smoke-test-windows.py`'s own convention. Not confirmed on Linux/macOS.

**BUG #12 — `insert_toc_live` created a duplicate table of contents on a repeat call.** Fixed with a get-or-create: a repeat call matching an existing `com.sun.star.text.ContentIndex` (by title, or any existing ToC when title is omitted) now returns that index instead of inserting a second one. Live-verified: `list_document_indexes_live`'s own count stays at 1 across two repeat calls. **Caveat, confirmed live this pass, not just assumed:** the returned `index_id` itself can differ across repeat calls — a raw-UNO probe showed two `getDocumentIndexes().getByIndex()` fetches of the *same* underlying ContentIndex return proxies with different `hash()` values, so the object registry's identity-keyed dict mints a second id even though no second index was created. Each id still resolves correctly for its own later `get`/`update`/`delete`. Documented in `writer_layout.py`'s module docstring and the tool's `purpose` string so a caller doesn't mistake this for the fix not working.

**BUG #13 — `set_document_properties_live` silently dropped capitalized property keys.** The field-name lookup matched exact-case only (`"title"`, not `"Title"`), with no case-insensitivity and no schema documenting the requirement. Fixed by lowercasing the lookup key. Live-verified: `{"Title": ..., "AUTHOR": ...}` now applies and round-trips correctly through `get_document_properties_live`.

**BUG #14 — `get_document_statistics_live`'s `paragraph_count` disagreed with `get_paragraph_count_live` whenever the document contained a table.** The statistics path counted every top-level text element via a raw enumeration (a `TextTable` counts as one element of its own), while the dedicated tool used a filtered count — live-verified this diverged by exactly the table count (13 vs. 12 on a 12-paragraph, 1-table document). Fixed by having statistics share the same filtered `_count_paragraphs()` helper. Live-verified: both tools now report the same count on a document containing a table.

- 474 automated tests passing (up from 473, net +1): `test_insert_toc_live_is_idempotent` covers BUG #12's get-or-create contract, including the deliberate-second-ToC-via-distinct-title case
- Live-verified end to end on a fresh headless LibreOffice instance, rebuilding/redeploying after the fixes, independently re-checking real document state for each of the four fixes with runtime behavior (#9, #12, #13, #14); #7 and #10 are documentation-only, confirmed correct by reading the underlying behavior/environment directly rather than re-executing unchanged code

## v2.0.6

Live-verification pass on v2.0.5's four newest tools (document-events pair, `insert_embedded_object_live`, `activate_embedded_object_live`), now that the extension's held-open instance was free. Real bugs found and fixed, all re-verified live post-fix on a rebuild — same bar as every other "Real implementation pass" in this changelog.

**Bug 1 — `insert_embedded_object_live` was broken for Writer, the most common document type.** `com.sun.star.drawing.OLE2Shape` (the CLSID-bearing shape v2.0.5 used for every document type) raises `com.sun.star.lang.ServiceNotRegisteredException` from Writer's own `createInstance()` — confirmed live this is genuinely absent from Writer's document-level shape factory (not a general "Writer can't createInstance drawing.\* shapes" problem: `RectangleShape`/`GraphicObjectShape`/etc. all createInstance fine on the same document). Confirmed live still correct as originally shipped for Calc (creates cleanly, `Model.Formula` settable) — Impress/Draw share the same shape factory Calc uses so are expected, not individually live-verified this pass, to behave the same. Fixed: Writer now uses `com.sun.star.text.TextEmbeddedObject` inserted via `text.insertTextContent()` instead, the object type Writer's own `getAvailableServiceNames()` actually lists for embedding. Two smaller follow-on findings from live-verifying that fix, both fixed and re-verified:
- The new object's default `AnchorType` (`AT_PARAGRAPH`) doesn't support `Position` at all — not just refusing a `set`, `com.sun.star.beans.UnknownPropertyException` on a plain **read** too. `_shape_geometry()` (shared by every shape's `get_shape_summary`/`get_shape_details`, not embedded-object-specific) now treats `x`/`y` as best-effort and omits them on failure, the same convention it already used for `RotateAngle`/`ShearAngle` — `width`/`height` stay required (confirmed live: unaffected by anchor type).
- `delete_shape()` (shared by every `delete_shape_live`/`delete_embedded_object_live` call, not embedded-object-specific) unconditionally called `shape.getParent()`, which this object type doesn't implement at all (confirmed live: `AttributeError`, not an empty parent). Now falls back to `doc.getText().removeTextContent(shape)`, confirmed live this removes cleanly, when `getParent` isn't present — every other shape type keeps its existing `getParent()`/`page.remove()` path unchanged.

**Bug 2 — `activate_embedded_object_live`'s `ACTIVE`/`UI_ACTIVE` verbs hang the entire process, not just the call.** Live-verified reproducibly (twice, independently, isolating the exact call): `changeState()` for either UI-opening verb never returns against this headless soffice instance, and while it's stuck, *every other tool call* — including ones unrelated to this shape or document — times out too, until soffice is killed and relaunched. `LOADED`/`RUNNING` were confirmed safe and near-instant. This is a materially worse failure mode than this project's existing headless-limitation precedent (`next/previous_slideshow_effect_live`/`goto_slideshow_slide_live` fail clean, returning `None`/an error) — a hang, not a clean error, with no way for a caller to recover short of an external process kill. Fixed: `activate_embedded_object_live` is now scoped to `LOADED`/`RUNNING` only (default changed from `UI_ACTIVE` to `RUNNING`); `INPLACE_ACTIVE`/`UI_ACTIVE`/`ACTIVE` now raise a named `UNSUPPORTED_CAPABILITY` error instead of attempting the call. Whether the UI-opening verbs work in this project's *other* documented usage mode (a GUI-visible session — "Start LibreOffice" above, `Tools → MCP Server → Start MCP Server`) rather than the headless mode this project's own dev-workflow/smoke-test scripts use, is a real open question for a future pass, not assumed either way here.

**Also found, not fixed this pass — flagged for a decision, not silently patched:** `wait_for_document_event_live` blocks while holding `ai_interface.py`'s process-wide `_UNO_EXECUTION_LOCK` (every tool call's full duration, an intentional, evidence-based design from the concurrency-hardening pass — see the comment above `_UNO_EXECUTION_LOCK`'s definition). Live-verified this means it can never observe an event triggered by *another tool call through the same HTTP server* — that second call queues behind the lock and only executes after the wait times out. Confirmed with two positive/negative pairs: an edit issued via the same HTTP tool-call path never got picked up (timed out at the full `timeout_ms` every time, event landed in the buffer only afterward); the identical edit issued via a raw UNO connection bypassing that lock was picked up correctly in ~3 seconds. This defeats the primary expected use case (one agent driving both the edit and the wait through this same tool surface) while still working for events from outside it (a human editing directly in a GUI session). Not fixed here: the lock is deliberately coarse for a real, tested reason (a per-mutation-only lock left 95/600 concurrency errors; only wrapping the full call reached 0/600), and carving out an exception for one blocking tool is a genuine concurrency-design decision, not a same-pass fix.

- 472 automated tests passing (up from 471, net +1): `test_drawing_objects.py`'s `test_activate_embedded_object_live_defaults_to_running`/`test_activate_embedded_object_live_accepts_case_insensitive_verb` replace the old UI_ACTIVE-default/`"active"`-verb assertions, plus one new `test_activate_embedded_object_live_ui_opening_verb_is_unsupported_capability` covering all three now-blocked verbs
- Live-verified end to end on a fresh headless LibreOffice 26.2 instance, independently checking real document state after every call, rebuilding/redeploying after each of the three fixes above: full insert → list → get → activate(RUNNING) → activate(LOADED) → activate(UI_ACTIVE, confirmed clean `UNSUPPORTED_CAPABILITY`, no hang) → delete → confirmed gone lifecycle on Writer; `insert_embedded_object_live` regression-checked clean on Calc post-fix (still returns real `x`/`y`/`rotation`/`shear`, unaffected by the Writer-only branch)

## v2.0.5

`activate_embedded_object_live` implemented for real, the last of Part 2's 12 shared-service scope-limited stubs. `drawing_objects.py` is now 31/31 fully implemented.

Drives `XEmbeddedObject.changeState()` via the shape's own `ExtendedControlOverEmbeddedObject` property (void/`None` if the shape has no CLSID), sourced from the documented OOo/LibreOffice Basic macro pattern (`oXEO = oShape.ExtendedControlOverEmbeddedObject; oXEO.changeState(com.sun.star.embed.EmbedStates.UI_ACTIVE)`), corroborated independently against the `XEmbeddedObjectSupplier2`/`XEmbeddedObject` IDL reference. `verb` accepts one of `LOADED`/`RUNNING`/`INPLACE_ACTIVE`/`UI_ACTIVE`/`ACTIVE` (case-insensitive; an unknown value is a named `INVALID_PARAMETER`, not a crash), defaulting to `UI_ACTIVE` — the state the documented pattern uses to open an embedded object for interactive editing. `EmbedStates` is a UNO constants group, not an enum, resolved through `uno.getConstantByName()` in both directions (the request, and the read-back `getCurrentState()`) rather than hardcoding a numeric value, matching this file's established convention for every other constants-group lookup.

**Not yet live-verified, flagged rather than assumed:** same footing as `insert_embedded_object_live`/the document-events pair in v2.0.4 — code-complete and unit-tested against a fake bridge, but the live REST round trip against a real running LibreOffice instance is still pending. The extension's one live instance was held for another agent's overnight Writer-agent test for the entire duration of this pass (per this channel's own hold instruction, lifted for source work only, not live verification); the next live pass needs to insert a real formula object, activate it, and confirm `ExtendedControlOverEmbeddedObject`/`changeState()` behave as documented before this is trusted the way `insert_embedded_object_live`'s CLSID is.

- 393 live tools (was 392), 5 stub-only (was 6)
- 471 automated tests passing (up from 469, net +2): 4 new tests in `test_drawing_objects.py` (default verb, case-insensitive verb, unknown-verb `INVALID_PARAMETER`, non-OLE-shape `INVALID_PARAMETER`) replace the old still-`NOT_IMPLEMENTED` assertion, offset by removing `test_tool_scaffold_contract.py`'s now-obsolete `drawing_objects.py` mixed-module status-guard test (moved into `IMPLEMENTED_MODULES` outright, same as `charts.py`/`undo_view_selection.py` before it)

## v2.0.4

3 of Part 2's last 4 shared-service scope-limited stubs implemented: the document-events pair (`get_document_events_live`/`wait_for_document_event_live`) and `insert_embedded_object_live` (scoped to `object_type="formula"`). 1 remains (`activate_embedded_object_live` -- see Tooling Roadmap).

**Document events.** A single `com.sun.star.document.XDocumentEventListener` is registered once, process-wide, against the `com.sun.star.frame.GlobalEventBroadcaster` singleton -- already covers every open document, not just the active one, so no per-document wiring is needed. Captured events land in a bounded, seq-numbered buffer on the `UNOBridge` instance (a monotonically increasing `seq`, not a raw deque index/length, since a bounded deque silently evicts from the left once full). `get_document_events_live` reads and filters that buffer; `wait_for_document_event_live` blocks the calling request thread on a `threading.Condition` until a matching event lands or the deadline passes -- confirmed safe against `ai_interface.py`'s per-request-thread model (a blocking wait on one request thread can't stall another). `document_id` correlation for a captured event's source document is best-effort: a new read-only `DocumentRegistry.find_document_id()` looks up an already-registered document without ever minting a new id, so a document opened directly in the LibreOffice GUI (rather than through `open_document_live`/`create_document_live`) reports `document_id: null` instead of raising or being silently dropped.

**`insert_embedded_object_live`.** Real mechanism is a `com.sun.star.drawing.OLE2Shape` added to the resolved container's draw page (the same `_resolve_shape_container()` every other shape tool in this module uses), with its `CLSID` property set before `page.add()` -- the documented OOo/LibreOffice Basic macro pattern for this shape type. Scoped to `object_type="formula"` only: that CLSID (`078B7ABA-54FC-457F-8551-6147E776A997`) is repeated identically across enough independent sources to trust without a live round trip, but the other embeddable types (Calc sheet, Writer text, chart) don't have the same repeated-independent-source confidence -- a wrong CLSID fails silently rather than loudly, exactly the risk this project's CoreReflection-verification precedent exists to catch. Any other `object_type` raises a clear `NotImplementedError` naming the gap (surfaces as `UNSUPPORTED_CAPABILITY`) rather than shipping a guessed GUID as fact.

**Not yet live-verified, flagged rather than assumed:** all three tools above are code-complete and unit-tested (`uv run pytest`), but this pass's REST round trip against a real running LibreOffice instance is still pending -- the extension's one live instance was held for a separate overnight Writer-agent test at the time of this work (per this channel's own hold instruction) and, checked directly afterward, was carrying an unsaved, never-saved `modified: true` document with no backing file, which a rebuild/relaunch to live-verify would have destroyed. Every open design question the original design note flagged (does `GlobalEventBroadcaster` miss a document's own pre-registration `OnLoad`? what are the real `EventName` values seen in practice for a Writer session? does a second `UNOBridge` instance's registration attempt actually no-op cleanly?) is still open until that round trip runs -- flipped to `status="implemented"` on the strength of the unit-test coverage and the documented mechanism, matching this module's usual bar for code review, not as a substitute for the live pass once the instance is free again.

- 392 live tools (was 389), 6 stub-only (was 9)
- 469 automated tests passing (up from 453, net +16): 12 new in `test_undo_view_selection.py` for the document-events pair, 3 new in `test_document_registry.py` for `find_document_id()`, and `test_drawing_objects.py`'s old `test_insert_and_activate_embedded_object_are_still_not_implemented` split into 3 (a real formula-insert test, an unscoped-type-is-`UNSUPPORTED_CAPABILITY` test, and `activate_embedded_object_live`'s still-`NOT_IMPLEMENTED` test) -- offset by removing the now-obsolete mixed-module status-guard test for `undo_view_selection.py` (moved into `IMPLEMENTED_MODULES` outright, all 14 tools now real)

## v2.0.3

`add_chart_series_live` implemented for real (Calc charts), 1 of Part 2's 5 remaining shared-service scope-limited stubs (4 remain: `insert_embedded_object_live`, `activate_embedded_object_live`, `get_document_events_live`, `wait_for_document_event_live` -- see Tooling Roadmap).

Live-verified this pass: chart2's public `XDataProvider` has no value-array constructor (confirmed against the interface reference), only `createDataSequenceByRangeRepresentation` from a range string. So raw in-memory `values`/`label`/`categories` get written to a real, untouched scratch range past the sheet's used area first (staggered fresh per call via `gotoEndOfUsedArea`, so repeated calls don't collide), then wired into a new chart2 `DataSeries` via `XDataSink.setData()` with `Role="values-y"`/`"label"`/`"categories"` data sequences. Scoped to the `values-y` role only -- a `values-x` role for scatter/bubble charts is left for a follow-up, same honest-cut precedent as `create_chart_live`'s data-array branch.

One real bug caught and fixed before shipping: the first working version wrote `categories` to real sheet cells but never attached them to any chart2 data sequence, silently orphaning the values -- invisible from this tool's own success response, only caught by independently reading the raw `XDataSeries.getDataSequences()` back after a live REST round trip. Fixed by wiring a second `Role="categories"` labeled sequence onto the new series.

- 389 live tools (was 388), 9 stub-only (was 10)
- 453 automated tests passing (unchanged): `test_add_chart_series_live`/`test_add_chart_series_live_requires_values` replace the old `test_add_chart_series_live_not_implemented`; `charts.py` moved from a mixed 19/20 module into `IMPLEMENTED_MODULES` (all 20 tools now real)
- Live-verified via a real build → install → launch → REST round trip (write source data, create a chart, add a series with label/values/categories, add a second series with no label to confirm column staggering, remove a series), plus an independent raw-UNO read of the resulting sheet cells and chart2 data sequences -- not just this tool's own response

## v2.0.2

`add_animation_live`/`update_animation_live`/`delete_animation_live`/`reorder_animations_live` implemented for real (Impress), 4 of the 12 scope-limited stubs from this pass's earlier catch-up (5 remain queued: shared-services `add_chart_series_live`, `insert_embedded_object_live`, `activate_embedded_object_live`, `get_document_events_live`, `wait_for_document_event_live` -- see Tooling Roadmap).

Built on the generic `com.sun.star.animations` module (`AnimateSet` wrapped in a `ParallelTimeContainer`, appended to the slide's main sequence), not LibreOffice's internal preset library (`sd/source/core/CustomAnimationEffect.cxx`'s `CustomAnimationPresets`, which loads from a bundled XML template database and isn't reachable from the public UNO API at all -- confirmed by reading LO's own C++ source, since the public API docs don't cover node construction). Scoped to a small honest effect set (`appear`/`disappear`) rather than attempting to port that preset library.

Two real findings from live verification against the real MCP REST layer, not just raw UNO:

- `NodeType` (`ON_CLICK`/`WITH_PREVIOUS`/`AFTER_PREVIOUS`/`MAIN_SEQUENCE`/`TIMING_ROOT`) is NOT a settable/gettable property on a generically-constructed animation node, despite being an `XAnimationNode`-shaped name -- LibreOffice's own UI stores it as a `"node-type"` `NamedValue` inside `UserData` instead (`CustomAnimationEffect::setNodeType()`). `list_animations_live`'s `NodeType` read (pre-existing, from the earlier read-only pass) never actually exercised this, since no live document it was tested against had a tagged node; now reads `UserData` instead, surfaced as `trigger` in each entry.
- animcore `XAnimationNode` proxies don't compare equal across independently-obtained PyUNO references (unlike shape/document proxies elsewhere in this project, which do) -- `reorder_animations_live`'s original safety check (comparing a resolved node list against a freshly re-enumerated one via `set()`/`==`) could never pass even for a fully valid, complete reorder. Fixed by using the server's own `removeChild()` call as the membership oracle instead of client-side identity comparison, with a rollback path if a caller-supplied id turns out foreign. Same root cause also means `list_animations_live` and `add_animation_live` mint different (but both independently working) `animation_id`s for the same freshly-added effect -- a cosmetic non-deduplication, confirmed non-blocking via a live round trip, not a correctness bug.

Click-advance runtime behavior (does an `on_click`-triggered effect actually wait for a click during a slideshow) is not verifiable in this environment -- headless mode's `XSlideShowController` is always `None`, the same documented dead end as `next_slideshow_effect_live`/`previous_slideshow_effect_live`/`goto_slideshow_slide_live`. Only tree construction and REST-layer plumbing are live-verified.

- 388 live tools (was 384), 10 stub-only (was 14)
- 453 automated tests passing (up from 451): `test_animation_lifecycle_live`, `test_add_animation_live_unknown_effect`, `test_reorder_animations_live_rejects_partial_set` replace the old `test_add_animation_live_not_implemented`
- Live-verified via a real build → install → launch → REST round trip (insert a shape, add an effect, list it back, update it, reorder it, delete it, confirm removal), not just raw UNO probing

## v2.0.1

Docs and tool-catalog updates on the v2.0.0 baseline; no version-source files were bumped for these three commits when they shipped, folded into this entry as a catch-up.

Includes:

- New "Project Stats" section in the README (test-run count, real-bug count, probe results, commit count), sourced from the project's own planning docs rather than invented
- The 17 stub-only tools re-documented as two distinct groups: 5 genuinely blocked on a live-verified technical wall (`set_chapter_numbering_live`'s UNO `IllegalArgumentException`, `mail_merge_live`'s `DatabaseContext` registration requirement, and the `next/previous_slideshow_effect_live`/`goto_slideshow_slide_live` trio's headless-mode `XSlideShowController`), versus 12 scope-limited stubs with a real UNO mechanism just not yet attempted
- `create_external_link_live`/`refresh_external_link_live`/`delete_external_link_live` implemented for real (Calc), built on `com.sun.star.sheet.XAreaLinks` rather than the read-only `ExternalDocLinks` cache `list_external_links_live` originally read; `list_external_links_live` now also reports `area_links` refresh state alongside the unchanged `formula_links`, fixing a gap between its documented purpose and what it actually read
- 384 live tools (was 381), 14 stub-only (was 17), 42 real bugs found and fixed via live verification (was 41)
- 451 automated tests passing (up from 449)
- Standing policy from this release forward: every push that changes code or tool behavior bumps all version-source files and adds a dated entry here, rather than batching version bumps later

## v2.0.0

Full tool catalog, concurrency control, and MCP transport protocol conformance, built on the v1.0.0 Windows baseline.

Includes:

- 398 registered MCP tools (384 live by default) across Writer, Calc, Impress, Draw, and shared services — up from the 32-tool v1.0.0 baseline
- Process-wide UNO execution lock and bounded admission semaphore for concurrency safety, live-verified at 600/600 concurrent round trips
- `Mcp-Session-Id` enforcement and `MCP-Protocol-Version` negotiation/validation on the real MCP JSON-RPC (`/mcp`) transport, per spec
- Systematic PyUNO robustness sweep and centralized error-code/UNO→JSON conversion handling
- 451 automated tests passing, plus live install/launch/health-check probes

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
