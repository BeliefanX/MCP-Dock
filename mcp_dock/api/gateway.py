"""
API Gateway - Provides RESTful API interfaces to manage MCP services
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
import traceback
import uuid
from urllib.parse import unquote

from typing import Any

from mcp_dock.utils.logging_config import get_logger

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mcp_dock.api.routes import (
    dynamic_proxy,  # Import dynamic proxy routing module
    proxy,
)
from mcp_dock.core.mcp_service import McpServerConfig, McpServiceManager

# Add debug information
logger = get_logger(__name__)
logger.debug("========================")
logger.debug("gateway.py importing proxy modules")
logger.debug(f"Proxy module: {proxy}")
logger.debug(f"Proxy route: {proxy.router}")
logger.debug(f"Dynamic proxy module: {dynamic_proxy}")
logger.debug(f"Dynamic proxy routes: {dynamic_proxy.router}")
logger.debug("========================")

# Initialize FastAPI application
app = FastAPI(
    title="MCP-Dock API",
    description="REST API for managing MCP services",
    redirect_slashes=True,
)


# Enhanced request logging middleware for debugging Docker MCP Inspector issues
@app.middleware("http")
async def enhanced_request_logging_middleware(request: Request, call_next):
    """Enhanced logging for all HTTP requests with detailed debugging information"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Store request ID for use in other parts of the application
    request.state.request_id = request_id

    # Enhanced request logging with full details
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    origin = request.headers.get("origin", "none")
    referer = request.headers.get("referer", "none")
    x_forwarded_for = request.headers.get("x-forwarded-for", "none")
    x_real_ip = request.headers.get("x-real-ip", "none")
    content_type = request.headers.get("content-type", "none")
    accept_header = request.headers.get("accept", "none")

    # Log comprehensive request start information
    logger.info(f"🌐 REQUEST START [{request_id}]: {request.method} {request.url}")
    logger.info(f"   📍 Client: {client_ip} | X-Forwarded-For: {x_forwarded_for} | X-Real-IP: {x_real_ip}")
    logger.info(f"   🔍 User-Agent: {user_agent}")
    logger.info(f"   🌍 Origin: {origin} | Referer: {referer}")
    logger.info(f"   📄 Content-Type: {content_type}")
    logger.info(f"   📨 Accept: {accept_header}")

    # Log all headers for debugging (but filter sensitive ones)
    sensitive_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}
    headers_to_log = {}
    for name, value in request.headers.items():
        if name.lower() not in sensitive_headers:
            headers_to_log[name] = value
        else:
            headers_to_log[name] = "[REDACTED]"

    logger.debug(f"   📋 All Headers [{request_id}]: {json.dumps(headers_to_log, indent=2)}")

    # Enhanced body logging for POST/PUT/PATCH requests
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if body:
                body_size = len(body)
                logger.info(f"   📦 Request Body Size: {body_size} bytes")

                # Try to parse and log JSON body
                try:
                    json_body = json.loads(body.decode())
                    # Log JSON body with size limit for readability
                    if body_size < 1000:  # Full body for small requests
                        logger.info(f"   📝 Request Body [{request_id}]: {json.dumps(json_body, indent=2)}")
                    else:  # Truncated for large requests
                        logger.info(f"   📝 Request Body [{request_id}] (truncated): {json.dumps(json_body, indent=2)[:500]}...")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Log raw body for non-JSON content
                    if body_size < 200:
                        logger.info(f"   📝 Request Body [{request_id}] (raw): {body}")
                    else:
                        logger.info(f"   📝 Request Body [{request_id}] (raw, truncated): {body[:200]}...")

                # Reset request body for FastAPI to read
                try:
                    await request._body.seek(0)
                except AttributeError:
                    # For newer FastAPI versions, we need to recreate the body
                    pass
        except Exception as e:
            logger.warning(f"   ⚠️ Error reading request body [{request_id}]: {e}")

    # Process request
    try:
        response = await call_next(request)

        # Enhanced response logging
        processing_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(processing_time)
        status_emoji = "✅" if 200 <= response.status_code < 300 else "⚠️" if 300 <= response.status_code < 400 else "❌"

        logger.info(f"{status_emoji} REQUEST COMPLETED [{request_id}]: {request.method} {request.url.path}")
        logger.info(f"   📊 Status: {response.status_code} | Time: {processing_time:.4f}s")

        # Log response headers for debugging
        response_headers = dict(response.headers)
        logger.debug(f"   📋 Response Headers [{request_id}]: {json.dumps(response_headers, indent=2)}")

        return response

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"💥 REQUEST ERROR [{request_id}]: {request.method} {request.url.path}")
        logger.error(f"   ⏱️ Time: {processing_time:.4f}s | Error: {e!s}")
        logger.error(f"   🔍 Exception Details [{request_id}]: {traceback.format_exc()}")
        raise


# Add CORS middleware with Docker compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Set to False for Docker compatibility
    allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Cache-Control", "Authorization", "Accept", "X-Requested-With", "X-Session-ID"],
    expose_headers=["Content-Type", "Cache-Control", "X-Session-ID"],
)

# Get the directory of the current file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Initialize template engine
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "web", "templates"))

# Initialize MCP service manager
manager = McpServiceManager()

# Initialize MCP proxy manager
from mcp_dock.core.mcp_proxy import McpProxyManager
proxy_manager = McpProxyManager(manager)

# Set the global manager for proxy routes
from mcp_dock.api.routes.proxy import set_global_manager
set_global_manager(manager)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "web", "static")),
    name="static",
)


# Call async initialization when the application starts
@app.on_event("startup")
async def startup_event():
    """Asynchronous initialization executed at application startup"""
    logger.info("Starting asynchronous initialization of service manager...")
    try:
        auto_start_count = await manager.initialize()
        logger.info(
            f"Service manager initialization complete, auto-started/connected {auto_start_count} services",
        )

        # Initialize proxy manager and auto-start proxies
        proxy_auto_start_count = await proxy_manager.initialize()
        logger.info(
            f"Proxy manager initialization complete, auto-started {proxy_auto_start_count} proxies",
        )

        # Start SSE session cleanup task
        from mcp_dock.core.sse_session_manager import SSESessionManager
        session_manager = SSESessionManager.get_instance()
        session_manager.start_cleanup_task()

    except Exception as e:
        logger.error(f"Service manager initialization error: {e!s}")
        logger.error(traceback.format_exc())


# Add handler for safe shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup operations executed when the application is shut down"""
    logger.info("Shutting down all MCP services...")

    # Stop SSE session cleanup task
    try:
        from mcp_dock.core.sse_session_manager import SSESessionManager
        session_manager = SSESessionManager.get_instance()
        session_manager.stop_cleanup_task()
    except Exception as e:
        logger.error(f"Error stopping SSE session cleanup task: {e!s}")

    # Stop all MCP services
    for name in list(manager.servers.keys()):
        try:
            manager.stop_server(name)
        except Exception as e:
            logger.error(f"Error shutting down service {name}: {e!s}")
    logger.info("All MCP services have been shut down")


# Helper function for handling asynchronous tasks
async def run_async_task(coroutine):
    """Safely run asynchronous tasks with error handling

    Args:
        coroutine: Coroutine object to run
    """
    try:
        return await coroutine
    except Exception as e:
        logger.error(f"Async task execution failed: {e!s}")
        logger.error(traceback.format_exc())
        return False


# Add proxy routes
logger.debug("========================")
logger.debug("Registering proxy routes...")
logger.debug(f"Proxy route object: {proxy.router}")
logger.debug(f"Proxy route path: {proxy.router.prefix}")
app.include_router(proxy.router)
logger.debug("Proxy routes registration completed!")
logger.debug("========================")


# Homepage and API routes should be registered before dynamic proxy
# Homepage route - return WebUI
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "time": time})


# API routes


@app.get("/api/servers", response_model=list[dict[str, Any]])
async def get_servers():
    """Get the status of all MCP servers"""
    try:
        # Get status of all servers
        servers = manager.get_all_servers_status()

        # Ensure a list is returned, even if it's empty
        if not isinstance(servers, list):
            servers = []

        # Add debug logs
        logger.debug(f"API get services list: returned {len(servers)} services")

        return servers
    except Exception as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Error getting service list: {error_details}")
        # Return empty list instead of throwing error to ensure frontend can process properly
        return []


@app.get("/api/servers/{name}", response_model=dict[str, Any])
async def get_server(name: str):
    """Get the status of a specified MCP server"""
    try:
        return manager.get_server_status(name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")


@app.post("/api/servers", response_model=dict[str, Any])
async def add_server(
    name: str = Form(...),
    command: str = Form(...),
    args: str | None = Form(None),
    env: str | None = Form(None),
    cwd: str | None = Form(None),
    transport_type: str | None = Form(None),
    url: str | None = Form(None),
    headers: str | None = Form(None),
    auto_start: bool | None = Form(False),
    instructions: str | None = Form(""),
):
    """Add a new MCP server"""
    try:
        # Parse JSON string
        try:
            args_list = json.loads(args) if args else []
        except:
            raise ValueError("Invalid JSON format for args")

        # Parse JSON string
        try:
            env_list = json.loads(env) if env else []
        except:
            raise ValueError("Invalid JSON format for env")

        # Parse JSON string
        try:
            headers_list = json.loads(headers) if headers else []
        except:
            raise ValueError("Invalid JSON format for headers")

        config = McpServerConfig(
            name=name,
            command=command,
            args=args_list,
            env=env_list,
            cwd=cwd,
            transport_type=transport_type,
            url=url,
            headers=headers_list,
            auto_start=auto_start,
            instructions=instructions or "",
        )

        # Check if server name already exists
        if name in manager.servers:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "name_conflict",
                    "message": f"Server named '{name}' already exists. Please use a different name.",
                },
            )

        # Add server to manager
        manager.add_server(config)

        # Determine if auto-start/connect is needed
        if config.auto_start:
            if config.transport_type == "stdio":
                # Auto-start stdio type service
                logger.info(
                    f"Starting auto-start stdio service during initialization: {name}",
                )
                start_result = manager.start_server(name)
                if start_result:
                    logger.info(
                        f"Successfully auto-started stdio service {name} during initialization",
                    )
                    return JSONResponse(
                        content={
                            "message": f"Server {name} added and started successfully",
                        },
                    )
                logger.error(
                    f"Failed to auto-start stdio service {name} during initialization",
                )
                return JSONResponse(
                    content={
                        "message": f"Server {name} was added but failed to start",
                    },
                )
            # Auto-connect sse/streamableHTTP type
            logger.info(
                f"Connecting to auto-connect remote service during initialization: {name}",
            )
            server = manager.get_server(name)
            if server:
                success, _ = await manager.verify_mcp_server(server)
                if success:
                    logger.info(
                        f"Successfully auto-connected remote service {name} during initialization",
                    )
                    return JSONResponse(
                        content={
                            "message": f"Server {name} added and connected successfully",
                        },
                    )
                logger.error(
                    f"Failed to auto-connect remote service {name} during initialization",
                )
                return JSONResponse(
                    content={
                        "message": f"Server {name} was added but connection failed",
                    },
                )
        return JSONResponse(
            content={"message": f"Server {name} was added successfully"},
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Error adding server: {error_details}")
        raise HTTPException(
            status_code=400, detail={"error": "unexpected_error", "message": str(e)},
        )


@app.put("/api/servers/{name}")
async def update_server(
    name: str,
    new_name: str = Form(None),
    command: str = Form(None),
    args: str = Form(None),
    env: str = Form(None),
    cwd: str | None = Form(None),
    transport_type: str = Form(None),
    url: str | None = Form(None),
    headers: str | None = Form(None),
    auto_start: str | None = Form(None),
    instructions: str | None = Form(None),
) -> JSONResponse:
    """Update MCP server configuration"""
    try:
        current_status = manager.get_server_status(name)
        current_config = manager.servers[name].config
        processed_args = current_config.args
        processed_env = current_config.env
        processed_url = current_config.url
        processed_headers = current_config.headers
        if args:
            try:
                processed_args = json.loads(args)
            except json.JSONDecodeError as e:
                raise ValueError(f"Parameter JSON parse error: {e!s}")
        if env:
            try:
                processed_env = json.loads(env)
            except json.JSONDecodeError as e:
                raise ValueError(f"Environment variable JSON parse error: {e!s}")
        if headers:
            try:
                processed_headers = json.loads(headers)
            except json.JSONDecodeError as e:
                raise ValueError(f"Headers JSON parse error: {e!s}")
        if url:
            processed_url = url
        # Process boolean parameters
        auto_start_value = current_config.auto_start
        if auto_start is not None:
            auto_start_value = auto_start == "true" if auto_start is not None else current_config.auto_start

        config = McpServerConfig(
            name=new_name if new_name else name,
            command=command if command else current_config.command,
            args=processed_args,
            env=processed_env,
            cwd=cwd if cwd is not None else current_config.cwd,
            transport_type=transport_type
            if transport_type
            else current_config.transport_type,
            url=processed_url,
            headers=processed_headers,
            auto_start=auto_start_value,
            instructions=instructions if instructions is not None else current_config.instructions,
        )
        success = manager.update_server(name, config)
        if success:
            # Determine if auto-start/connect is needed
            updated_name = new_name if new_name else name
            updated_type = (
                transport_type if transport_type else current_config.transport_type
            )

            # If it's sse or streamableHTTP type and auto-connect is checked, connect immediately and get tool list
            if updated_type in ["sse", "streamableHTTP"] and auto_start_value:
                # Only auto-connect when auto_start changes from off to on, or is set to on for the first time
                if (
                    not current_config.auto_start
                    or current_config.transport_type != updated_type
                ):
                    try:
                        logger.info(
                            f"Auto-connecting updated {updated_type} type service: {updated_name}",
                        )
                        # Create asynchronous task to run service connection and get tool list
                        asyncio.create_task(manager.verify_mcp_server(updated_name))
                    except Exception as e:
                        logger.error(
                            f"Error auto-connecting updated service {updated_name}: {e!s}",
                        )
                        # Does not affect service update result, just log the error

            # Handle auto-start/connection for all types
            if auto_start_value:
                try:
                    if updated_type == "stdio":
                        # Auto-start stdio type service
                        logger.info(
                            f"Starting auto-start stdio service after update: {updated_name}",
                        )
                        # If the service is already running, stop it before restarting
                        server_status = manager.get_server_status(updated_name)
                        if server_status.get("status") in ["running", "verified"]:
                            manager.stop_server(updated_name)

                        start_result = manager.start_server(updated_name)
                        if start_result:
                            return JSONResponse(
                                content={
                                    "message": f"Server {name} updated and started successfully",
                                },
                            )
                        return JSONResponse(
                            content={
                                "message": f"Server {name} updated but failed to start",
                            },
                        )
                    # Auto-connect sse/streamableHTTP type service
                    logger.info(
                        f"Connecting auto-connect remote service after update: {updated_name}",
                    )
                    server = manager.get_server(updated_name)
                    if server:
                        success, _ = await manager.verify_mcp_server(server)
                        if success:
                            logger.info(
                                f"Successfully auto-connected remote service {updated_name} after update",
                            )
                            return JSONResponse(
                                content={
                                    "message": f"Server {name} updated and connected successfully",
                                },
                            )
                        logger.error(
                            f"Failed to auto-connect remote service {updated_name} after update",
                        )
                        return JSONResponse(
                            content={
                                "message": f"Server {name} updated but failed to connect",
                            },
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to start/connect service {updated_name} after update: {e!s}",
                    )
                    return JSONResponse(
                        content={
                            "message": f"Server {name} updated but failed to start/connect: {e!s}",
                        },
                    )

            return JSONResponse(
                content={"message": f"Server {name} updated successfully"},
            )
        raise HTTPException(
            status_code=400, detail=f"Failed to update server {name}",
        )
    except ValueError as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        print(f"Value error: {error_details}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        print(f"Server update error: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update server: {e!s}",
        )


@app.delete("/api/servers/{name}")
async def remove_server(name: str) -> JSONResponse:
    """Remove MCP server"""
    try:
        decoded_name = unquote(name)
        print(
            f"[DEBUG] Request to delete service: original name={name}, decoded={decoded_name}",
        )
        success = manager.remove_server(decoded_name)
        if success:
            print(f"[DEBUG] Service {decoded_name} deleted successfully")
            return JSONResponse(
                content={"message": f"Server {decoded_name} removed successfully"},
            )
        print(
            f"[DEBUG] Service {decoded_name} deletion failed, not found or already removed",
        )
        raise HTTPException(
            status_code=400, detail=f"Failed to remove server {decoded_name}",
        )
    except ValueError as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        print(f"Value error: {error_details}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        print(f"Delete server exception: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete server: {e!s}",
        )


@app.post("/api/servers/{name}/start")
async def start_server(name: str) -> JSONResponse:
    """Start MCP server"""
    try:
        success = manager.start_server(name)
        if success:
            return JSONResponse(
                content={"message": f"Server {name} started successfully"},
            )
        raise HTTPException(
            status_code=400, detail=f"Failed to start server {name}",
        )
    except ValueError as e:
        # Special handling for Value error, usually JSON parsing issues
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Value error in start_server: {error_details}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other unexpected errors
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Server error in start_server: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Server operation failed: {e!s}",
        )


@app.post("/api/servers/{name}/stop")
async def stop_server(name: str) -> JSONResponse:
    """Stop MCP server"""
    try:
        success = manager.stop_server(name)
        if success:
            return JSONResponse(
                content={"message": f"Server {name} stopped successfully"},
            )
        raise HTTPException(status_code=400, detail=f"Failed to stop server {name}")
    except ValueError as e:
        # Special handling for Value error, usually JSON parsing issues
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Value error in stop_server: {error_details}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other unexpected errors
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Server error in stop_server: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Server operation failed: {e!s}",
        )


@app.post("/api/servers/{name}/restart")
async def restart_server(name: str) -> JSONResponse:
    """Restart MCP server"""
    try:
        success = manager.restart_server(name)
        if success:
            return JSONResponse(
                content={"message": f"Server {name} restarted successfully"},
            )
        raise HTTPException(
            status_code=400, detail=f"Failed to restart server {name}",
        )
    except ValueError as e:
        # Special handling for Value error, usually JSON parsing issues
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Value error in restart_server: {error_details}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other unexpected errors
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Server error in restart_server: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Server operation failed: {e!s}",
        )


@app.post("/api/servers/{name}/verify")
async def verify_server(name: str) -> JSONResponse:
    """Verify MCP server and get its tool list"""
    try:
        success, tools = await manager.verify_mcp_server(name)
        status = manager.get_server_status(name).get("status")
        server = manager.servers.get(name)
        if not success:
            # Distinguish types
            if server and server.config.transport_type in ["sse", "streamableHTTP"]:
                # As long as it's not an error, allow it to pass
                if status in ["running", "verified"]:
                    return JSONResponse(
                        content={
                            "message": f"Remote service {name} is connected, but tool list is not available",
                            "tools": tools,
                            "status": status,
                        },
                    )
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to connect to remote service: {server.error_message or 'Unknown error'}",
                )
            raise HTTPException(
                status_code=400,
                detail=f"Failed to verify server {name}, service might not be fully started yet.",
            )
        return JSONResponse(
            content={
                "message": f"Server {name} verified successfully",
                "tools": tools,
                "status": status,
            },
        )
    except ValueError as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        print(f"Value error: {error_details}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        print(f"Server update error: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update server: {e!s}",
        )


@app.post("/api/servers/{name}/test")
async def test_server(name: str) -> JSONResponse:
    """Test MCP server initialization and get service info"""
    try:
        # Check if server exists
        if name not in manager.servers:
            raise HTTPException(status_code=404, detail=f"Server {name} not found")

        server = manager.servers[name]

        # Test server initialization based on transport type
        success, tools = await manager.verify_mcp_server(name)

        if success:
            # Get original server instructions from MCP server initialization
            # Always prefer original server info over config instructions for test results
            original_instructions = "No Instructions"
            if hasattr(server, 'server_info') and server.server_info:
                server_instructions = server.server_info.get('instructions', '').strip()
                server_description = server.server_info.get('description', '').strip()
                if server_instructions:
                    original_instructions = server_instructions
                elif server_description:
                    original_instructions = server_description

            # Get server info for response
            server_info = {
                "name": server.config.name,
                "transport_type": server.config.transport_type,
                "instructions": original_instructions,
                "tools": tools,
                "status": server.status
            }

            return JSONResponse(
                content={
                    "message": f"服务 {name} 测试成功",
                    "server_info": server_info,
                    "success": True
                }
            )
        else:
            # Return error information
            error_msg = server.error_message or "测试失败，无法连接到服务"
            return JSONResponse(
                status_code=400,
                content={
                    "message": f"服务 {name} 测试失败: {error_msg}",
                    "success": False
                }
            )

    except Exception as e:
        import traceback

        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Test server error: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"测试服务失败: {e!s}",
        )


@app.post("/api/servers/test-config")
async def test_server_config(request: Request) -> JSONResponse:
    """Test MCP server configuration without saving it"""
    try:
        # Parse request body
        config_data = await request.json()

        # Validate required fields
        if not config_data.get('name'):
            raise HTTPException(status_code=400, detail="服务名称不能为空")

        if not config_data.get('transport_type'):
            raise HTTPException(status_code=400, detail="传输类型不能为空")

        transport_type = config_data['transport_type']

        if transport_type == 'stdio':
            if not config_data.get('command'):
                raise HTTPException(status_code=400, detail="stdio 类型服务需要指定命令")
        elif transport_type in ['sse', 'streamableHTTP']:
            if not config_data.get('url'):
                raise HTTPException(status_code=400, detail=f"{transport_type} 类型服务需要指定 URL")
        else:
            raise HTTPException(status_code=400, detail=f"不支持的传输类型: {transport_type}")

        # Create temporary server config for testing
        from mcp_dock.core.mcp_service import McpServerConfig, McpServerInstance

        temp_config = McpServerConfig(
            name=config_data['name'],
            transport_type=transport_type,
            command=config_data.get('command'),
            args=config_data.get('args', []),
            env=config_data.get('env', {}),
            url=config_data.get('url'),
            auto_start=False,  # Don't auto-start test configs
            instructions=config_data.get('instructions', "")
        )

        # Test the configuration by creating a temporary manager
        from mcp_dock.core.mcp_service import McpServiceManager

        # Create a temporary manager for testing
        temp_manager = McpServiceManager()

        try:
            # Add the temporary server to the manager
            temp_service = McpServerInstance(temp_config)
            temp_manager.servers[temp_config.name] = temp_service

            # Test the configuration
            success, tools = await temp_manager.verify_mcp_server(temp_config.name)

            if success:
                # Get server info
                status = "verified" if transport_type == 'stdio' else "connected"
                # For temporary test, use original instructions or "No Instructions"
                instructions = temp_config.instructions or "No Instructions"

                server_info = {
                    "name": temp_config.name,
                    "transport_type": temp_config.transport_type,
                    "status": status,
                    "instructions": instructions,
                    "tools": tools or []
                }

                return JSONResponse({
                    "success": True,
                    "message": f"服务 {temp_config.name} 测试成功",
                    "server_info": server_info
                })
            else:
                error_msg = "服务初始化失败，无法获取工具列表" if transport_type == 'stdio' else "无法连接到远程服务"
                raise HTTPException(status_code=400, detail=error_msg)

        finally:
            # Clean up temporary service
            if temp_config.name in temp_manager.servers:
                temp_service = temp_manager.servers[temp_config.name]
                if hasattr(temp_service, 'stop'):
                    await temp_service.stop()
                del temp_manager.servers[temp_config.name]

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = f"{e!s}\n{traceback.format_exc()}"
        logger.error(f"Test config error: {error_details}")
        raise HTTPException(
            status_code=500, detail=f"测试配置失败: {e!s}",
        )


@app.post("/api/import")
async def import_config(file: UploadFile = File(...)) -> JSONResponse:
    """Import configuration from file"""
    try:
        content = await file.read()
        config = json.loads(content)

        # 获取导入前的服务列表
        before_import = set(manager.servers.keys())

        success_count, failure_count = manager.import_config_from_json(config)

        # 获取导入后的服务列表，找出新增的服务
        after_import = set(manager.servers.keys())
        imported_servers = list(after_import - before_import)

        # 构建详细的响应信息
        message = f"配置导入完成"
        if success_count > 0:
            message += f"，成功导入 {success_count} 个服务"
        if failure_count > 0:
            message += f"，{failure_count} 个服务导入失败"

        # 检查是否有路径标准化的情况
        path_normalized = []
        for server_name in imported_servers:
            server = manager.servers.get(server_name)
            if server and server.config.command:
                # 检查是否是常见的可执行文件名（说明进行了路径标准化）
                common_executables = ['npx', 'node', 'python', 'python3', 'uv', 'pip', 'pip3']
                if server.config.command in common_executables:
                    path_normalized.append(server_name)

        return JSONResponse(
            content={
                "message": message,
                "success_count": success_count,
                "failure_count": failure_count,
                "imported_servers": imported_servers,
                "path_normalized": path_normalized,
                "details": {
                    "total_servers_in_config": len(config.get("mcpServers", {})),
                    "path_normalization_applied": len(path_normalized) > 0
                }
            },
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400, detail=f"配置文件格式错误，请确保是有效的JSON格式: {e!s}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"导入配置失败: {e!s}",
        )


# Add test route to ensure route registration works properly
@app.get("/api/test", response_model=dict[str, Any])
async def test_api() -> dict[str, Any]:
    """Test if API route is working properly"""
    return {
        "message": "API test route working properly",
        "time": time.time(),
        "routes": [
            {
                "path": route.path,
                "name": getattr(route, "name", "unknown"),
                "methods": list(getattr(route, "methods", [])),
            }
            for route in app.routes
            if hasattr(route, "path")
        ],
    }


# Add dynamic proxy route - this will handle all remaining requests, must be placed last
logger.debug("========================")
logger.debug("Registering dynamic proxy routes...")
logger.debug(f"Dynamic proxy route object: {dynamic_proxy.router}")
# Important: dynamic proxy must be registered last so it only captures requests not handled by other routes
app.include_router(dynamic_proxy.router)
logger.debug("Dynamic proxy route registration complete!")
logger.debug("========================")


@app.post("/api/restart")
async def restart_app() -> JSONResponse:
    """Force restart application server (asynchronous, won't wait)"""
    # Create child process for restart
    subprocess.Popen(["python", "run.py"])
    # Return success response
    return JSONResponse(
        content={"message": "Restart command sent, service will restart shortly"},
    )


def handle_exit(signum: int, frame: Any) -> None:
    print(f"\nReceived signal {signum}, gracefully exiting all MCP subprocesses...")
    for name in list(manager.servers.keys()):
        manager.stop_server(name)
    os._exit(0)  # Force kill current process (including reload parent process)


# Only register signal handler in actual service process
# Temporarily disabled to prevent unexpected server shutdown
# if os.environ.get("RUN_MAIN") == "true" or not os.environ.get("UVICORN_RELOAD"):
#     signal.signal(signal.SIGINT, handle_exit)
#     signal.signal(signal.SIGTERM, handle_exit)


# Start API service
def start_api(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start API service"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_api()
