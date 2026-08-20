# LibreOffice MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.6-blue.svg)](#versioning)
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
build/libreoffice-mcp-extension-2.0.6.oxt
```

The Windows builder creates a LibreOffice-compatible ZIP/OXT structure with normalized archive paths.

## 3. Install the extension

Adjust the LibreOffice path if your installation is located elsewhere.

PowerShell example:

```powershell
$RepoDir = "E:\Tools\mcp-libre"  # adjust to your clone location
& "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension
& "E:\LibreOffice\program\unopkg.com" add "$RepoDir\build\libreoffice-mcp-extension-2.0.6.oxt"
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
python "$RepoDir\build-oxt-windows.py"; Stop-Process -Name soffice,soffice.bin -Force -ErrorAction SilentlyContinue; & "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension; & "E:\LibreOffice\program\unopkg.com" add "$RepoDir\build\libreoffice-mcp-extension-2.0.6.oxt"
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

Run the automated test suite (471 tests):

```bash
uv run pytest
```

---

# Versioning

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
