"""
MCP Proxy API Routes
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from mcp_dock.core.mcp_proxy import McpProxyConfig, McpProxyInstance, McpProxyManager
from mcp_dock.core.mcp_service import McpServiceManager
from mcp_dock.utils.logging_config import get_logger

logger = get_logger(__name__)


# Initialize API routes
router = APIRouter(prefix="/api/proxy", tags=["proxy"])


# Global proxy manager instance
proxy_manager = None


# Global manager instance - will be set by gateway
_global_mcp_manager = None

def set_global_manager(manager):
    """Set the global MCP manager instance"""
    global _global_mcp_manager
    _global_mcp_manager = manager

# Dependency: Get MCP service manager and proxy manager
def get_managers():
    global proxy_manager, _global_mcp_manager

    # Use the global MCP service manager instance if available
    if _global_mcp_manager is not None:
        mcp_manager = _global_mcp_manager
    else:
        # Fallback to creating a new instance
        mcp_manager = McpServiceManager()

    # Ensure proxy manager is also a singleton and uses the global manager
    proxy_manager = McpProxyManager.get_instance(mcp_manager)

    return {"mcp_manager": mcp_manager, "proxy_manager": proxy_manager}


# Data models
class ProxyRequest(BaseModel):
    """Proxy request model"""

    name: str
    server_name: str
    endpoint: str | None = "/mcp"
    transport_type: str | None = "streamableHTTP"
    exposed_tools: list[str] | None = []
    auto_start: bool | None = False
    description: str | None = ""


class ProxyUpdateRequest(BaseModel):
    """Proxy update request model"""

    name: str | None = None
    server_name: str | None = None
    endpoint: str | None = None
    transport_type: str | None = None
    exposed_tools: list[str] | None = None
    auto_start: bool | None = None
    description: str | None = None


class JsonRpcRequest(BaseModel):
    """JSON-RPC request model"""

    jsonrpc: str = "2.0"
    id: Any | None = None
    method: str
    params: dict[str, Any] | None = {}


# API Routes

@router.get("/debug/sessions")
async def get_session_stats():
    """Get SSE session statistics for debugging"""
    from mcp_dock.core.sse_session_manager import SSESessionManager
    session_manager = SSESessionManager.get_instance()
    stats = session_manager.get_session_stats()
    return stats





@router.post("/debug/rate-limit/clear")
async def clear_rate_limit_history(client_host: str = None):
    """Clear rate limiting history for a specific client or all clients"""
    from mcp_dock.core.sse_session_manager import SSESessionManager
    session_manager = SSESessionManager.get_instance()
    cleared_count = session_manager.clear_rate_limit_history(client_host)

    if client_host:
        message = f"Cleared rate limit history for client {client_host}"
    else:
        message = f"Cleared rate limit history for all clients ({cleared_count} entries)"

    return {
        "cleared_histories": cleared_count,
        "client_host": client_host,
        "message": message
    }


@router.get("/", response_model=list[dict[str, Any]])
async def get_all_proxies(managers: dict = Depends(get_managers)):
    """Get status of all MCP proxies"""
    try:
        proxy_manager = managers["proxy_manager"]
        return proxy_manager.get_all_proxies_status()
    except Exception as e:
        logger.error(f"Failed to get proxy list: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get proxy list: {e!s}",
        )


@router.post("/{name}/messages")
async def handle_proxy_messages(
    name: str = Path(..., description="Proxy name"),
    request: Request = None,
    managers: dict = Depends(get_managers),
):
    """Handle StreamableHTTP messages for specific proxy (MCP Inspector compatibility)"""
    try:
        # Import the handler from dynamic_proxy
        from mcp_dock.api.routes.dynamic_proxy import handle_proxy_streamable_http

        # Call the dynamic proxy handler
        return await handle_proxy_streamable_http(name, request, managers)

    except Exception as e:
        logger.error(f"Error handling proxy message for {name}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        )


@router.post("/{name}")
async def handle_proxy_post_request(
    request: Request,
    name: str = Path(..., description="Proxy name"),
    managers: dict = Depends(get_managers),
):
    """Handle POST requests to proxy base URL (StreamableHTTP compatibility)"""
    try:
        # Import the StreamableHTTP handler from dynamic_proxy
        from mcp_dock.api.routes.dynamic_proxy import handle_proxy_streamable_http

        # For POST requests to base URL, treat as StreamableHTTP messages
        logger.info(f"📡 POST request to proxy base URL {name}, treating as StreamableHTTP")
        return await handle_proxy_streamable_http(name, request, managers)

    except Exception as e:
        logger.error(f"Error handling POST request for {name}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        )


@router.get("/{name}")
async def get_proxy_or_sse(
    request: Request,
    name: str = Path(..., description="Proxy name"),
    managers: dict = Depends(get_managers),
):
    """Get status of a specific proxy or handle SSE stream request"""
    try:
        proxy_manager = managers["proxy_manager"]
        proxy = proxy_manager.get_proxy_status(name)

        # Check if this is an SSE stream request
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            # For SSE requests, always return SSE stream regardless of proxy transport type
            # This allows MCP Inspector to connect via SSE even if the underlying proxy uses streamableHTTP
            # Import SSE handling from dynamic_proxy
            from mcp_dock.api.routes.dynamic_proxy import handle_proxy_warmup

            # Create a fake proxy_path for the dynamic proxy handler
            # Since we're in /api/proxy/{name}, we need to simulate the path that dynamic_proxy expects
            # Dynamic proxy expects proxy_path parameter, so we pass the proxy name as proxy_path
            return await handle_proxy_warmup(name, request, managers)
        else:
            # Regular GET request - return proxy status
            return proxy

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Proxy does not exist: {e!s}")
    except Exception as e:
        logger.error(f"Failed to get proxy information: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get proxy information: {e!s}",
        )


@router.post("/", response_model=dict[str, Any])
async def create_proxy(request: ProxyRequest, managers: dict = Depends(get_managers)):
    """Create a new MCP proxy"""
    proxy_manager = managers["proxy_manager"]
    mcp_manager = managers["mcp_manager"]  # Add MCP service manager reference

    try:
        # Create proxy configuration
        config = McpProxyConfig(
            name=request.name,
            server_name=request.server_name,
            endpoint=request.endpoint,
            transport_type=request.transport_type,
            exposed_tools=request.exposed_tools,
            auto_start=request.auto_start,
            description=request.description or f"MCP 服务 {request.server_name}",
        )

        # Add proxy
        success = proxy_manager.add_proxy(config)
        if not success:
            raise HTTPException(
                status_code=409, detail=f"Proxy {request.name} already exists",
            )

        # Check if source server is running, if so, automatically start proxy
        try:
            server_status = mcp_manager.get_server_status(request.server_name)
            if server_status.get("status") == "running":
                # Manually update proxy status
                if request.name in proxy_manager.proxies:
                    proxy_manager.proxies[request.name].status = "running"
                    logger.info(
                        f"Source server {request.server_name} is running, automatically setting proxy {request.name} status to running",
                    )
                    # Update proxy tool list
                    await proxy_manager.update_proxy_tools(request.name)
        except Exception as e:
            logger.warning(f"Failed to check server status: {e!s}")

        # Save configuration
        proxy_manager.save_config()

        return {"message": f"Proxy {request.name} created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create proxy: {e!s}")


@router.put("/{name}", response_model=dict[str, Any])
async def update_proxy(
    name: str = Path(..., description="Proxy name"),
    request: ProxyUpdateRequest = Body(...),
    managers: dict = Depends(get_managers),
):
    """Update MCP proxy configuration"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Check if proxy exists
        try:
            current_proxy = proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        # Create updated configuration
        updated_config = McpProxyConfig(
            name=request.name if request.name is not None else current_proxy["name"],
            server_name=request.server_name
            if request.server_name is not None
            else current_proxy["server_name"],
            endpoint=request.endpoint
            if request.endpoint is not None
            else current_proxy["endpoint"],
            transport_type=request.transport_type
            if request.transport_type is not None
            else current_proxy["transport_type"],
            exposed_tools=request.exposed_tools
            if request.exposed_tools is not None
            else current_proxy["exposed_tools"],
            auto_start=request.auto_start
            if request.auto_start is not None
            else current_proxy.get("auto_start", False),
            description=request.description
            if request.description is not None
            else current_proxy.get("description", ""),
        )

        # Update proxy
        success = proxy_manager.update_proxy(name, updated_config)
        if not success:
            raise HTTPException(
                status_code=400, detail=f"Failed to update proxy {name}",
            )

        # Update proxy tool list
        await proxy_manager.update_proxy_tools(updated_config.name)

        return {"message": f"Proxy {name} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update proxy: {e!s}")


@router.delete("/{name}", response_model=dict[str, Any])
async def delete_proxy(
    name: str = Path(..., description="Proxy name"),
    managers: dict = Depends(get_managers),
):
    """Delete MCP proxy configuration"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Delete proxy
        success = proxy_manager.remove_proxy(name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        return {"message": f"Proxy {name} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete proxy: {e!s}")


@router.post("/{name}/update-tools")
async def update_proxy_tools(name: str, managers: dict = Depends(get_managers)):
    """Update proxy tool list"""
    proxy_manager = managers["proxy_manager"]

    try:
        # Ensure proxy exists
        try:
            proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        # Update tool list
        success, tools = await proxy_manager.update_proxy_tools(name)

        # Re-check proxy status to ensure it has been updated
        proxy_status = proxy_manager.get_proxy_status(name)
        logger.info(f"Proxy status after updating tool list: {proxy_status['status']}")

        if success:
            return JSONResponse(
                content={
                    "message": f"Proxy {name} tool list updated successfully",
                    "tools": tools,
                    "count": len(tools),
                },
            )
        raise HTTPException(
            status_code=400, detail=f"Failed to update proxy {name} tool list",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update proxy tool list: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update proxy tool list: {e!s}",
        )


# Add a backdoor API to directly use the server's tool list
@router.post("/{name}/force-update")
async def force_update_proxy(name: str, managers: dict = Depends(get_managers)):
    """Force update proxy status and tool list (copied from source server)"""
    proxy_manager = managers["proxy_manager"]
    mcp_manager = managers["mcp_manager"]

    try:
        # Ensure proxy exists
        try:
            proxy = proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        server_name = proxy["server_name"]

        # Check if source server exists
        try:
            server_status = mcp_manager.get_server_status(server_name)
        except:
            raise HTTPException(
                status_code=404, detail=f"Source server {server_name} does not exist",
            )

        # Get server tool list from server status first
        server_tools = server_status.get("tools", [])
        logger.info(f"Got server {server_name} tool list from status: {len(server_tools)} tools")

        # If status doesn't have tools, try to get from server instance
        if not server_tools:
            logger.warning(
                f"Server {server_name} tool list is empty in status, trying server instance",
            )

            # Try to get tool list from server instance
            server_instance = mcp_manager.servers.get(server_name)
            if (
                server_instance
                and hasattr(server_instance, "tools")
                and server_instance.tools
            ):
                server_tools = server_instance.tools
                logger.info(
                    f"Got tool list from server instance: {len(server_tools)} tools",
                )
            else:
                # Force refresh server status to get latest tools
                try:
                    await mcp_manager.get_server_tools(server_name)
                    updated_status = mcp_manager.get_server_status(server_name)
                    server_tools = updated_status.get("tools", [])
                    logger.info(f"Got refreshed tool list: {len(server_tools)} tools")
                except Exception as e:
                    logger.error(f"Failed to refresh server tools: {e}")

        # Directly set proxy tool list and status
        if name in proxy_manager.proxies:
            proxy_instance = proxy_manager.proxies[name]
            proxy_instance.tools = server_tools
            proxy_instance.status = "running"
            proxy_instance.error_message = None

            # Return success
            return JSONResponse(
                content={
                    "message": f"Proxy {name} status and tool list updated successfully",
                    "tools": server_tools,
                    "count": len(server_tools),
                },
            )
        raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force update proxy status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to force update proxy status: {e!s}",
        )


@router.post("/{name}/start", response_model=dict[str, Any])
async def start_proxy(
    name: str = Path(..., description="Proxy name"),
    managers: dict = Depends(get_managers),
):
    """Start MCP proxy"""
    try:
        proxy_manager = managers["proxy_manager"]
        mcp_manager = managers["mcp_manager"]

        # Check if proxy exists
        try:
            proxy = proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        # Check if proxy is already running
        if proxy["status"] == "running":
            return {"message": f"Proxy {name} is already running"}

        # Get proxy instance
        proxy_instance = proxy_manager.proxies[name]
        server_name = proxy_instance.config.server_name

        # Check if source server exists and is running
        try:
            server_status = mcp_manager.get_server_status(server_name)
            if "error" in server_status:
                raise HTTPException(
                    status_code=404,
                    detail=f"Source server {server_name} does not exist",
                )

            # Check server status based on transport type
            server_transport_type = server_status.get("transport_type", "stdio")
            current_status = server_status.get("status")

            if server_transport_type == "stdio":
                # For stdio servers, expect "running" status
                if current_status not in ["running", "verified"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source server {server_name} is not running (status: {current_status}). Please start the server first.",
                    )
            else:
                # For sse/streamableHTTP servers, expect "connected" status
                if current_status not in ["connected", "running", "verified"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source server {server_name} is not connected (status: {current_status}). Please connect the server first.",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Source server {server_name} does not exist",
            )

        # Start proxy by updating its status and tools
        proxy_instance.status = "running"
        proxy_instance.error_message = None

        # Update proxy tools from source server
        success, _ = await proxy_manager.update_proxy_tools(name)
        if not success:
            proxy_instance.status = "error"
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start proxy {name}: unable to get tools from source server",
            )

        return {"message": f"Proxy {name} started successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start proxy: {e!s}")


@router.post("/{name}/stop", response_model=dict[str, Any])
async def stop_proxy(
    name: str = Path(..., description="Proxy name"),
    managers: dict = Depends(get_managers),
):
    """Stop MCP proxy"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Check if proxy exists
        try:
            proxy = proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        # Check if proxy is already stopped
        if proxy["status"] == "stopped":
            return {"message": f"Proxy {name} is already stopped"}

        # Stop proxy by updating its status
        proxy_instance = proxy_manager.proxies[name]
        proxy_instance.status = "stopped"
        proxy_instance.error_message = None
        proxy_instance.tools = []  # Clear tools when stopped

        return {"message": f"Proxy {name} stopped successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop proxy: {e!s}")


@router.post("/{name}/restart", response_model=dict[str, Any])
async def restart_proxy(
    name: str = Path(..., description="Proxy name"),
    managers: dict = Depends(get_managers),
):
    """Restart MCP proxy"""
    try:
        proxy_manager = managers["proxy_manager"]
        mcp_manager = managers["mcp_manager"]

        # Check if proxy exists
        try:
            proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        # Get proxy instance
        proxy_instance = proxy_manager.proxies[name]
        server_name = proxy_instance.config.server_name

        # Check if source server exists and is running
        try:
            server_status = mcp_manager.get_server_status(server_name)
            if "error" in server_status:
                raise HTTPException(
                    status_code=404,
                    detail=f"Source server {server_name} does not exist",
                )

            # Check server status based on transport type
            server_transport_type = server_status.get("transport_type", "stdio")
            current_status = server_status.get("status")

            if server_transport_type == "stdio":
                # For stdio servers, expect "running" status
                if current_status not in ["running", "verified"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source server {server_name} is not running (status: {current_status}). Please start the server first.",
                    )
            else:
                # For sse/streamableHTTP servers, expect "connected" status
                if current_status not in ["connected", "running", "verified"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source server {server_name} is not connected (status: {current_status}). Please connect the server first.",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Source server {server_name} does not exist",
            )

        # Stop proxy first
        proxy_instance.status = "stopped"
        proxy_instance.error_message = None
        proxy_instance.tools = []

        # Wait a moment
        import asyncio
        await asyncio.sleep(0.5)

        # Start proxy again
        proxy_instance.status = "running"

        # Update proxy tools from source server
        success, _ = await proxy_manager.update_proxy_tools(name)
        if not success:
            proxy_instance.status = "error"
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restart proxy {name}: unable to get tools from source server",
            )

        return {"message": f"Proxy {name} restarted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart proxy: {e!s}")


@router.post("/reload-config", response_model=dict[str, Any])
async def reload_proxy_config(managers: dict = Depends(get_managers)):
    """Reload proxy configuration from file"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Clear current proxies
        proxy_manager.proxies.clear()

        # Reload configuration
        proxy_manager._load_config()

        return {
            "message": "Proxy configuration reloaded successfully",
            "proxy_count": len(proxy_manager.proxies),
            "proxies": list(proxy_manager.proxies.keys())
        }

    except Exception as e:
        logger.error(f"Failed to reload proxy configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload proxy configuration: {e!s}")


@router.post("/{name}/call", response_model=dict[str, Any])
async def proxy_call(
    name: str = Path(..., description="Proxy name"),
    request: JsonRpcRequest = Body(...),
    managers: dict = Depends(get_managers),
):
    """Call JSON-RPC request through MCP proxy"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Forward request
        response = await proxy_manager.proxy_request(name, request.model_dump())

        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to call proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to call proxy: {e!s}")


@router.post("/{name}/stream")
async def proxy_stream(
    name: str = Path(..., description="Proxy name"),
    request: JsonRpcRequest = Body(...),
    managers: dict = Depends(get_managers),
):
    """Stream JSON-RPC request through MCP proxy"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Create streaming response
        response_generator = proxy_manager.create_proxy_stream(name, request.model_dump())

        return StreamingResponse(
            response_generator,
            media_type="application/json",
            headers={"Content-Type": "application/json"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stream proxy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stream proxy: {e!s}")


# Actual MCP endpoint route: This is the main endpoint accessed by users
@router.post("/endpoint/{name}")
async def mcp_endpoint(
    name: str = Path(..., description="Proxy name"),
    request: dict[str, Any] = Body(...),
    stream: bool = Query(False, description="Whether to use streaming response"),
    managers: dict = Depends(get_managers),
):
    """MCP proxy endpoint, routes JSON-RPC requests based on proxy name"""
    try:
        proxy_manager = managers["proxy_manager"]

        # Check if proxy exists
        try:
            proxy = proxy_manager.get_proxy_status(name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Proxy {name} does not exist")

        # Check if proxy is available based on its status
        if proxy["status"] != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Proxy {name} is not available, status is {proxy['status']}",
            )

        # Handle request
        if stream:
            # Streaming response
            response_generator = proxy_manager.create_proxy_stream(name, request)

            # Return appropriate response based on proxy configuration's transport type
            if proxy["transport_type"] == "sse":
                return StreamingResponse(
                    response_generator,
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            # streamableHTTP
            return StreamingResponse(
                response_generator,
                media_type="application/json",
                headers={"Content-Type": "application/json"},
            )
        # Normal response
        response = await proxy_manager.proxy_request(name, request)
        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to call MCP endpoint: {e}")
        # Return JSON-RPC error response
        error_response = {
            "jsonrpc": "2.0",
            "id": request.get("id") if isinstance(request, dict) else None,
            "error": {
                "code": -32603,  # Internal error
                "message": f"Failed to call MCP endpoint: {e!s}",
            },
        }
        return JSONResponse(
            content=error_response, status_code=200,
        )  # JSON-RPC always returns 200


# Add an API to directly create a proxy, forcing inclusion of tool list
@router.post("/{name}/create-with-tools")
async def create_proxy_with_tools(
    name: str,
    server_name: str = Form(...),
    transport_type: str = Form("stdio"),
    endpoint: str = Form("/notion"),
):
    """Force creation of proxy with tool list included"""
    logger.info(f"Forcing creation of proxy {name} for server {server_name}")

    # Manually create proxy
    proxy_instance = McpProxyInstance(
        config=McpProxyConfig(
            name=name,
            server_name=server_name,
            endpoint=endpoint,
            transport_type=transport_type,
        ),
        status="running",
        error_message=None,
        tools=[
            {"name": "API-get-user", "description": "Retrieve a user"},
            {"name": "API-get-users", "description": "List all users"},
            {"name": "API-get-self", "description": "Retrieve your token's bot user"},
            {"name": "API-post-database-query", "description": "Query a database"},
            {"name": "API-post-search", "description": "Search by title"},
            {
                "name": "API-get-block-children",
                "description": "Retrieve block children",
            },
            {
                "name": "API-patch-block-children",
                "description": "Append block children",
            },
            {"name": "API-retrieve-a-block", "description": "Retrieve a block"},
            {"name": "API-update-a-block", "description": "Update a block"},
            {"name": "API-delete-a-block", "description": "Delete a block"},
            {"name": "API-retrieve-a-page", "description": "Retrieve a page"},
            {"name": "API-patch-page", "description": "Update page properties"},
            {"name": "API-post-page", "description": "Create a page"},
            {"name": "API-create-a-database", "description": "Create a database"},
            {"name": "API-update-a-database", "description": "Update a database"},
            {"name": "API-retrieve-a-database", "description": "Retrieve a database"},
            {
                "name": "API-retrieve-a-page-property",
                "description": "Retrieve a page property item",
            },
            {"name": "API-retrieve-a-comment", "description": "Retrieve comments"},
            {"name": "API-create-a-comment", "description": "Create comment"},
        ],
    )

    # Get proxy manager and add proxy
    proxy_manager = McpProxyManager(McpServiceManager())

    # Remove any existing old proxy
    if name in proxy_manager.proxies:
        del proxy_manager.proxies[name]

    # Add new proxy
    proxy_manager.proxies[name] = proxy_instance

    # Save configuration
    proxy_manager.save_config()

    return JSONResponse(
        content={
            "message": f"Proxy {name} created successfully with {len(proxy_instance.tools)} tools",
            "status": "running",
            "tools": proxy_instance.tools,
        },
    )
