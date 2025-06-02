# MCP 代理技术文档

## 概述

MCP-Dock 的代理功能提供了一个统一的接口来访问和管理多个 MCP 服务器。代理系统支持多种传输协议，包括 SSE（Server-Sent Events）和 StreamableHTTP，并提供了工具过滤、聚合等高级功能。

## 架构设计

### 核心组件

1. **代理管理器 (ProxyManager)**
   - 位置: `mcp_dock/core/mcp_proxy.py`
   - 功能: 管理代理配置、路由请求、处理响应

2. **动态代理路由 (DynamicProxy)**
   - 位置: `mcp_dock/api/routes/dynamic_proxy.py`
   - 功能: 处理 HTTP 请求路由、SSE 连接管理

3. **SSE 会话管理器 (SSESessionManager)**
   - 位置: `mcp_dock/core/sse_session_manager.py`
   - 功能: 管理 SSE 连接生命周期、消息队列

## 传输协议支持

### 1. SSE (Server-Sent Events)

**特点:**
- 实时双向通信
- 自动重连机制
- 支持流式响应

**实现细节:**
- 端点格式: `/api/proxy/{proxy_name}/sse`
- 会话管理: 自动创建和清理会话
- 消息格式: JSON-RPC 2.0

**关键修复:**
- ✅ 修复了 MCP Inspector v0.13.0 的 `nextCursor` 验证错误
- ✅ 为 `resources/list` 和 `resources/templates/list` 提供默认空响应
- ✅ 完善了 Pydantic 模型验证

### 2. StreamableHTTP

**特点:**
- 基于 HTTP POST 的请求-响应模式
- 支持批量操作
- 简单的集成方式

**实现细节:**
- 端点格式: `/api/proxy/{proxy_name}/messages`
- 响应格式: 标准 JSON-RPC 2.0
- 状态码: 202 Accepted (异步处理)

## 配置管理

### 代理配置文件

位置: `mcp_dock/config/proxy_config.json`

```json
{
    "mcpProxies": {
        "Tavily_Proxy": {
            "server_name": "Tavily",
            "endpoint": "/tavily",
            "transport_type": "streamableHTTP",
            "exposed_tools": [],
            "enable_aggregation": false
        }
    }
}
```

### 配置参数说明

- `server_name`: 关联的 MCP 服务器名称
- `endpoint`: 代理端点路径
- `transport_type`: 传输协议类型 (`sse` | `streamableHTTP`)
- `exposed_tools`: 暴露的工具列表（空数组表示全部暴露）
- `enable_aggregation`: 是否启用聚合代理功能

## 核心功能

### 1. 方法路由

支持的 MCP 方法:
- `initialize`: 初始化连接
- `tools/list`: 获取工具列表
- `tools/call`: 调用工具
- `resources/list`: 获取资源列表 ✨
- `resources/templates/list`: 获取资源模板列表 ✨

### 2. 资源方法处理

**问题背景:**
MCP Inspector v0.13.0 期望资源方法返回特定格式的响应，但某些 MCP 服务器（如 Tavily）不支持这些方法。

**解决方案:**
在代理层拦截并提供默认响应:

```python
# resources/list 默认响应
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {"resources": []}
}

# resources/templates/list 默认响应
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {"resourceTemplates": []}
}
```

### 3. 工具过滤

**配置方式:**
- 空数组 `[]`: 暴露所有工具
- 指定工具名: 只暴露列表中的工具

**实现位置:**
- `handle_tools_list_request()` 函数
- 支持动态过滤和权限控制

## 错误处理

### 1. Pydantic 验证错误修复

**问题:** `AttributeError: type object 'dict' has no attribute 'model_validate'`

**解决方案:**
- 为特定 MCP 方法使用正确的 Pydantic 模型类型
- 创建 `GenericResult` 包装器处理未知方法

### 2. nextCursor 验证错误修复

**问题:** MCP Inspector 期望 `nextCursor` 为字符串，但收到 `null`

**解决方案:**
- 在代理层提供符合协议的默认响应
- 避免将不支持的方法转发到后端服务器

## 性能优化

### 1. 会话管理

- 自动清理过期会话（默认 5 分钟超时）
- 定期清理任务（每 60 秒执行一次）
- 优雅的连接关闭处理

### 2. 消息队列

- 异步消息处理
- 支持并发连接
- 内存高效的队列管理

## 调试和监控

### 日志级别

- `INFO`: 基本操作日志
- `DEBUG`: 详细调试信息
- `ERROR`: 错误和异常

### 关键日志标识

- `📡 StreamableHTTP request`: HTTP 请求处理
- `📤 StreamableHTTP response`: HTTP 响应发送
- `🔗 SSE connection`: SSE 连接事件
- `📨 SSE message`: SSE 消息传输

## 兼容性

### MCP Inspector 版本支持

- ✅ v0.13.0: 完全兼容，包括 nextCursor 验证
- ✅ 早期版本: 向后兼容

### MCP 协议版本

- 支持 JSON-RPC 2.0
- 兼容 MCP 协议规范
- 支持标准和扩展方法

## 故障排除

### 常见问题

1. **代理未找到错误**
   - 检查代理配置文件
   - 确认代理名称正确

2. **工具列表为空**
   - 检查 `exposed_tools` 配置
   - 确认后端服务器连接状态

3. **SSE 连接失败**
   - 检查网络连接
   - 确认端点 URL 正确

### 调试步骤

1. 检查服务器日志
2. 验证代理配置
3. 测试后端服务器连接
4. 检查防火墙和网络设置
