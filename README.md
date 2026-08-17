# LibreOffice MCP

Native Model Context Protocol integration for LibreOffice, with live access to Writer, Calc, Impress, and Draw through the UNO API.

This fork focuses on making the LibreOffice extension work cleanly on Windows while preserving the original external MCP server and cross-platform project structure.

## v1.0.0 — Windows Native Extension Baseline

Version 1.0.0 establishes a known-working Windows baseline for the native LibreOffice extension, validated end-to-end on Windows.

Validated functionality includes:

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

The v1.0.0 tag is intended to remain a stable compatibility baseline while broader LibreOffice tooling is developed on later branches.

---

## Features

### Native LibreOffice Extension

The extension runs inside LibreOffice and exposes live document operations through a local HTTP interface.

Benefits:

- Direct access to the currently open document
- Immediate visual feedback in LibreOffice
- No document reload cycle for edits
- Direct UNO API access
- Support for multiple open LibreOffice documents
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

The original external server remains available for file-oriented workflows and traditional MCP/stdio integrations.

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
build/libreoffice-mcp-extension-1.0.0.oxt
```

The Windows builder creates a LibreOffice-compatible ZIP/OXT structure with normalized archive paths.

## 3. Install the extension

Adjust the LibreOffice path if your installation is located elsewhere.

PowerShell example:

```powershell
& "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension
& "E:\LibreOffice\program\unopkg.com" add "E:\Tools\mcp-libre\build\libreoffice-mcp-extension-1.0.0.oxt"
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
python "E:\Tools\mcp-libre\build-oxt-windows.py"; Stop-Process -Name soffice,soffice.bin -Force -ErrorAction SilentlyContinue; & "E:\LibreOffice\program\unopkg.com" remove org.mcp.libreoffice.extension; & "E:\LibreOffice\program\unopkg.com" add "E:\Tools\mcp-libre\build\libreoffice-mcp-extension-1.0.0.oxt"
```

Then reopen LibreOffice and start the MCP server from the Tools menu.

For console logging:

```powershell
& "E:\LibreOffice\program\soffice.com" --writer 2>&1 |
    Tee-Object -FilePath "E:\Tools\mcp-libre\libreoffice-mcp.log"
```

---

# HTTP API

The native extension currently exposes a small local HTTP API.

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

# Native Tooling — v1.0.0

The Windows v1.0.0 baseline registers 32 live tools.

They cover the following areas.

## Document lifecycle

- `create_document_live`
- `get_document_info_live`
- `list_open_documents`
- `save_document_live`
- `export_document_live`

## Text and content

- `insert_text_live`
- `get_text_content_live`
- `format_text_live`

## Document structure

- `get_paragraph_count_live`
- `get_document_outline_live`
- `get_paragraph_live`
- `get_paragraphs_range_live`

## Cursor navigation

- `goto_paragraph_live`
- `goto_position_live`
- `get_cursor_position_live`
- `get_context_around_cursor_live`

## Selection and editing

- `select_paragraph_live`
- `select_text_range_live`
- `delete_selection_live`
- `replace_selection_live`

## Search and replace

- `find_text_live`
- `find_and_replace_live`
- `find_and_replace_all_live`

## Comments

- `get_comments_live`
- `add_comment_live`

## Track Changes

- `get_track_changes_status_live`
- `set_track_changes_live`
- `get_tracked_changes_live`
- `accept_tracked_change_live`
- `reject_tracked_change_live`
- `accept_all_changes_live`
- `reject_all_changes_live`

The v1.0.0 tool names are intended to remain backward-compatible as the interface expands.

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

# Windows Fixes Included in v1.0.0

The Windows baseline incorporates several fixes required for reliable native extension operation.

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

The 32 tools in v1.0.0 are only the compatibility baseline.

The long-term goal is comprehensive semantic coverage of LibreOffice rather than only basic Writer manipulation.

Planned areas include:

## Writer

- Page styles and page layout
- Custom page sizes and book trim presets
- Margins and mirrored margins
- Headers and footers
- Sections
- Columns
- Paragraph styles
- Character styles
- Lists and numbering
- Tables
- Frames
- Images
- Fields
- Footnotes and endnotes
- Bookmarks
- Cross-references
- Indexes and tables of contents
- Mail merge
- Advanced typography
- Page numbering
- Document properties
- Print settings

## Calc

- Sheet creation and deletion
- Cell and range access
- Formatting
- Formulas
- Named ranges
- Sorting and filtering
- Conditional formatting
- Validation
- Pivot tables
- Charts
- Images and shapes
- Freeze panes
- Print areas
- Page styles
- Data import and export

## Impress

- Slides
- Layouts
- Master slides
- Text boxes
- Images
- Shapes
- Charts
- Tables
- Notes
- Transitions
- Animations
- Slide ordering
- Presentation settings
- Export

## Draw

- Pages
- Shapes
- Connectors
- Grouping
- Alignment
- Distribution
- Layers
- Text
- Images
- Geometry
- Export

## Shared LibreOffice services

- Styles
- Charts
- Drawing objects
- Forms
- Metadata
- Accessibility
- Printing
- PDF options
- Undo/redo
- Clipboard operations
- Document events
- Diagnostics
- Capability discovery
- Batch operations
- Object handles

The intended design is a semantic MCP layer with a guarded advanced UNO escape hatch for capabilities that do not justify dedicated first-class tools.

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
Registered 32 MCP tools
```

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

---

# Versioning

## v1.0.0

First working Windows native extension baseline.

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

The `v1.0.0` tag is intended to remain a stable baseline while the broader MCP tooling surface is implemented.

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
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Upstream project: https://github.com/patrup/mcp-libre

---

**LibreOffice MCP v1.0.0 — Native AI-driven document control inside LibreOffice.**
