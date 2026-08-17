# Pull Request: LibreOffice Plugin/Extension Implementation

> **Historical PR record.** This document captures the original plugin PR description and is kept for history; some claims below (auto-start, "10x", multi-document editing) have since been corrected. See `plugin/README.md` and the root `README.md` for the current, accurate description.

## 🎯 Overview

This PR implements a **complete LibreOffice plugin/extension** that provides a LibreOffice-native HTTP tool bridge designed for MCP integration, offering plausibly improved performance and real-time document manipulation capabilities.

## 🚀 Major Features Added

### ✨ Native LibreOffice Extension
- **Embedded HTTP Tool Server**: Runs directly inside LibreOffice using UNO API (custom REST API, not native MCP JSON-RPC)
- **Improved Performance**: Direct API access, plausibly faster than subprocess calls (no benchmark numbers published)
- **Real-time Document Editing**: Live manipulation with instant visual feedback
- **HTTP API Interface**: AI assistants connect to `localhost:8765`
- **Multi-document Awareness**: Enumerates all open LibreOffice documents; editing operations target the active document

### 🏗️ Core Implementation
- **UNO Bridge** (`plugin/pythonpath/uno_bridge.py`): Direct LibreOffice API integration
- **Embedded MCP Server** (`plugin/pythonpath/mcp_server.py`): All MCP tools using UNO API
- **AI Interface** (`plugin/pythonpath/ai_interface.py`): HTTP server for external connections
- **Extension Registration** (`plugin/pythonpath/registration.py`): LibreOffice lifecycle management

### 🔧 Professional Tooling
- **Automated Build System**: `plugin/build.sh` for .oxt packaging
- **Installation Manager**: `plugin/install.sh` with comprehensive commands
- **Testing Suite**: `plugin/test_plugin.py` with interactive testing mode
- **Status Monitoring**: Health checks and server status reporting

## 📊 Performance Comparison

| Feature | External Server | LibreOffice Plugin |
|---------|----------------|-------------------|
| **Performance** | ⭐⭐ (subprocess calls) | ⭐⭐⭐⭐⭐ (direct UNO API) |
| **Real-time Editing** | ⭐⭐ (file-based) | ⭐⭐⭐⭐⭐ (live objects) |
| **GUI Integration** | ⭐ (none) | ⭐⭐⭐⭐⭐ (native menus) |
| **Multi-document** | ⭐⭐ (file operations) | ⭐⭐⭐⭐ (enumerates all open docs; edits target the active one) |
| **Startup Time** | ⭐⭐ (LibreOffice launch) | ⭐⭐⭐⭐⭐ (instant) |

## 🛠️ New MCP Tools (Plugin Version)

- `create_document_live`: Create documents with instant GUI appearance
- `insert_text_live`: Insert text with real-time visual updates
- `format_text_live`: Apply formatting with live preview (NEW!)
- `get_document_info_live`: Multi-document information retrieval
- `save_document_live`: Save without file I/O overhead
- `export_document_live`: Instant export to PDF/DOCX/etc
- `list_open_documents`: Multi-document support (NEW!)
- `get_text_content_live`: Direct memory text extraction

## 📁 Files Added/Modified

### New Plugin Directory (`plugin/`)
```
plugin/
├── META-INF/manifest.xml           # Extension packaging manifest
├── pythonpath/                     # Python extension modules
│   ├── uno_bridge.py               # UNO API bridge
│   ├── mcp_server.py               # Embedded MCP server
│   ├── ai_interface.py             # HTTP API server
│   └── registration.py             # Extension lifecycle
├── Addons.xcu                      # LibreOffice menu configuration
├── ProtocolHandler.xcu             # Protocol handler registration
├── description.xml                 # Extension metadata
├── build.sh                        # Build automation (executable)
├── install.sh                      # Installation manager (executable)
├── test_plugin.py                  # Testing client (executable)
└── README.md                       # Plugin documentation
```

### Documentation Added/Updated
- **`plugin/README.md`**: Comprehensive plugin documentation
- **`plugin/IMPLEMENTATION_SUMMARY.md`**: Technical architecture overview
- **`docs/PLUGIN_MIGRATION_GUIDE.md`**: Migration from external server guide
- **`README.md`**: Updated with plugin integration information
- **`docs/REPOSITORY_STRUCTURE.md`**: Updated directory structure

## 🔗 AI Assistant Integration

### Claude Desktop Configuration
No functional `mcpServers` entry exists for the plugin's REST API -- Claude Desktop launches a real MCP server process and cannot substitute placeholders into a fixed `curl` command. Use the external server (`src/libremcp.py`) for Claude Desktop until the plugin exposes a real Streamable HTTP MCP endpoint or is paired with an MCP-to-REST adapter.

### Super Assistant Integration
- **Direct Connection**: `http://localhost:8765` (no proxy needed!)
- **Real-time Updates**: See changes instantly in LibreOffice GUI

## 📦 Installation & Usage

### Quick Start
```bash
cd plugin/
./install.sh install    # Build and install extension
./install.sh test       # Verify functionality
./install.sh status     # Check status
```

### Management Commands
```bash
./install.sh build      # Build .oxt package only
./install.sh uninstall  # Remove extension
./install.sh interactive # Interactive testing mode
```

### HTTP API Examples
```bash
# Create document (appears instantly in LibreOffice)
curl -X POST http://localhost:8765/tools/create_document_live \
  -H "Content-Type: application/json" \
  -d '{"doc_type": "writer"}'

# Insert text with live preview
curl -X POST http://localhost:8765/tools/insert_text_live \
  -H "Content-Type: application/json" \
  -d '{"text": "Real-time AI content!"}'
```

## 🎯 Benefits

### For Users
- **Improved Performance**: Direct UNO API, plausibly faster than subprocess overhead
- **Real-time Feedback**: See AI changes instantly in LibreOffice
- **Native Experience**: Integrated Tools menu (manually started, does not auto-start)
- **Multi-document Awareness**: Enumerate all open documents; editing operations target the active one

### For Developers
- **Direct API Access**: Full LibreOffice UNO API capabilities
- **Professional Architecture**: Standard extension format
- **Extensible Design**: Easy to add new features
- **Comprehensive Testing**: Automated test suite

### For AI Assistants
- **Simple Integration**: HTTP API on localhost:8765 (custom REST, not native MCP JSON-RPC)
- **Rich Functionality**: Document lifecycle tools across Writer, Calc, Impress, and Draw, plus a Writer-focused live editing surface
- **Real-time Operations**: Live document manipulation
- **Multi-client Support**: Concurrent connections

## 🧪 Testing

### Automated Testing
- **Comprehensive Test Suite**: `plugin/test_plugin.py`
- **Health Checks**: Server status and connectivity tests
- **Interactive Mode**: Manual testing with all tools
- **Status Monitoring**: Extension and server status checks

### Manual Testing
1. Install extension: `./install.sh install`
2. Start LibreOffice
3. Check **Tools > MCP Server** menu
4. Test API: `curl http://localhost:8765/health`
5. Run tests: `./install.sh test`

## 🔄 Migration Support

### Smooth Transition
- **Parallel Installation**: Plugin coexists with external server
- **Migration Guide**: Step-by-step transition documentation
- **Backward Compatibility**: All existing tools supported
- **Enhanced Features**: New capabilities only in plugin

### Migration Benefits
- **Performance**: Plausibly faster operations via direct API access (no benchmark numbers published)
- **Features**: Real-time editing and multi-document enumeration (edits still target the active document)
- **Reliability**: Direct API access (no subprocess overhead)
- **Integration**: Native LibreOffice controls

## 🏆 Impact

This implementation represents a **major evolution** of the project:

### Architecture Evolution
- **From**: External Python server launching LibreOffice
- **To**: Integrated extension running inside LibreOffice

### Performance Evolution
- **From**: File I/O operations for document manipulation
- **To**: Direct memory object manipulation via UNO API

### Capability Evolution
- **From**: Static batch operations with no visual feedback
- **To**: Live editing with instant visual updates

### Integration Evolution
- **From**: External tool requiring manual setup
- **To**: Native extension with professional deployment

## ✅ Checklist

- [x] Complete LibreOffice extension implementation
- [x] All MCP tools ported to UNO API
- [x] HTTP API server for AI assistant integration
- [x] Professional .oxt packaging with automated build
- [x] Comprehensive installation and management scripts
- [x] Extensive testing suite with interactive mode
- [x] Complete documentation and migration guides
- [x] Updated main project documentation
- [x] Backward compatibility maintained
- [ ] Performance benchmarking completed (no formal benchmark numbers were published)

## 🚀 Ready to Merge

This PR is **ready for review and merge**. It provides:

- **Complete Implementation**: Production-ready LibreOffice extension
- **Professional Quality**: Standard extension format with proper packaging
- **Comprehensive Testing**: Automated and manual test coverage
- **Full Documentation**: User guides, API docs, and migration instructions
- **Backward Compatibility**: Existing external server continues to work
- **Enhanced Capabilities**: plausibly improved performance and real-time features (no benchmark numbers published)

The plugin represents the **future of LibreOffice MCP integration** while maintaining full compatibility with existing workflows.

---

**Files Changed**: 18 files, 2,873 insertions, 14 deletions  
**Commit**: `fa1fe67` - feat: Add LibreOffice Plugin/Extension Implementation  
**Branch**: `devplugin` → `main`
