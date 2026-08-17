# 🔄 Migration Guide: External Server → LibreOffice Plugin

## 🎯 Overview

This guide helps you migrate from the external MCP server to the new LibreOffice plugin extension, which provides significantly better performance and capabilities.

> **Note:** The plugin exposes a custom REST API (`GET /tools`, `POST /execute`, `POST /tools/{tool_name}`), not native MCP JSON-RPC. It is a LibreOffice-native HTTP tool bridge designed for MCP integration, not a drop-in MCP server -- the Claude Desktop configuration snippets below are conceptual/nonfunctional until a real Streamable HTTP MCP endpoint or an MCP-to-REST adapter exists. For working Claude Desktop integration today, use the external server (`src/libremcp.py`), which is real MCP via the `mcp` SDK.

## 📊 Benefits of Migration

| Feature | External Server | LibreOffice Plugin |
|---------|----------------|-------------------|
| **Performance** | ⭐⭐ (subprocess calls) | ⭐⭐⭐⭐⭐ (direct UNO API) |
| **Real-time Editing** | ⭐⭐ (file-based) | ⭐⭐⭐⭐⭐ (live objects) |
| **Startup Time** | ⭐⭐ (LibreOffice startup) | ⭐⭐⭐⭐⭐ (instant) |
| **Multi-document** | ⭐⭐ (file operations) | ⭐⭐⭐⭐ (enumerates all open docs; edits target the active one) |
| **GUI Integration** | ⭐ (none) | ⭐⭐⭐⭐⭐ (native menus) |
| **Advanced Features** | ⭐⭐⭐ (limited) | ⭐⭐⭐⭐⭐ (full access) |

## 🚀 Quick Migration (5 Minutes)

### Step 1: Install the Plugin
```bash
cd plugin/
./install.sh install
```

### Step 2: Update AI Assistant Configuration

**For Claude Desktop:** there is currently no functional `mcpServers` entry for the plugin -- Claude Desktop launches a real MCP server process and cannot substitute placeholders like `TOOL_NAME`/`PARAMETERS` into a fixed `curl` command. Until the plugin exposes a real Streamable HTTP MCP endpoint (or is paired with an MCP-to-REST adapter), keep using the external server (`src/libremcp.py`) for Claude Desktop, which is documented in the root `README.md`.

**For Super Assistant:**
Change the server URL from your external server to:
```
http://localhost:8765
```

### Step 3: Test the Migration
```bash
./install.sh test
```

### Step 4: Remove External Server (Optional)
Once you've verified the plugin works, you can stop using the external server.

## 🔧 Detailed Migration Steps

### 1. Backup Current Configuration

**Claude Desktop:**
```bash
cp ~/.config/claude/claude_desktop_config.json ~/.config/claude/claude_desktop_config.json.backup
```

**Super Assistant:**
```bash
cp ~/Documents/mcp/mcp.config.json ~/Documents/mcp/mcp.config.json.backup
```

### 2. Install LibreOffice Plugin

```bash
# Navigate to plugin directory (adjust to your clone location)
cd /path/to/mcp-libre/plugin

# Check prerequisites
./install.sh status

# Install the extension
./install.sh install

# Restart LibreOffice
pkill soffice || true
libreoffice &
```

### 3. Verify Plugin Installation

```bash
# Check extension status
./install.sh status

# Run comprehensive tests
./install.sh test

# Interactive testing (optional)
./install.sh interactive
```

### 4. Update AI Assistant Configurations

#### Claude Desktop Migration

Replace your existing LibreOffice MCP server configuration:

**Before (External Server):**
```json
{
  "mcpServers": {
    "libreoffice": {
      "command": "python",
      "args": ["/path/to/mcp-libre/src/main.py"],
      "env": {
        "PYTHONPATH": "/path/to/mcp-libre"
      }
    }
  }
}
```

**After (Plugin):**

There is no working `mcpServers` entry for the plugin yet. Claude Desktop's `mcpServers` configuration launches a real MCP server process; it cannot dynamically substitute values like `TOOL_NAME`/`PARAMETERS` into a fixed `curl` command, so a config in that shape would not function. Using this REST API from Claude Desktop today would require either a real Streamable HTTP MCP endpoint added to the extension, or a separate MCP-to-REST adapter process. Until then, keep the external server (`src/libremcp.py`) configured for Claude Desktop and use the plugin's HTTP API directly (`curl`, scripts, or a custom client) instead.

#### Super Assistant Migration

**Before (External Server via Proxy):**
```bash
npx @srbhptl39/mcp-superassistant-proxy@latest --config ~/Documents/mcp/mcp.config.json
# Server URL: http://localhost:3006
```

**After (Direct Plugin):**
```
Server URL: http://localhost:8765
```
No proxy needed!

### 5. Test Migration Success

#### Basic Functionality Test
```bash
# Test server accessibility
curl http://localhost:8765/health

# List available tools
curl http://localhost:8765/tools

# Test document creation
curl -X POST http://localhost:8765/tools/create_document_live \
  -H "Content-Type: application/json" \
  -d '{"doc_type": "writer"}'
```

#### AI Assistant Test

**Claude Desktop:**
- Ask: *"Create a new Writer document and add some text"*
- Verify the document appears in LibreOffice

**Super Assistant:**
- Use the command: *"Create a document with the title 'Migration Test'"*
- Check that it works without the proxy

## 🔄 Tool Name Mapping

Most tool names remain the same, but some have new "live" variants:

| External Server | LibreOffice Plugin | Notes |
|----------------|-------------------|-------|
| `create_document` | `create_document_live` | Creates in active LibreOffice instance |
| `read_document_text` | `get_text_content_live` | Reads from active document |
| `insert_text_at_position` | `insert_text_live` | Inserts in active document |
| `get_document_info` | `get_document_info_live` | Gets info from active document |
| *(new)* | `format_text_live` | Apply formatting to selected text |
| *(new)* | `list_open_documents` | List all open documents |
| `convert_document` | `export_document_live` | Export active document |

## 🎯 New Capabilities with Plugin

### Real-time Editing
```bash
# Create document
curl -X POST http://localhost:8765/tools/create_document_live \
  -H "Content-Type: application/json" \
  -d '{"doc_type": "writer"}'

# Insert text (see it appear immediately in LibreOffice)
curl -X POST http://localhost:8765/tools/insert_text_live \
  -H "Content-Type: application/json" \
  -d '{"text": "Live editing in action!"}'

# Format the text (select it first in LibreOffice)
curl -X POST http://localhost:8765/tools/format_text_live \
  -H "Content-Type: application/json" \
  -d '{"bold": true, "font_size": 16}'
```

### Multi-document Support
```bash
# List all open documents (enumeration only)
curl -X POST http://localhost:8765/tools/list_open_documents \
  -H "Content-Type: application/json" \
  -d '{}'

# There is no document_id/handle parameter to target a specific document;
# editing tools operate on whichever document currently has focus in LibreOffice
```

### Advanced Document Operations
```bash
# Save current document
curl -X POST http://localhost:8765/tools/save_document_live \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/home/user/Documents/saved-doc.odt"}'

# Export to PDF
curl -X POST http://localhost:8765/tools/export_document_live \
  -H "Content-Type: application/json" \
  -d '{
    "export_format": "pdf",
    "file_path": "/home/user/Documents/exported.pdf"
  }'
```

## 🔧 Control and Management

### LibreOffice Menu Integration
After installation, access plugin controls via:
- **Tools > MCP Server > Start MCP Server**
- **Tools > MCP Server > Stop MCP Server**
- **Tools > MCP Server > Restart MCP Server**
- **Tools > MCP Server > Show Server Status**

### Command Line Management
```bash
# Check status
./install.sh status

# Restart if needed
./install.sh install

# Uninstall if necessary
./install.sh uninstall
```

## 🐛 Troubleshooting Migration

### Plugin Not Loading
```bash
# Check LibreOffice version
libreoffice --version  # Tested on LibreOffice 24.2 and later

# Verify extension installation
unopkg list | grep mcp

# Check error logs
journalctl -f | grep soffice
```

### HTTP Server Not Starting
```bash
# Check if port 8765 is in use
netstat -tlnp | grep 8765

# Restart LibreOffice
pkill soffice
libreoffice &

# Check plugin status
./install.sh status
```

### AI Assistant Connection Issues
```bash
# Test server manually
curl http://localhost:8765/health

# Verify configuration syntax
cat ~/.config/claude/claude_desktop_config.json | python3 -m json.tool

# Test tool execution
curl -X POST http://localhost:8765/tools/get_document_info_live
```

## 🎉 Migration Complete!

Once migrated successfully, you'll have:

✅ **Improved Performance** - Direct UNO API access, plausibly faster than subprocess/file round-tripping  
✅ **Real-time Visual Feedback** - See changes instantly  
✅ **Native Integration** - LibreOffice menu controls  
✅ **Multi-document Awareness** - Enumerate all open documents; editing operations target the active one  
✅ **Advanced Capabilities** - Full LibreOffice feature access  
✅ **Manual Start** - Started via Tools > MCP Server > Start MCP Server whenever you need it (does not auto-start with LibreOffice)  

Enjoy the enhanced LibreOffice MCP experience! 🚀

## 🔗 Resources

- **Plugin Documentation**: [`plugin/README.md`](../plugin/README.md)
- **Installation Guide**: [`plugin/install.sh help`](../plugin/install.sh)
- **Test Client**: [`plugin/test_plugin.py`](../plugin/test_plugin.py)
- **Original Design**: [`docs/LIBREOFFICE_PLUGIN_DESIGN.md`](LIBREOFFICE_PLUGIN_DESIGN.md)
