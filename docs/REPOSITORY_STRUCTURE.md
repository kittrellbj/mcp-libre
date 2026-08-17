# 📂 Repository Structure

This document explains the organization of the LibreOffice MCP Server repository.

## 🗂️ Directory Structure

```
mcp-libre/
├── 📁 src/                         # Source code
│   ├── __init__.py                 # Package initialization
│   ├── libremcp.py                 # Main MCP server implementation
│   └── main.py                     # Entry point script
├── 📁 plugin/                      # LibreOffice Extension (NEW!)
│   ├── 📁 META-INF/                # Extension metadata
│   │   └── manifest.xml            # Extension manifest file
│   ├── 📁 pythonpath/              # Python extension modules
│   │   ├── uno_bridge.py           # UNO API bridge for LibreOffice
│   │   ├── mcp_server.py           # Embedded MCP server
│   │   ├── ai_interface.py         # HTTP API for AI assistants
│   │   ├── host_trust.py           # Host/Origin trust check (DNS-rebinding guard) for ai_interface.py
│   │   ├── uno_datetime.py         # com.sun.star.util.DateTime -> ISO-8601 string (unit-testable, no UNO needed)
│   │   ├── registration.py         # Extension registration and lifecycle
│   │   └── 📁 tools/               # Full-catalog tool scaffold (see docs/MCP_TOOLING_SCAFFOLD_PLAN.md)
│   │       ├── registry.py         # @register_tool decorator (status=stub|implemented), merge_into()
│   │       ├── envelope.py         # {success, result, error, document_id, elapsed_ms} builders
│   │       ├── documents.py        # DocumentRegistry (real): stable document_id handles + per-doc get_object_registry()
│   │       ├── object_registry.py  # ObjectRegistry (real): stable shape_id/chart_id/table_id handles, see docs/OBJECT_HANDLE_DESIGN.md
│   │       ├── runtime_state.py    # RuntimeState (real): session id, profile, bounded error history
│   │       ├── context.py          # RuntimeContext install()/get_context() -- shared server state for handlers
│   │       ├── core_runtime.py     # Phase A, IMPLEMENTED: discovery/capability/profile/diagnostics tools
│   │       ├── document_lifecycle.py # Phase A, IMPLEMENTED: open/save/convert/properties tools
│   │       ├── undo_view_selection.py # Phase A, 12/14 IMPLEMENTED: undo/redo/view/zoom/selection/locking (document-events pair still stub)
│   │       ├── styles.py           # Phase A, IMPLEMENTED: style family/apply/formatting tools
│   │       ├── writer_text.py      # Phase B, 18/18 IMPLEMENTED: paragraph/character editing, regex find/replace, comments
│   │       ├── writer_layout.py    # Phase B, stub: page layout, headers/footers, fields, bookmarks, indexes
│   │       ├── writer_tables.py    # Phase B, stub: tables, sections, footnotes/endnotes, content controls, mail merge
│   │       ├── drawing_objects.py  # Phase C, stub: shapes, glue points, images, embedded objects
│   │       ├── charts.py           # Phase C, stub: chart2-based chart tools
│   │       ├── calc_sheets.py      # Phase C, stub: sheets, cells, ranges, rows/columns, formulas
│   │       ├── calc_data.py        # Phase C, stub: named ranges, filters, pivots, validation, external data
│   │       ├── calc_page.py        # Phase C, stub: page layout, print areas, comments, protection
│   │       ├── impress.py          # Phase D, stub: slides, masters, notes, transitions, animations, slideshow
│   │       └── draw.py             # Phase D, stub: Draw pages, layers, vector operations
│   ├── Addons.xcu                  # LibreOffice menu configuration
│   ├── ProtocolHandler.xcu         # Protocol handler configuration
│   ├── description.xml             # Extension description
│   ├── description-en.txt          # English description text
│   ├── release-notes-en.txt        # Release notes
│   ├── README.md                   # Plugin documentation
│   ├── build.sh                    # Extension build script
│   ├── install.sh                  # Installation and management script
│   └── test_plugin.py              # Plugin testing client
├── 📁 tests/                       # Test files
│   ├── __init__.py                 # Test package initialization
│   ├── test_client.py              # Interactive MCP client test
│   ├── test_insert_fix.py          # Specific function tests
│   ├── test_tool_scaffold_contract.py # Tool scaffold registry contract tests (no live LibreOffice needed)
│   ├── test_document_registry.py   # DocumentRegistry unit tests (no live LibreOffice needed)
│   ├── test_object_registry.py     # ObjectRegistry unit tests (no live LibreOffice needed)
│   ├── test_runtime_state.py       # RuntimeState unit tests (no live LibreOffice needed)
│   ├── test_context.py             # tools.context unit tests (no live LibreOffice needed)
│   ├── test_core_runtime.py        # core_runtime.py's 12 implemented tools, tested against fakes
│   ├── test_document_lifecycle.py  # document_lifecycle.py's 22 implemented tools, tested against fakes
│   ├── test_undo_view_selection.py # undo_view_selection.py's 12 implemented tools, tested against fakes
│   ├── test_styles.py              # styles.py's 12 implemented tools, tested against fakes
│   ├── test_writer_text.py         # writer_text.py's 18 implemented tools, tested against fakes
│   ├── test_uno_datetime.py        # DateTime-to-ISO conversion unit tests (no live LibreOffice needed)
│   └── test_host_trust.py          # Host/Origin trust check unit tests (no live LibreOffice needed)
├── 📁 examples/                    # Demo and example scripts
│   ├── __init__.py                 # Examples package initialization
│   ├── demo_editing.py             # Document editing demonstrations
│   └── demo_live_viewing.py        # Live viewing and editing demo
├── 📁 config/                      # Configuration templates
│   ├── claude_config.json.template # Claude Desktop configuration template
│   └── mcp.config.json.template    # Super Assistant configuration template
├── 📁 scripts/                     # Utility scripts
│   ├── generate-config.sh          # Configuration generator script
│   └── mcp-helper.sh               # Helper script for testing and setup
├── 📁 docs/                        # Documentation
│   ├── CHATGPT_BROWSER_GUIDE.md    # ChatGPT browser integration guide
│   ├── COMPLETE_SOLUTION.md        # Comprehensive overview
│   ├── DOCUMENT_TARGETING_DECISION.md # document_id vs document_url decision (vs. WriterAgent reference)
│   ├── EXAMPLES.md                 # Usage examples
│   ├── LICENSE_OPTIONS.md          # License information
│   ├── LIVE_VIEWING_GUIDE.md       # Live viewing setup guide
│   ├── MCP_TOOLING_SCAFFOLD_PLAN.md # Full-catalog scaffold/real-implementation progress tracker
│   ├── OBJECT_HANDLE_DESIGN.md     # shape_id/chart_id/table_id/sheet/slide handle design
│   ├── PREREQUISITES.md            # System requirements
│   ├── QUICK_START.md              # Quick start guide
│   ├── REPOSITORY_STRUCTURE.md     # This file
│   ├── SUPER_ASSISTANT_SETUP.md    # Super Assistant setup guide
│   └── TROUBLESHOOTING.md          # Troubleshooting guide
├── 📄 README.md                    # Main project documentation
├── 📄 LICENSE                      # MIT License
├── 📄 pyproject.toml               # Python project configuration
├── 📄 uv.lock                      # UV dependency lock file
├── 📄 .gitignore                   # Git ignore rules
├── 📄 .python-version              # Python version specification
├── 🔧 mcp-helper.sh               # Wrapper for scripts/mcp-helper.sh
└── 🔧 generate-config.sh          # Wrapper for scripts/generate-config.sh
```

## 📋 File Descriptions

### Source Code (`src/`)

**Core MCP server implementation for external usage:**

- `libremcp.py`: Main MCP server with all tools and functionality
- `main.py`: Entry point for running the external MCP server
- `__init__.py`: Package initialization and exports

### LibreOffice Extension (`plugin/`) - NEW!

**Native LibreOffice plugin/extension implementation:**

- `pythonpath/uno_bridge.py`: Bridge between MCP and LibreOffice UNO API
- `pythonpath/mcp_server.py`: Embedded MCP server for the extension
- `pythonpath/ai_interface.py`: HTTP API server for AI assistant connections
- `pythonpath/registration.py`: Extension lifecycle management
- `META-INF/manifest.xml`: Extension packaging manifest
- `Addons.xcu`: LibreOffice menu and toolbar configuration
- `ProtocolHandler.xcu`: Protocol handler registration
- `description.xml`: Extension metadata and information
- `build.sh`: Script to build the .oxt extension package
- `install.sh`: Installation and management utilities
- `test_plugin.py`: Testing client for the plugin HTTP API
- `README.md`: Comprehensive plugin documentation

### Tests (`tests/`)
- **`test_client.py`**: Interactive test client that demonstrates all MCP tools
- **`test_insert_fix.py`**: Specific tests for document text insertion functionality
- **`__init__.py`**: Test package initialization

### Examples (`examples/`)
- **`demo_editing.py`**: Comprehensive demo showing document editing capabilities
- **`demo_live_viewing.py`**: Demo of live document viewing and real-time editing
- **`__init__.py`**: Examples package initialization

### Configuration (`config/`)
- **`claude_config.json.template`**: Template for Claude Desktop MCP configuration
- **`mcp.config.json.template`**: Template for Super Assistant proxy configuration

### Scripts (`scripts/`)
- **`generate-config.sh`**: Generates personalized configuration files from templates
- **`mcp-helper.sh`**: Comprehensive helper script for testing, setup, and management

### Documentation (`docs/`)
- **Setup Guides**: Step-by-step instructions for different integration scenarios
- **Usage Examples**: Practical examples and use cases
- **Troubleshooting**: Common issues and solutions
- **Prerequisites**: System requirements and installation instructions

## 🚀 Quick Access

### Root Level Wrappers
For convenience, wrapper scripts are provided in the root directory:

```bash
# These are equivalent:
./mcp-helper.sh check          # Wrapper script
./scripts/mcp-helper.sh check  # Direct access

./generate-config.sh both      # Wrapper script  
./scripts/generate-config.sh both  # Direct access
```

### Running Components

```bash
# Run the MCP server directly
uv run python src/main.py

# Run tests
uv run python tests/test_client.py

# Run examples
uv run python examples/demo_editing.py

# Use helper scripts
./mcp-helper.sh test
./generate-config.sh claude
```

## 📦 Package Structure

The project follows Python packaging best practices:

- **Source code** is in `src/` (src layout)
- **Tests** are separate from source code
- **Examples** are clearly separated from core functionality
- **Configuration** templates are centralized
- **Scripts** are organized in their own directory
- **Documentation** is comprehensive and well-organized

## 🔧 Build and Installation

The `pyproject.toml` file is configured for the new structure:

```toml
[project.scripts]
mcp-libre = "src.libremcp:main"
```

This allows the package to be installed and run as:
```bash
uv pip install -e .  # Install in development mode
mcp-libre             # Run the installed script
```

## 🔍 Path Management

All scripts automatically handle the new directory structure:

- **generate-config.sh**: Uses `PROJECT_ROOT` to find templates and generate correct paths
- **mcp-helper.sh**: Uses `PROJECT_ROOT` to run tests and examples from correct locations
- **Test files**: Add `src/` to Python path automatically
- **Example files**: Add `src/` to Python path automatically

This ensures everything works regardless of where the repository is installed or how scripts are executed.
