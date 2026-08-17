# LibreOffice MCP Extension

## 🎯 Overview

The LibreOffice MCP Extension is a LibreOffice-native HTTP tool bridge designed for MCP integration, enabling AI assistants to interact with LibreOffice documents in real-time through direct UNO API access. It exposes a custom REST API (`GET /tools`, `POST /execute`, `POST /tools/{tool_name}`), not native MCP JSON-RPC (`tools/list`, `tools/call`); pairing it with an MCP client currently requires an MCP-to-REST adapter. For an actual MCP server usable directly with Claude Desktop today, see the external Python server under `src/` (`src/libremcp.py`).

> **Note on version numbers:** This extension (OXT) is versioned independently from the external Python MCP server package in `pyproject.toml`. The two `1.0.0` / `0.1.0` numbers are not meant to track each other.

## 🚀 Key Features

### **Real-time Document Manipulation**
- Create documents directly in LibreOffice (Writer, Calc, Impress, Draw)
- Insert and format text in active documents
- Live document editing without file I/O overhead
- Enumerates all open documents; editing operations target the active document

### **Advanced Document Operations**
- Save and export documents to various formats (PDF, DOCX, ODT, etc.)
- Get comprehensive document information and statistics
- Real-time text content extraction
- Format text with fonts, styles, and attributes

### **AI Assistant Integration**
- HTTP API server running on localhost:8765
- LibreOffice-native HTTP tool bridge designed for MCP integration (custom REST API, not native MCP JSON-RPC)
- RESTful endpoints for easy integration
- Real-time status monitoring and control
- Trusted-localhost-only: the server validates Host/Origin headers and rejects non-localhost requests, but has no authentication -- any process on the local machine can call every tool

### **Native LibreOffice Integration**
- Appears in LibreOffice Tools menu
- Manually started via Tools → MCP Server → Start MCP Server (does not auto-start with LibreOffice)
- Professional .oxt extension format

## 📋 Installation

### **Method 1: Extension Manager (Recommended)**
1. Download `libreoffice-mcp-extension.oxt`
2. Open LibreOffice
3. Go to **Tools > Extension Manager**
4. Click **Add** and select the .oxt file
5. Restart LibreOffice

### **Method 2: Command Line**
```bash
unopkg add libreoffice-mcp-extension.oxt
```

### **Method 3: Build from Source**
```bash
cd plugin/
./build.sh
unopkg add ../build/libreoffice-mcp-extension.oxt
```

## 🔧 Usage

### **Manual Control**
After installation, access MCP server controls via:
- **Tools > MCP Server** (menu)
- Use the toolbar button for quick toggle

Available commands:
- **Start MCP Server**: Begins the HTTP API server
- **Stop MCP Server**: Stops the server
- **Restart MCP Server**: Restarts the server
- **Show Server Status**: Displays current status

### **HTTP API Endpoints**

The extension starts an HTTP server on `http://localhost:8765` with the following endpoints:

#### **GET Endpoints**
```bash
# Server information
curl http://localhost:8765/

# List available tools
curl http://localhost:8765/tools

# Health check
curl http://localhost:8765/health
```

#### **POST Endpoints**
```bash
# Execute a specific tool
curl -X POST http://localhost:8765/tools/create_document_live \
  -H "Content-Type: application/json" \
  -d '{"doc_type": "writer"}'

# Execute tool via generic endpoint
curl -X POST http://localhost:8765/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "insert_text_live",
    "parameters": {
      "text": "Hello from AI assistant!"
    }
  }'
```

## 🛠️ Available MCP Tools

### **Document Creation**
- `create_document_live`: Create new Writer, Calc, Impress, or Draw documents
- Parameters: `doc_type` (writer|calc|impress|draw)

### **Text Manipulation**
- `insert_text_live`: Insert text at cursor or specific position
- `format_text_live`: Apply formatting to selected text
- `get_text_content_live`: Extract text content from document

### **Document Information**
- `get_document_info_live`: Get comprehensive document details
- `list_open_documents`: List all currently open documents

### **File Operations**
- `save_document_live`: Save active document
- `export_document_live`: Export to PDF, DOCX, ODT, TXT, etc.

## 🔗 AI Assistant Configuration

### **Claude Desktop Setup**
Claude Desktop's `mcpServers` configuration launches a real MCP server process (stdio or a Streamable HTTP MCP endpoint); it does not support substituting arbitrary values like `{{tool}}`/`{{parameters}}` into a fixed `curl` command, so a config in that shape is not functional. This extension currently exposes a plain REST API, not a Streamable HTTP MCP endpoint, so there is no working `mcpServers` entry for it yet -- using it from Claude Desktop today would require either a real MCP transport added to this extension or a separate MCP-to-REST adapter process in between.

For a working MCP server you can point Claude Desktop at today, use the external Python server under `src/` (`src/libremcp.py`), which implements actual MCP via the `mcp` SDK.

### **Super Assistant Integration**
Configure the MCP proxy to point to:
```
http://localhost:8765
```

## 🎮 Example Usage

### **Create and Edit Document**
```bash
# Create a new Writer document
curl -X POST http://localhost:8765/tools/create_document_live \
  -H "Content-Type: application/json" \
  -d '{"doc_type": "writer"}'

# Insert text
curl -X POST http://localhost:8765/tools/insert_text_live \
  -H "Content-Type: application/json" \
  -d '{"text": "This is AI-generated content!"}'

# Apply formatting to selected text
curl -X POST http://localhost:8765/tools/format_text_live \
  -H "Content-Type: application/json" \
  -d '{
    "bold": true,
    "font_size": 14,
    "font_name": "Arial"
  }'

# Save document
curl -X POST http://localhost:8765/tools/save_document_live \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/home/user/Documents/ai-document.odt"}'

# Export to PDF
curl -X POST http://localhost:8765/tools/export_document_live \
  -H "Content-Type: application/json" \
  -d '{
    "export_format": "pdf",
    "file_path": "/home/user/Documents/ai-document.pdf"
  }'
```

### **Document Analysis**
```bash
# Get document information (targets the active document)
curl -X POST http://localhost:8765/tools/get_document_info_live \
  -H "Content-Type: application/json" \
  -d '{}'

# Extract text content (targets the active document)
curl -X POST http://localhost:8765/tools/get_text_content_live \
  -H "Content-Type: application/json" \
  -d '{}'

# List all open documents (enumeration only; editing tools still target the active document)
curl -X POST http://localhost:8765/tools/list_open_documents \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 🔄 Comparison with External MCP Server

| Feature | External Server | Plugin Extension |
|---------|----------------|------------------|
| **Performance** | ⭐⭐ (file I/O) | ⭐⭐⭐⭐⭐ (direct API) |
| **Real-time Editing** | ⭐⭐ (file-based) | ⭐⭐⭐⭐⭐ (live objects) |
| **Installation** | ⭐⭐⭐⭐ (simple) | ⭐⭐⭐ (extension install) |
| **Multi-document** | ⭐⭐ (file ops) | ⭐⭐⭐⭐ (enumerates all open docs; edits target the active one) |
| **GUI Integration** | ⭐ (none) | ⭐⭐⭐⭐⭐ (native menus) |
| **Startup Time** | ⭐⭐ (LibreOffice launch) | ⭐⭐⭐⭐⭐ (instant) |

## 🛠️ Technical Architecture

```
AI Assistant (Claude/Super Assistant)
     ↓ (HTTP API calls)
LibreOffice Plugin Extension
     ↓ (UNO API - direct access)
LibreOffice Internal Components
     ↓ (direct memory access)
Documents & Data Structures
```

### **Core Components**
- **UNO Bridge**: Direct LibreOffice API integration
- **MCP Server**: Embedded protocol server
- **AI Interface**: HTTP API for external connections
- **Extension Registration**: LibreOffice lifecycle management

## 🐛 Troubleshooting

### **Extension Not Loading**
1. Check LibreOffice version (tested on LibreOffice 24.2 and later, matching the root README)
2. Verify Python environment
3. Check Extension Manager for conflicts
4. Review LibreOffice error logs

### **HTTP Server Not Starting**
1. Verify port 8765 is available
2. Check firewall settings
3. Review extension logs
4. Try restarting LibreOffice

### **Tool Execution Errors**
1. Ensure document is open for document-specific tools
2. Check parameter formats in API calls
3. Verify LibreOffice permissions
4. Check UNO API compatibility

### **Getting Help**
- Check LibreOffice extension logs
- Use `curl http://localhost:8765/health` for server status
- Access **Tools > MCP Server > Show Server Status**
- Visit project GitHub repository for issues

## 📝 Development

### **Building from Source**
```bash
git clone https://github.com/kittrellbj/mcp-libre.git
cd mcp-libre/plugin
./build.sh
```

### **Installing Development Version**
```bash
unopkg remove org.mcp.libreoffice.extension  # Remove old version
unopkg add ../build/libreoffice-mcp-extension.oxt
```

### **Debugging**
- Enable LibreOffice Basic IDE debugging
- Check Python console output
- Monitor HTTP server logs
- Use UNO reflection tools

## 📜 License

This extension is released under the MIT License. See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please check the main project repository for contribution guidelines.

---

**Happy AI-powered document editing with LibreOffice! 🎉**
