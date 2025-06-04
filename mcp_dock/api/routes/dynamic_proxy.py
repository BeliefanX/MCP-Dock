"""
Dynamic MCP Proxy Routes - Dynamically generate endpoints based on proxy configuration
"""

import json
import logging
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from mcp_dock.core.mcp_proxy import McpProxyManager
from mcp_dock.core.sse_session_manager import SSESessionManager
from mcp_dock.utils.logging_config import get_logger

logger = get_logger(__name__)

# Print initialization log
logger.info("Initializing dynamic proxy routing module")

# Create a router with prefix and tags
router = APIRouter(prefix="", tags=["dynamic_proxy"])


# Import the set_global_manager function from proxy module
from mcp_dock.api.routes.proxy import get_managers


def detect_docker_environment(request: Request) -> bool:
    """Detect if the request is coming from a Docker environment (like MCP Inspector)"""
    # Check for common Docker/container indicators
    user_agent = request.headers.get("user-agent", "").lower()
    x_forwarded_for = request.headers.get("x-forwarded-for")
    x_real_ip = request.headers.get("x-real-ip")

    # Docker container indicators
    docker_indicators = [
        "docker" in user_agent,
        "container" in user_agent,
        x_forwarded_for is not None,
        x_real_ip is not None,
        request.client.host in ["172.17.0.1", "172.18.0.1", "172.19.0.1"],  # Common Docker bridge IPs
        request.client.host.startswith("172."),  # Docker network range
    ]

    return any(docker_indicators)


def get_docker_optimized_headers(request: Request) -> dict:
    """Get optimized headers for Docker/container environments"""
    base_headers = {
        # Standard SSE headers
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream; charset=utf-8",

        # CORS headers for container environments
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Cache-Control, Authorization, Accept, X-Requested-With, X-Session-ID",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
        "Access-Control-Expose-Headers": "Content-Type, Cache-Control, X-Session-ID",
        "Access-Control-Allow-Credentials": "false",

        # MCP Inspector specific headers
        "X-MCP-Transport": "sse",
        "X-MCP-Version": "2024-11-05",
    }

    # Add Docker-specific optimizations if detected
    if detect_docker_environment(request):
        logger.info(f"Docker environment detected for {request.client.host}, applying optimizations")
        base_headers.update({
            # Prevent all forms of buffering in Docker environments
            "X-Accel-Buffering": "no",
            "X-Nginx-Buffering": "no",
            "Proxy-Buffering": "off",
            "X-Proxy-Buffering": "off",

            # Docker network optimizations
            "Keep-Alive": "timeout=300, max=1000",
            "Transfer-Encoding": "chunked",

            # Force immediate delivery
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",

            # Docker Inspector compatibility
            "X-Docker-Compatible": "true",
            "X-MCP-Inspector-Ready": "true",
        })

    return base_headers


@router.get("/debug/sessions")
async def get_session_stats():
    """Get SSE session statistics for debugging"""
    from mcp_dock.core.sse_session_manager import SSESessionManager
    session_manager = SSESessionManager.get_instance()
    stats = session_manager.get_session_stats()
    return JSONResponse(content=stats)


@router.options("/messages")
async def handle_global_sse_messages_options(request: Request):
    """Handle CORS preflight requests for /messages endpoint (Docker compatibility)"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Cache-Control, Authorization, Accept, X-Requested-With, X-Session-ID",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD",
            "Access-Control-Max-Age": "86400",  # 24 hours
        }
    )


@router.post("/messages")
async def handle_global_sse_messages(request: Request, managers: dict = Depends(get_managers)):
    """Handle SSE messages sent to /messages endpoint (MCP Inspector compatibility)"""
    try:
        # Extract session ID from query parameters
        session_id = request.query_params.get("sessionId")
        if not session_id:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32600,
                        "message": "Session ID is required in query parameters"
                    }
                },
                status_code=400
            )

        # Find which proxy this session belongs to
        session_manager = SSESessionManager.get_instance()
        session = session_manager.get_session(session_id)
        if not session:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32002,
                        "message": f"Session {session_id} not found"
                    }
                },
                status_code=404
            )

        # Route to the appropriate proxy handler
        return await handle_sse_message(session.proxy_name, request)

    except Exception as e:
        logger.error(f"Error handling global SSE message: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {e}"
                }
            },
            status_code=500
        )


async def handle_sse_message(proxy_name: str, request: Request) -> JSONResponse:
    """Handle SSE message from MCP Inspector"""
    try:
        # Get session ID from query parameters
        session_id = request.query_params.get("session_id")
        if not session_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing session_id parameter"}
            )

        # Parse message
        message_data = await request.json()
        logger.info(f"Received SSE message for session {session_id}: {message_data.get('method', 'response')}")

        # Handle message through session manager
        from mcp_dock.core.sse_session_manager import SSESessionManager
        session_manager = SSESessionManager.get_instance()

        # Handle MCP message through session manager
        response = await session_manager.handle_mcp_message(session_id, message_data)

        # Return response immediately
        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error handling SSE message: {e}")
        logger.error(f"Error details: {traceback.format_exc()}")
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


# Add GET handler for warmup requests
@router.get("/{proxy_path:path}")
async def handle_proxy_warmup(
    proxy_path: str, request: Request, managers: dict = Depends(get_managers),
):
    """
    Handle MCP warmup GET request.
    URL format: /{proxy_name}/{endpoint} or /{proxy_name}
    Example: /notion/mcp, /Notion_MCP/notion, /Notion_MCP

    Args:
        proxy_path: Proxy path ({proxy_name}/{endpoint} or {proxy_name})
        request: FastAPI request object
        managers: Manager instances injected as dependencies
    """
    logger.debug(f"Received proxy warmup request: {proxy_path}")

    # Exclude API paths
    if proxy_path.startswith("api/"):
        logger.debug(f"Skipping API path: {proxy_path}")
        raise HTTPException(status_code=404, detail="Not Found")

    # Parse proxy path (first path part is the proxy name)
    path_parts = proxy_path.strip("/").split("/")
    if not path_parts:
        logger.error("Invalid proxy path")
        raise HTTPException(status_code=404, detail="Invalid proxy path")

    proxy_name = path_parts[0]
    endpoint_path = "/".join(path_parts[1:]) if len(path_parts) > 1 else ""

    logger.info(f"Parsed proxy request: proxy_name={proxy_name}, endpoint_path={endpoint_path}")

    # Get proxy manager
    proxy_manager = managers["proxy_manager"]
    mcp_manager = managers["mcp_manager"]

    # Try to find proxy by name, with fallback logic for different naming patterns
    proxy = None
    actual_proxy_name = None

    # First try exact match
    try:
        proxy = proxy_manager.get_proxy_status(proxy_name)
        actual_proxy_name = proxy_name
        logger.info(f"Found exact proxy match: {proxy_name}")
    except ValueError:
        # Try to find proxy by endpoint path matching
        logger.info(f"Exact proxy name '{proxy_name}' not found, trying endpoint matching...")

        # Get all available proxies
        all_proxies = proxy_manager.get_all_proxies()

        # Try to match by endpoint path
        for p_name, p_info in all_proxies.items():
            p_endpoint = p_info.get('endpoint', '').strip('/')

            # Check if the requested path matches the proxy's endpoint
            if endpoint_path and p_endpoint == endpoint_path:
                proxy = p_info
                actual_proxy_name = p_name
                logger.info(f"Found proxy by endpoint matching: {p_name} -> {p_endpoint}")
                break

            # Also check if proxy name contains the requested name (case insensitive)
            if proxy_name.lower() in p_name.lower() or p_name.lower() in proxy_name.lower():
                proxy = p_info
                actual_proxy_name = p_name
                logger.info(f"Found proxy by name similarity: {p_name}")
                break

        if not proxy:
            logger.error(f"No proxy found for path: {proxy_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Proxy not found for path: {proxy_path}. Available proxies: {list(all_proxies.keys())}"
            )

    logger.info(
        f"Processing proxy {actual_proxy_name} GET request, current status: {proxy['status']}",
    )

    # If proxy status is stopped but server is running, try auto-recovery
    if proxy["status"] != "running":
        logger.info(
            f"Proxy {actual_proxy_name} status is not running, checking server status",
        )
        # Check source server status
        server_name = proxy["server_name"]
        try:
            server_status = mcp_manager.get_server_status(server_name)
            logger.info(f"Server {server_name} status: {server_status.get('status', 'unknown')}")

            # For remote servers (like Tavily), check if they are connected
            if server_status.get("status") in ["connected", "running", "verified"]:
                logger.info(
                    f"Source server {server_name} status is {server_status['status']}, attempting to auto-recover proxy",
                )
                # Manually set proxy status to running
                if actual_proxy_name in proxy_manager.proxies:
                    proxy_manager.proxies[actual_proxy_name].status = "running"
                    logger.info(
                        f"Manually recovered proxy {actual_proxy_name} status to running",
                    )

                    # If server has tool list, copy it to proxy
                    if server_status.get("tools"):
                        proxy_manager.proxies[actual_proxy_name].tools = server_status[
                            "tools"
                        ]
                        logger.info(
                            f"Copied {len(server_status['tools'])} tools from server to proxy",
                        )

                    # Update proxy status to reflect the change
                    proxy = proxy_manager.get_proxy_status(actual_proxy_name)
                    logger.info(f"Proxy {actual_proxy_name} status after recovery: {proxy['status']}")
            else:
                logger.warning(f"Server {server_name} status is {server_status.get('status', 'unknown')}, cannot auto-recover proxy")
        except Exception as e:
            logger.error(f"Error checking server status: {e!s}")
            logger.error(f"Exception details: {traceback.format_exc()}")

    # Check proxy status
    if proxy["status"] != "running":
        logger.error(
            f"Proxy {actual_proxy_name} is not available, status is {proxy['status']}",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Proxy {actual_proxy_name} is not available, status is {proxy['status']}",
        )

    # For GET requests, check if client expects SSE stream
    accept_header = request.headers.get("accept", "")
    if "text/event-stream" in accept_header:
        # Always provide SSE stream when requested, regardless of proxy transport type
        # This allows MCP Inspector to connect via SSE even if the underlying proxy uses streamableHTTP
        # Enhanced SSE connection logging
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        origin = request.headers.get("origin", "none")
        x_forwarded_for = request.headers.get("x-forwarded-for", "none")

        logger.info(f"🌊 SSE STREAM REQUEST: {actual_proxy_name}")
        logger.info(f"   📍 Client: {client_ip} | X-Forwarded-For: {x_forwarded_for}")
        logger.info(f"   🔍 User-Agent: {user_agent}")
        logger.info(f"   🌍 Origin: {origin}")

        # Use provided session ID or generate a new one
        session_id = request.query_params.get("sessionId")
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            logger.info(f"   🆔 Generated Session ID: {session_id}")
        else:
            logger.info(f"   🆔 Using provided Session ID: {session_id}")

        # Store session info
        from mcp_dock.core.sse_session_manager import SSESessionManager
        session_manager = SSESessionManager.get_instance()

        # Return MCP-compatible SSE stream with Docker optimizations
        async def mcp_sse_stream():
            import asyncio
            try:
                # Register session with enhanced logging and rate limiting
                if not session_manager.register_session(session_id, actual_proxy_name, client_ip):
                    # Rate limited - return error response
                    logger.warning(f"🚫 SSE connection denied due to rate limiting: {session_id}")
                    yield f"event: error\n"
                    yield f"data: {{\"error\": \"Rate limit exceeded\", \"code\": 429}}\n\n"
                    return

                # Check if this is a Docker environment
                is_docker = detect_docker_environment(request)
                if is_docker:
                    logger.info(f"🐳 Docker environment detected for session {session_id}, applying optimizations")

                # Send endpoint event as expected by MCP Inspector
                # This tells the client where to send JSON-RPC messages
                endpoint_url = f"/messages?sessionId={session_id}"
                yield f"event: endpoint\n"
                yield f"data: {endpoint_url}\n\n"

                # For Docker environments, send an immediate ping to establish connection
                if is_docker:
                    docker_ping = {
                        "jsonrpc": "2.0",
                        "method": "notifications/ping",
                        "params": {
                            "timestamp": time.time(),
                            "sessionId": session_id,
                            "dockerOptimized": True
                        }
                    }
                    yield f"event: ping\n"
                    yield f"data: {json.dumps(docker_ping)}\n\n"

                # Wait for MCP Inspector to send initialize request
                # In the meantime, keep connection alive with periodic checks
                heartbeat_count = 0
                logger.info(f"🔄 SSE session {session_id} waiting for messages...")

                while True:
                    # Check for pending messages for this session
                    messages = session_manager.get_pending_messages(session_id)
                    if messages:
                        for message in messages:
                            msg_type = message.get('method', 'response')
                            msg_id = message.get('id', 'unknown')
                            logger.info(f"📤 Sending message to SSE session {session_id}: {msg_type} (ID={msg_id})")
                            yield f"event: message\n"
                            yield f"data: {json.dumps(message)}\n\n"
                        # Immediately yield after sending messages to ensure delivery
                        continue

                    # Send heartbeat more frequently for faster response delivery
                    await asyncio.sleep(1)  # Check every 1 second instead of 5
                    heartbeat_count += 1

                    if heartbeat_count % 10 == 0:  # Every 10 seconds
                        heartbeat_msg = {
                            "jsonrpc": "2.0",
                            "method": "notifications/ping",
                            "params": {"timestamp": time.time(), "sessionId": session_id}
                        }
                        yield f"event: ping\n"
                        yield f"data: {json.dumps(heartbeat_msg)}\n\n"

                        if heartbeat_count % 12 == 0:  # Log every minute
                            logger.info(f"SSE session {session_id} heartbeat #{heartbeat_count//2}")

                    # Clean up expired sessions periodically
                    if heartbeat_count % 60 == 0:  # Every 5 minutes
                        expired_count = session_manager.cleanup_expired_sessions()
                        if expired_count > 0:
                            logger.info(f"Cleaned up {expired_count} expired sessions")

            except asyncio.CancelledError:
                logger.info(f"🔌 SSE session {session_id} cancelled by client")
                # Don't unregister here - let finally block handle it
                raise
            except Exception as e:
                logger.error(f"💥 SSE session {session_id} error: {e}")
                logger.error(f"   🔍 Error details: {traceback.format_exc()}")
                # Don't unregister here - let finally block handle it
                raise
            finally:
                # Single cleanup point to prevent double unregistration
                try:
                    if session_manager.has_session(session_id):
                        session_manager.unregister_session(session_id)
                        logger.info(f"🧹 SSE session {session_id} cleanup completed")
                    else:
                        logger.debug(f"🔍 Session {session_id} already cleaned up")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Error during session cleanup: {cleanup_error}")

        return StreamingResponse(
            mcp_sse_stream(),
            media_type="text/event-stream",
            headers=get_docker_optimized_headers(request),
        )
    else:
        # For regular GET requests, return a simple successful Response (MCP warmup)
        logger.info(f"Proxy {actual_proxy_name} warmup request successful")
        return JSONResponse(
            content={"status": "ok", "message": "MCP service is available"},
        )


@router.post("/{proxy_name}/messages")
async def handle_proxy_streamable_http(proxy_name: str, request: Request, managers: dict = Depends(get_managers)):
    """Handle StreamableHTTP messages for specific proxy (MCP Inspector compatibility)"""
    try:
        # Parse JSON body
        body = await request.json()

        # Get managers
        proxy_manager = managers["proxy_manager"]
        mcp_manager = managers["mcp_manager"]

        # Handle different MCP methods
        method = body.get("method")

        logger.info(f"📡 StreamableHTTP request for {proxy_name}: {method}")

        if method == "initialize":
            response = await handle_initialize_request(proxy_name, body, proxy_manager)
        elif method == "tools/list":
            response = await handle_tools_list_request(proxy_name, body, proxy_manager)
        elif method == "tools/call":
            response = await handle_tool_call_request(proxy_name, body, proxy_manager, mcp_manager)
        elif method == "resources/list":
            # Provide default empty response for MCP Inspector compatibility
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"resources": []}
            }
        elif method == "resources/templates/list":
            # Provide default empty response for MCP Inspector compatibility
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"resourceTemplates": []}
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

        logger.info(f"📤 StreamableHTTP response for {proxy_name}: {response.get('result', {}).get('protocolVersion', 'N/A') if 'result' in response else 'error'}")
        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error handling StreamableHTTP message for {proxy_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id") if 'body' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        )


async def handle_initialize_request(proxy_name: str, message: dict, proxy_manager) -> dict:
    """Handle MCP initialize request"""
    try:
        proxy = proxy_manager.get_proxy_status(proxy_name)

        # Get client's requested protocol version
        client_protocol_version = message.get("params", {}).get("protocolVersion", "2024-11-05")

        # Support multiple protocol versions for compatibility
        supported_versions = ["2024-11-05", "2025-03-26"]
        protocol_version = client_protocol_version if client_protocol_version in supported_versions else "2024-11-05"

        logger.info(f"Initialize request for proxy {proxy_name}: client_version={client_protocol_version}, using_version={protocol_version}")

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": False, "listChanged": False},
                    "logging": {},  # Required by MCP Inspector
                    "sampling": {}  # Required by some clients like n8n
                },
                "serverInfo": {
                    "name": f"MCP-Dock-{proxy_name}",
                    "version": "1.0.0",
                    "instructions": f"MCP-Dock proxy server for {proxy_name}. This server provides access to tools from the underlying MCP service through a unified interface."  # Required by MCP Inspector
                }
            }
        }
    except Exception as e:
        logger.error(f"Error handling initialize request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }


async def handle_tools_list_request(proxy_name: str, message: dict, proxy_manager) -> dict:
    """Handle MCP tools/list request"""
    try:
        # Get proxy instance directly to access tools list
        proxy_instance = proxy_manager.proxies.get(proxy_name)
        if not proxy_instance:
            raise ValueError(f"Proxy {proxy_name} not found")

        tools = proxy_instance.tools if proxy_instance.tools else []

        logger.info(f"Returning {len(tools)} tools for proxy {proxy_name}")
        if logger.isEnabledFor(logging.DEBUG) and tools:
            tool_names = [tool.get('name', 'unknown') for tool in tools[:3]]
            logger.debug(f"First few tools: {tool_names}")

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": tools
            }
        }
    except Exception as e:
        logger.error(f"Error handling tools/list request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }


async def handle_tool_call_request(proxy_name: str, message: dict, proxy_manager, mcp_manager) -> dict:
    """Handle MCP tools/call request"""
    try:
        params = message.get("params", {})
        tool_name = params.get("name")
        tool_arguments = params.get("arguments", {})

        if not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32602,
                    "message": "Tool name is required"
                }
            }

        # Create a tool call request
        tool_call_request = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_arguments
            }
        }

        # Use proxy manager to call the tool
        response = await proxy_manager.proxy_request(proxy_name, tool_call_request)
        return response

    except Exception as e:
        logger.error(f"Error handling tools/call request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }


async def handle_sse_message(proxy_name: str, request: Request) -> JSONResponse:
    """Handle SSE message from MCP Inspector

    This endpoint receives JSON-RPC messages from MCP Inspector and routes them
    to the appropriate SSE session.
    """
    try:
        # Parse request body
        message_data = await request.json()
        logger.info(f"Received SSE message for proxy {proxy_name}: {message_data.get('method', 'response')}")

        # Validate JSON-RPC format
        if not isinstance(message_data, dict):
            raise ValueError("Message must be a JSON object")

        if message_data.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC version")

        # Extract session ID from query parameters, headers, or message body
        session_id = (
            request.query_params.get("sessionId") or
            request.headers.get("X-Session-ID") or
            message_data.get("sessionId")
        )
        if not session_id:
            raise ValueError("Session ID is required")

        # Get managers
        managers = get_managers()
        proxy_manager = managers["proxy_manager"]
        mcp_manager = managers["mcp_manager"]

        # Get session manager
        session_manager = SSESessionManager.get_instance()

        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for proxy {proxy_name}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": message_data.get("id"),
                    "error": {
                        "code": -32002,
                        "message": "Session not found"
                    }
                },
                status_code=404
            )

        # Verify session belongs to the correct proxy
        if session.proxy_name != proxy_name:
            logger.warning(f"Session {session_id} belongs to proxy {session.proxy_name}, not {proxy_name}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": message_data.get("id"),
                    "error": {
                        "code": -32002,
                        "message": "Session proxy mismatch"
                    }
                },
                status_code=400
            )

        # Process the message based on method
        method = message_data.get("method")
        message_id = message_data.get("id")

        try:
            if method == "initialize":
                response = await handle_initialize_request(proxy_name, message_data, proxy_manager)
                session.is_initialized = True
            elif method == "tools/list":
                response = await handle_tools_list_request(proxy_name, message_data, proxy_manager)
            elif method == "tools/call":
                response = await handle_tool_call_request(proxy_name, message_data, proxy_manager, mcp_manager)
            elif method == "resources/list":
                # Provide default empty response for MCP Inspector compatibility
                response = {
                    "jsonrpc": "2.0",
                    "id": message_data.get("id"),
                    "result": {"resources": []}
                }
            elif method == "resources/templates/list":
                # Provide default empty response for MCP Inspector compatibility
                response = {
                    "jsonrpc": "2.0",
                    "id": message_data.get("id"),
                    "result": {"resourceTemplates": []}
                }
            else:
                # For other methods, try to proxy to the actual MCP server
                response = await proxy_manager.proxy_request(proxy_name, message_data)

            # Add response to session's message queue
            session_manager.add_message(session_id, response, priority=True)

            logger.info(f"Processed {method} request for session {session_id}")

            # Return 202 Accepted for async processing
            return JSONResponse(
                content={"status": "accepted", "sessionId": session_id},
                status_code=202
            )

        except Exception as e:
            logger.error(f"Error processing {method} request: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            session_manager.add_message(session_id, error_response, priority=True)

            return JSONResponse(
                content={"status": "error", "sessionId": session_id, "error": str(e)},
                status_code=202
            )

    except ValueError as e:
        logger.error(f"Invalid SSE message: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": f"Invalid request: {e}"
                }
            },
            status_code=400
        )
    except Exception as e:
        logger.error(f"Error handling SSE message: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {e}"
                }
            },
            status_code=500
        )


# Wildcard route, handle all proxy requests
@router.post("/{proxy_path:path}")
async def handle_proxy_request(
    proxy_path: str, request: Request, managers: dict = Depends(get_managers),
):
    """
    Wildcard route, handle all proxy requests.
    URL format: /{proxy_name}/{endpoint}
    Example: /notion/mcp

    Args:
        proxy_path: Proxy path ({proxy_name}/{endpoint})
        request: FastAPI request object
        managers: Manager instances injected as dependencies
    """
    logger.debug(f"Received proxy request: {proxy_path}")

    # Exclude API paths
    if proxy_path.startswith("api/"):
        logger.debug(f"Skipping API path: {proxy_path}")
        raise HTTPException(status_code=404, detail="Not Found")

    # Parse proxy path (first part is proxy name)
    path_parts = proxy_path.strip("/").split("/")
    if not path_parts:
        logger.error("Invalid proxy path")
        raise HTTPException(status_code=404, detail="Invalid proxy path")

    proxy_name = path_parts[0]
    endpoint_path = "/".join(path_parts[1:]) if len(path_parts) > 1 else ""

    # Check if this is an SSE message endpoint
    content_type = request.headers.get("content-type", "").lower()
    if endpoint_path == "messages" and content_type.startswith("application/json"):
        return await handle_sse_message(proxy_name, request)

    # Also handle /messages without proxy prefix (for direct MCP Inspector compatibility)
    if proxy_path == "messages" and content_type.startswith("application/json"):
        # Extract proxy name from sessionId or use default
        session_id = request.query_params.get("sessionId")
        if session_id:
            # Try to find which proxy this session belongs to
            session_manager = SSESessionManager.get_instance()
            session = session_manager.get_session(session_id)
            if session:
                return await handle_sse_message(session.proxy_name, request)
        # Fallback: assume it's for the first available proxy
        proxy_manager = managers["proxy_manager"]
        if proxy_manager.proxies:
            first_proxy = next(iter(proxy_manager.proxies.keys()))
            return await handle_sse_message(first_proxy, request)

    # Get proxy manager
    proxy_manager = managers["proxy_manager"]
    mcp_manager = managers["mcp_manager"]

    # Try to find proxy by name, with fallback logic for different naming patterns
    proxy = None
    actual_proxy_name = None

    # First try exact match
    try:
        proxy = proxy_manager.get_proxy_status(proxy_name)
        actual_proxy_name = proxy_name
        logger.info(f"Found exact proxy match: {proxy_name}")
    except ValueError:
        # Try to find proxy by endpoint path matching
        logger.info(f"Exact proxy name '{proxy_name}' not found, trying endpoint matching...")

        # Get all available proxies
        all_proxies = proxy_manager.get_all_proxies()

        # Try to match by endpoint path or name similarity
        for p_name, p_info in all_proxies.items():
            # Check if proxy name contains the requested name (case insensitive)
            if proxy_name.lower() in p_name.lower() or p_name.lower() in proxy_name.lower():
                proxy = p_info
                actual_proxy_name = p_name
                logger.info(f"Found proxy by name similarity: {p_name}")
                break

        if not proxy:
            logger.error(f"No proxy found for name: {proxy_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Proxy not found: {proxy_name}. Available proxies: {list(all_proxies.keys())}"
            )

    # Check proxy status, if not running, try to recover
    if proxy["status"] != "running":
        logger.info(f"Proxy {actual_proxy_name} status is not running, checking server status")

        # Check source server status
        server_name = proxy["server_name"]
        try:
            server_status = mcp_manager.get_server_status(server_name)
            if server_status["status"] in ["running", "verified"]:
                logger.info(
                    f"Source server {server_name} status is {server_status['status']}, attempting to auto-recover proxy",
                )
                # Manually set proxy status to running
                if actual_proxy_name in proxy_manager.proxies:
                    proxy_manager.proxies[actual_proxy_name].status = "running"
                    logger.info(
                        f"Manually recovered proxy {actual_proxy_name} status to running",
                    )

                    # If server has tool list, copy it to proxy
                    if server_status.get("tools"):
                        proxy_manager.proxies[actual_proxy_name].tools = server_status["tools"]
                        logger.info(
                            f"Copied {len(server_status['tools'])} tools from server to proxy",
                        )

                    # Update proxy variable since we modified the proxy status
                    proxy = proxy_manager.get_proxy_status(actual_proxy_name)
        except Exception as e:
            logger.error(f"Error checking server status: {e!s}")

    # Check proxy status again
    if proxy["status"] != "running":
        logger.error(f"Proxy {actual_proxy_name} is not available, status: {proxy['status']}")
        raise HTTPException(
            status_code=400,
            detail=f"Proxy {actual_proxy_name} is not available, status: {proxy['status']}",
        )

    try:
        # Parse Request body as JSON-RPC request
        request_data = await request.json()
        logger.debug(f"Request body: {request_data}")

        # Log request source IP and type
        client_host = request.client.host
        request_id = request_data.get("id", "unknown")
        request_method = request_data.get("method", "unknown")
        logger.info(
            f"Client {client_host} requested proxy {actual_proxy_name}: id={request_id}, method={request_method}",
        )

        # Check streaming flag
        stream = request.query_params.get("stream", "false").lower() == "true"

        # Process request
        if stream:
            # Streaming Response
            logger.info(
                f"Create streaming response: proxy={actual_proxy_name}, transport_type={proxy['transport_type']}",
            )
            response_generator = proxy_manager.create_proxy_stream(
                actual_proxy_name, request_data,
            )

            # Return appropriate Response based on proxy's transport type
            if proxy["transport_type"] == "sse":
                logger.debug("Using SSE transport，Create streaming response")
                return StreamingResponse(
                    response_generator,
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            # streamableHTTP
            logger.debug(
                "Using streamableHTTP transport，Create streaming response",
            )
            return StreamingResponse(
                response_generator,
                media_type="application/json",
                headers={"Content-Type": "application/json"},
            )
        # Regular Response
        logger.debug(f"Create regular response: proxy={actual_proxy_name}")

        # Use specialized handlers for better MCP Inspector compatibility
        method = request_data.get("method")
        if method == "initialize":
            response = await handle_initialize_request(actual_proxy_name, request_data, proxy_manager)
        elif method == "tools/list":
            response = await handle_tools_list_request(actual_proxy_name, request_data, proxy_manager)
        elif method == "tools/call":
            response = await handle_tool_call_request(actual_proxy_name, request_data, proxy_manager, mcp_manager)
        elif method == "resources/list":
            # Provide default empty response for MCP Inspector compatibility
            response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": {"resources": []}
            }
        elif method == "resources/templates/list":
            # Provide default empty response for MCP Inspector compatibility
            response = {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": {"resourceTemplates": []}
            }
        else:
            # For other methods, use the original proxy request
            response = await proxy_manager.proxy_request(actual_proxy_name, request_data)

        logger.info(
            f"Proxy {actual_proxy_name} Response: id={response.get('id', 'unknown')}, result={'success' if 'result' in response else 'error'}",
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Response details: {json.dumps(response, ensure_ascii=False)}",
            )
        return JSONResponse(content=response)

    except json.JSONDecodeError:
        logger.error(
            f"Client {request.client.host} sent invalid JSON request to proxy {proxy_name}",
        )
        raise HTTPException(status_code=400, detail="Invalid JSON request")
    except Exception as e:
        logger.error(f"Error processing proxy request: {e!s}")
        logger.error(f"Exception details: {traceback.format_exc()}")
        # Return JSON-RPC error Response
        error_response = {
            "jsonrpc": "2.0",
            "id": None,  # Cannot get id because parsing may have failed
            "error": {
                "code": -32603,  # Internal error
                "message": f"Error processing proxy request: {e!s}",
            },
        }
        logger.info(
            f"Returning error response to client {request.client.host}: {error_response}",
        )
        return JSONResponse(
            content=error_response, status_code=200,
        )  # JSON-RPC always returns 200
