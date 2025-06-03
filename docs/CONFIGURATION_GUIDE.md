# Configuration Guide

This guide explains how to configure MCP-Dock for different use cases and transport combinations.

## 📁 Configuration Files

MCP-Dock uses two main configuration files:

1. **`mcp.config.json`** - Defines backend MCP services
2. **`proxy_config.json`** - Defines client-facing proxy endpoints

Both files are located in `mcp_dock/config/` directory.

## 🔧 MCP Service Configuration

### File: `mcp_dock/config/mcp.config.json`

This file defines the backend MCP services that MCP-Dock will manage.

### Basic Structure

```json
{
  "servers": {
    "service_name": {
      "command": "command_to_run",           // For stdio services
      "args": ["arg1", "arg2"],             // Command arguments
      "url": "https://example.com/mcp",     // For SSE services
      "transport_type": "stdio|sse",        // Backend transport type
      "auto_start": true|false,             // Auto-start on server boot
      "env": {                              // Environment variables
        "API_KEY": "your_api_key"
      }
    }
  }
}
```

### STDIO Service Example

```json
{
  "servers": {
    "notionApi": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "transport_type": "stdio",
      "auto_start": true,
      "env": {
        "NOTION_API_KEY": "secret_..."
      }
    },
    "filesystem": {
      "command": "python",
      "args": ["-m", "mcp.server.filesystem", "/allowed/path"],
      "transport_type": "stdio",
      "auto_start": true
    }
  }
}
```

### SSE Service Example

```json
{
  "servers": {
    "Tavily": {
      "url": "https://tavily.api.tadata.com/mcp/tavily/session-id",
      "transport_type": "sse",
      "auto_start": true
    },
    "RemoteAPI": {
      "url": "https://api.example.com/mcp/endpoint",
      "transport_type": "sse",
      "auto_start": false
    }
  }
}
```

### StreamableHTTP Service Example

```json
{
  "servers": {
    "HTTPService": {
      "url": "https://api.example.com/mcp/http",
      "transport_type": "streamableHTTP",
      "auto_start": true,
      "headers": {
        "Authorization": "Bearer your-token",
        "Content-Type": "application/json"
      }
    },
    "CustomAPI": {
      "url": "https://custom.api.com/mcp",
      "transport_type": "streamableHTTP",
      "auto_start": false,
      "headers": {
        "X-API-Key": "your-api-key"
      }
    }
  }
}
```

### Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | Yes (stdio) | Executable command |
| `args` | array | No | Command line arguments |
| `url` | string | Yes (sse) | SSE endpoint URL |
| `transport_type` | string | Yes | "stdio" or "sse" |
| `auto_start` | boolean | No | Auto-start on server boot (default: false) |
| `env` | object | No | Environment variables |

## 🌐 Proxy Configuration

### File: `mcp_dock/config/proxy_config.json`

This file defines client-facing proxy endpoints that expose backend services.

### Basic Structure

```json
{
  "proxies": {
    "ProxyName": {
      "server_name": "target_service",           // Backend service name
      "endpoint": "/endpoint_path",              // Client endpoint path
      "transport_type": "sse|streamableHTTP",    // Client transport type
      "exposed_tools": ["tool1", "tool2"]       // Filter tools (empty = all)
    }
  }
}
```

### Complete Example

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
    },
    "FileSystem_SSE": {
      "server_name": "filesystem",
      "endpoint": "/files",
      "transport_type": "sse",
      "exposed_tools": ["read_file", "write_file"]
    }
  }
}
```

### Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `server_name` | string | Yes | Name of backend service from mcp.config.json |
| `endpoint` | string | Yes | URL path for client connections |
| `transport_type` | string | Yes | "sse" or "streamableHTTP" |
| `exposed_tools` | array | No | Tool filter (empty array = expose all tools) |

## 🔄 Transport Type Combinations

### Supported Combinations

| Backend | Proxy | Status | Use Case |
|---------|-------|--------|----------|
| stdio | sse | ✅ | Local service → SSE clients |
| stdio | streamableHTTP | ✅ | Local service → MCP Inspector |
| sse | sse | ✅ | Remote service → SSE clients |
| sse | streamableHTTP | ✅ | Remote service → MCP Inspector |
| streamableHTTP | sse | ✅ | HTTP service → SSE clients |
| streamableHTTP | streamableHTTP | ✅ | HTTP service → MCP Inspector |

### Configuration Examples

#### 1. Local Service for MCP Inspector

```json
// mcp.config.json
{
  "servers": {
    "local_service": {
      "command": "python",
      "args": ["-m", "my_mcp_server"],
      "transport_type": "stdio",
      "auto_start": true
    }
  }
}

// proxy_config.json
{
  "proxies": {
    "Local_Inspector": {
      "server_name": "local_service",
      "endpoint": "/local",
      "transport_type": "streamableHTTP",
      "exposed_tools": []
    }
  }
}
```

#### 2. Remote Service for SSE Clients

```json
// mcp.config.json
{
  "servers": {
    "remote_api": {
      "url": "https://api.example.com/mcp",
      "transport_type": "sse",
      "auto_start": true
    }
  }
}

// proxy_config.json
{
  "proxies": {
    "Remote_SSE": {
      "server_name": "remote_api",
      "endpoint": "/remote",
      "transport_type": "sse",
      "exposed_tools": []
    }
  }
}
```

#### 3. StreamableHTTP Service for Both SSE and HTTP Clients

```json
// mcp.config.json
{
  "servers": {
    "http_service": {
      "url": "https://api.example.com/mcp/http",
      "transport_type": "streamableHTTP",
      "auto_start": true,
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  }
}

// proxy_config.json
{
  "proxies": {
    "HTTP_Inspector": {
      "server_name": "http_service",
      "endpoint": "/http",
      "transport_type": "streamableHTTP",
      "exposed_tools": []
    },
    "HTTP_SSE": {
      "server_name": "http_service",
      "endpoint": "/http-stream",
      "transport_type": "sse",
      "exposed_tools": []
    }
  }
}
```

#### 4. Mixed Environment

```json
// mcp.config.json
{
  "servers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "transport_type": "stdio",
      "auto_start": true,
      "env": {"NOTION_API_KEY": "secret_..."}
    },
    "tavily": {
      "url": "https://tavily.api.tadata.com/mcp/tavily/session",
      "transport_type": "sse",
      "auto_start": true
    },
    "custom_http": {
      "url": "https://custom.api.com/mcp",
      "transport_type": "streamableHTTP",
      "auto_start": true,
      "headers": {"X-API-Key": "your-key"}
    }
  }
}

// proxy_config.json
{
  "proxies": {
    "Notion_Inspector": {
      "server_name": "notion",
      "endpoint": "/notion",
      "transport_type": "streamableHTTP",
      "exposed_tools": []
    },
    "Notion_SSE": {
      "server_name": "notion",
      "endpoint": "/notion-stream",
      "transport_type": "sse",
      "exposed_tools": []
    },
    "Tavily_Inspector": {
      "server_name": "tavily",
      "endpoint": "/tavily",
      "transport_type": "streamableHTTP",
      "exposed_tools": ["search", "news_search"]
    },
    "Custom_HTTP_Inspector": {
      "server_name": "custom_http",
      "endpoint": "/custom",
      "transport_type": "streamableHTTP",
      "exposed_tools": []
    },
    "Custom_HTTP_SSE": {
      "server_name": "custom_http",
      "endpoint": "/custom-stream",
      "transport_type": "sse",
      "exposed_tools": []
    }
  }
}
```

## 🛠️ Advanced Configuration

### Tool Filtering

Use `exposed_tools` to limit which tools are available through a proxy:

```json
{
  "proxies": {
    "Limited_Proxy": {
      "server_name": "full_service",
      "endpoint": "/limited",
      "transport_type": "streamableHTTP",
      "exposed_tools": ["safe_tool_1", "safe_tool_2"]
    }
  }
}
```

### Environment Variables

Set environment variables for STDIO services:

```json
{
  "servers": {
    "secure_service": {
      "command": "python",
      "args": ["-m", "secure_mcp_server"],
      "transport_type": "stdio",
      "auto_start": true,
      "env": {
        "API_KEY": "your_api_key",
        "DEBUG": "false",
        "TIMEOUT": "30"
      }
    }
  }
}
```

### Multiple Endpoints for Same Service

You can create multiple proxies for the same backend service:

```json
{
  "proxies": {
    "Service_Inspector": {
      "server_name": "backend_service",
      "endpoint": "/inspector",
      "transport_type": "streamableHTTP",
      "exposed_tools": []
    },
    "Service_Stream": {
      "server_name": "backend_service",
      "endpoint": "/stream", 
      "transport_type": "sse",
      "exposed_tools": []
    },
    "Service_Limited": {
      "server_name": "backend_service",
      "endpoint": "/limited",
      "transport_type": "streamableHTTP",
      "exposed_tools": ["read_only_tool"]
    }
  }
}
```

## 🔍 Validation and Testing

### Validate Configuration

```bash
# Check configuration syntax
python -m json.tool mcp_dock/config/mcp.config.json
python -m json.tool mcp_dock/config/proxy_config.json

# Test service startup
uv run uvicorn mcp_dock.api.gateway:app --host 127.0.0.1 --port 8000
```

### Test Endpoints

```bash
# List all services and proxies
curl http://localhost:8000/api/service/
curl http://localhost:8000/api/proxy/

# Test specific proxy
curl -X POST http://localhost:8000/ProxyName/endpoint \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## 📝 Best Practices

1. **Use Descriptive Names**: Choose clear, descriptive names for services and proxies
2. **Separate Concerns**: Use different proxies for different client types
3. **Filter Tools**: Use `exposed_tools` to limit tool exposure for security
4. **Environment Variables**: Store sensitive data in environment variables
5. **Auto-start Critical Services**: Set `auto_start: true` for essential services
6. **Test Configurations**: Always test after configuration changes

## 🚨 Common Mistakes

1. **Mismatched Names**: Ensure `server_name` in proxy config matches service name in mcp config
2. **Wrong Transport Types**: Don't mix up backend and proxy transport types
3. **Missing Environment Variables**: Ensure required environment variables are set
4. **Port Conflicts**: Avoid port conflicts with other services
5. **Invalid JSON**: Validate JSON syntax before starting server

This configuration system provides maximum flexibility while maintaining simplicity for common use cases.
