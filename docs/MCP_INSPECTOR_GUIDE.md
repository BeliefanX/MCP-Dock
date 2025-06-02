# MCP Inspector Integration Guide

This guide explains how to use MCP Inspector with MCP-Dock for debugging and testing MCP services.

## 🎯 Overview

MCP-Dock provides full compatibility with [MCP Inspector](https://github.com/modelcontextprotocol/inspector), the official debugging tool for Model Context Protocol services. You can connect MCP Inspector to any StreamableHTTP proxy endpoint to inspect tools, test functionality, and debug issues.

## ✅ Supported Features

MCP Inspector can use all standard MCP features through MCP-Dock:

- ✅ **Protocol Initialization** - Full handshake support
- ✅ **Tool Discovery** - List all available tools
- ✅ **Tool Execution** - Execute tools with parameters
- ✅ **Resource Listing** - Compatible empty responses
- ✅ **Error Handling** - Proper JSON-RPC error responses
- ✅ **Validation** - Zod schema validation compatibility

## 🔧 Setup Instructions

### 1. Configure Proxy for StreamableHTTP

Ensure your proxy configuration uses `streamableHTTP` transport type:

```json
{
  "proxies": {
    "Notion_MCP": {
      "server_name": "notionApi",
      "endpoint": "/notion",
      "transport_type": "streamableHTTP",
      "exposed_tools": []
    },
    "Tavily_Proxy": {
      "server_name": "Tavily",
      "endpoint": "/tavily",
      "transport_type": "streamableHTTP", 
      "exposed_tools": []
    }
  }
}
```

### 2. Start MCP-Dock

```bash
# Start the server
uv run uvicorn mcp_dock.api.gateway:app --host 0.0.0.0 --port 8000

# Verify proxies are running
curl http://localhost:8000/api/proxy/
```

### 3. Connect MCP Inspector

Use these endpoint URLs in MCP Inspector:

- **Notion MCP**: `http://localhost:8000/Notion_MCP/notion`
- **Tavily Proxy**: `http://localhost:8000/Tavily_Proxy/tavily`

## 🌐 Connection Examples

### Example 1: Notion MCP Service

1. **Backend**: STDIO (local Notion MCP server)
2. **Proxy**: StreamableHTTP
3. **Inspector URL**: `http://localhost:8000/Notion_MCP/notion`

```bash
# Test connection manually
curl -X POST http://localhost:8000/Notion_MCP/notion \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "mcp-inspector",
        "version": "1.0.0"
      }
    }
  }'
```

### Example 2: Tavily API Service

1. **Backend**: SSE (remote Tavily API)
2. **Proxy**: StreamableHTTP
3. **Inspector URL**: `http://localhost:8000/Tavily_Proxy/tavily`

```bash
# Test connection manually
curl -X POST http://localhost:8000/Tavily_Proxy/tavily \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

## 🔍 Troubleshooting

### Common Issues

#### 1. "MCP error -32001: fetch failed"

**Cause**: Proxy not running or incorrect URL
**Solution**:
```bash
# Check proxy status
curl http://localhost:8000/api/proxy/

# Start proxy if stopped
curl -X POST http://localhost:8000/api/proxy/ProxyName/start
```

#### 2. Zod Validation Errors

**Cause**: Response format incompatibility
**Solution**: MCP-Dock automatically fixes these issues. If you see Zod errors:

```bash
# Check server logs for detailed error information
# Ensure you're using the latest version of MCP-Dock
```

#### 3. "capabilities.logging is null" Error

**Cause**: Backend service returns null values
**Solution**: MCP-Dock automatically converts null values to proper objects. This should not occur with current versions.

#### 4. Empty Tool List

**Cause**: Proxy hasn't synced tools from backend
**Solution**:
```bash
# Refresh tool list
curl -X POST http://localhost:8000/api/proxy/ProxyName/update-tools

# Check backend service status
curl http://localhost:8000/api/service/
```

### Debug Steps

1. **Verify Server Status**
   ```bash
   curl http://localhost:8000/api/service/
   ```

2. **Check Proxy Status**
   ```bash
   curl http://localhost:8000/api/proxy/
   ```

3. **Test Direct Connection**
   ```bash
   curl -X POST http://localhost:8000/ProxyName/endpoint \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
   ```

4. **Check Browser Console**
   - Open browser developer tools
   - Look for network errors or validation issues
   - Check for CORS or connectivity problems

## 🎛️ Advanced Configuration

### Custom Proxy Settings

For specific MCP Inspector requirements, you can customize proxy behavior:

```json
{
  "proxies": {
    "Custom_Proxy": {
      "server_name": "backend_service",
      "endpoint": "/custom",
      "transport_type": "streamableHTTP",
      "exposed_tools": ["specific_tool_1", "specific_tool_2"]
    }
  }
}
```

### Multiple Inspector Instances

You can connect multiple MCP Inspector instances to different proxies simultaneously:

- Inspector 1 → `http://localhost:8000/Notion_MCP/notion`
- Inspector 2 → `http://localhost:8000/Tavily_Proxy/tavily`
- Inspector 3 → `http://localhost:8000/Custom_Proxy/custom`

## 📊 Monitoring Inspector Connections

### View Active Sessions

```bash
# Check active SSE sessions (if any)
curl http://localhost:8000/debug/sessions

# Monitor proxy activity
curl http://localhost:8000/api/proxy/
```

### Server Logs

Monitor server logs for Inspector connection activity:

```bash
# Look for these log patterns:
# "StreamableHTTP request for ProxyName: initialize"
# "Proxy ProxyName Response: id=1, result=success"
```

## 🚀 Best Practices

1. **Use StreamableHTTP for Inspector**: Always configure proxies with `streamableHTTP` transport type for MCP Inspector compatibility.

2. **Test Connection First**: Use curl to test endpoints before connecting Inspector.

3. **Monitor Tool Counts**: Ensure proxies show the expected number of tools.

4. **Check Backend Health**: Verify backend services are running and responsive.

5. **Update Tool Lists**: Refresh proxy tool lists after backend changes.

## 📝 Example Workflow

1. **Start MCP-Dock**
   ```bash
   ./start.sh
   ```

2. **Verify Configuration**
   ```bash
   curl http://localhost:8000/api/proxy/
   ```

3. **Test Endpoint**
   ```bash
   curl -X POST http://localhost:8000/Notion_MCP/notion \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

4. **Connect Inspector**
   - Open MCP Inspector
   - Enter URL: `http://localhost:8000/Notion_MCP/notion`
   - Select transport: `streamableHTTP`
   - Click Connect

5. **Debug and Test**
   - Browse available tools
   - Test tool execution
   - Monitor server logs

This integration allows you to leverage MCP Inspector's powerful debugging capabilities while using MCP-Dock's flexible proxy system.
