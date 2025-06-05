"""
MCP Service Management Module - Responsible for MCP service lifecycle management
"""

import asyncio
import json
import os
import subprocess
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# MCP 1.9.0 version API changes significantly, directly use the mcp package, no longer import specific transport classes
from typing import Any

import psutil
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from mcp_dock.utils.logging_config import get_logger
from mcp_dock.core.mcp_compliance import (
    MCPComplianceEnforcer,
    MCPComplianceValidator,
    MCPErrorHandler,
    MCPInitializationResult
)

# Configure logging
logger = get_logger(__name__)

try:
    from modelcontextprotocol import MCPClient
except ImportError:
    MCPClient = None


@dataclass(slots=True)
class McpServerConfig:
    """MCP Server Configuration"""

    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    transport_type: str = "stdio"  # stdio, sse, streamableHTTP
    port: int | None = None  # Used for sse and streamableHTTP
    endpoint: str | None = None  # Service endpoint (URL path)
    url: str | None = None  # Only for sse/streamableHTTP
    headers: dict[str, str] | None = field(
        default_factory=dict,
    )  # Only for sse/streamableHTTP
    auto_start: bool = False  # For stdio type, whether to automatically start when the management tool starts
    instructions: str = ""  # Instructions for using the service (replaces description)


@dataclass
class McpServerInstance:
    """MCP Server Instance"""

    config: McpServerConfig
    process: subprocess.Popen | None = None
    pid: int | None = None
    status: str = "stopped"  # stopped, running, error, verified
    start_time: float | None = None
    error_message: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)  # MCP tool list
    server_info: dict[str, Any] = field(default_factory=dict)  # Original server info from MCP server

    def __hash__(self):
        """Make McpServerInstance hashable based on server name"""
        return hash(self.config.name)

    def __eq__(self, other):
        """Define equality based on server name"""
        if not isinstance(other, McpServerInstance):
            return False
        return self.config.name == other.config.name


class McpServiceManager:
    """MCP Service Manager"""

    def __init__(self, config_path: str = None):
        self.servers: dict[str, McpServerInstance] = {}
        # Priority: 1. Provided config_path 2. Project config directory
        if config_path:
            self.config_path = config_path
        else:
            # Get the directory where this file is located, then go up to find config
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # Go up from core/ to mcp_dock/
            self.config_path = os.path.join(project_root, "config", "mcp.config.json")
        self._ensure_config_dir()
        self._load_config()
        # Don't call auto-start during initialization, leave it for external async call

    async def initialize(self):
        """Asynchronous initialization method, contains logic for auto-starting/connecting services"""
        return await self._auto_start_services()

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    async def _auto_start_services(self):
        """Start all services marked for auto-start/connect"""
        auto_start_count = 0
        for name, server in self.servers.items():
            if not server.config.auto_start:
                continue

            if server.config.transport_type == "stdio":
                # Auto-start stdio type services
                logger.info(f"Auto-starting stdio service: {name}")
                try:
                    success = self.start_server(name)
                    if success:
                        auto_start_count += 1
                        logger.info(f"stdio service {name} auto-started successfully")
                    else:
                        logger.error(f"stdio service {name} failed to auto-start")
                except Exception as e:
                    logger.error(f"stdio service {name} auto-start exception: {e!s}")

            else:
                # Auto-connect sse/streamableHTTP type services
                logger.info(f"Auto-connecting remote service: {name}")
                try:
                    # Correctly use await for calling async methods
                    success, tools = await self.verify_mcp_server(name)
                    if success:
                        auto_start_count += 1
                        server.status = "connected"
                        server.tools = tools
                        logger.info(
                            f"Remote service {name} auto-connected successfully",
                        )
                    else:
                        server.status = "disconnected"
                        logger.error(f"Remote service {name} failed to auto-connect")
                except Exception as e:
                    server.status = "disconnected"
                    server.error_message = str(e)
                    logger.error(
                        f"Remote service {name} auto-connect exception: {e!s}",
                    )

        return auto_start_count

    def _parse_args(self, args_raw):
        """
        Parse arguments into a list format, supporting various input formats:
        - List: Already in desired format
        - JSON string: Containing a list
        - Newline/space delimited string: Split into list items
        - Simple string: Wrapped in a list

        Args:
            args_raw: Arguments in various formats (list, str, etc.)

        Returns:
            List[str]: Processed arguments as a list
        """
        # If already a list, return directly
        if isinstance(args_raw, list):
            return [str(arg) for arg in args_raw if arg is not None]

        # If it's a string, try to parse it
        if isinstance(args_raw, str):
            s = args_raw.strip()
            if not s:
                return []

            # Try JSON parsing first
            try:
                val = json.loads(s)
                if isinstance(val, list):
                    return [str(item) for item in val if item is not None]
            except json.JSONDecodeError:
                # JSON parsing failed, try other methods
                pass

            # Check for special delimiters
            if "\n" in s:
                return [x.strip() for x in s.split("\n") if x.strip()]
            if " " in s:
                return [x.strip() for x in s.split(" ") if x.strip()]

            # Single argument, wrap in a list
            return [s]

        # If other type, try to convert
        if args_raw is not None:
            try:
                # Try to convert to string
                return [str(args_raw)]
            except Exception:
                logger.warning(
                    f"Cannot convert parameter to string, ignoring: {args_raw}",
                )

        return []

    def _load_config(self):
        """Load service configurations from config file"""
        logger.info(f"Loading configuration from {self.config_path}")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                # Process mcpServers field
                if "mcpServers" in config:
                    for name, server_config in config["mcpServers"].items():

                        def get_field(sc, key):
                            # Prioritize underscore style, compatible with camelCase
                            return (
                                sc.get(key)
                                if key in sc
                                else sc.get(
                                    "".join(
                                        [
                                            key.split("_")[0],
                                            key.title().replace("_", "")[1:],
                                        ],
                                    ),
                                    None,
                                )
                            )

                        # Read auto-start field, supports both underscore and camelCase naming styles
                        auto_start_value = get_field(server_config, "auto_start")
                        if auto_start_value is None:
                            auto_start_value = get_field(server_config, "autoStart")
                        # If it's a JSON array string like ["a", "b"], parse it as a boolean value
                        if isinstance(auto_start_value, str):
                            auto_start_value = auto_start_value.lower() == "true"

                        server = McpServerConfig(
                            name=name,
                            command=get_field(server_config, "command") or "",
                            args=self._parse_args(
                                get_field(server_config, "args") or [],
                            ),
                            env=get_field(server_config, "env") or {},
                            cwd=get_field(server_config, "cwd"),
                            transport_type=get_field(server_config, "transport_type")
                            or get_field(server_config, "transportType")
                            or "stdio",
                            port=get_field(server_config, "port"),
                            endpoint=get_field(server_config, "endpoint"),
                            url=get_field(server_config, "url"),
                            headers=get_field(server_config, "headers") or {},
                            auto_start=bool(auto_start_value)
                            if auto_start_value is not None
                            else False,
                            instructions=get_field(server_config, "instructions") or get_field(server_config, "description") or "",
                        )
                        self.servers[name] = McpServerInstance(config=server)
                logger.info(f"Loaded {len(self.servers)} server configurations")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e!s}")
        else:
            logger.info("Configuration file does not exist, creating new configuration")

    def save_config(self) -> None:
        """Save service configurations to config file"""
        config = {"mcpServers": {}}
        for name, server in self.servers.items():
            cfg = server.config
            config["mcpServers"][name] = {
                "command": cfg.command,
                "args": cfg.args,
                "env": cfg.env,
                "cwd": cfg.cwd,
                "transport_type": cfg.transport_type,
                "port": cfg.port,
                "endpoint": cfg.endpoint,
                "url": cfg.url,
                "headers": cfg.headers,
                "auto_start": cfg.auto_start,
                "instructions": cfg.instructions,
            }
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e!s}")

    def add_server(self, config: McpServerConfig) -> bool:
        """Add new MCP server configuration

        Args:
            config: MCP server configuration

        Returns:
            bool: Whether the addition was successful
        """
        if config.name in self.servers:
            logger.warning(f"Server {config.name} already exists")
            return False

        config.args = self._parse_args(config.args)
        self.servers[config.name] = McpServerInstance(config=config)
        self.save_config()
        logger.info(f"Added server {config.name}")
        return True

    def remove_server(self, name: str) -> bool:
        """Remove MCP server configuration

        Args:
            name: Server name

        Returns:
            bool: Whether the removal was successful
        """
        if name not in self.servers:
            logger.warning(f"Server {name} not found")
            return False

        # Ensure the service is stopped
        self.stop_server(name)

        del self.servers[name]
        self.save_config()
        logger.info(f"Removed server {name}")
        return True

    def update_server(self, name: str, config: McpServerConfig) -> bool:
        """Update MCP server configuration

        Args:
            name: Current server name
            config: New MCP server configuration

        Returns:
            bool: Whether the update was successful
        """
        if name not in self.servers:
            logger.warning(f"Server {name} not found")
            return False

        # Ensure the service is stopped
        was_running = self.servers[name].status == "running"
        if was_running:
            self.stop_server(name)

        # If the name has changed, delete the old configuration and add the new one
        if name != config.name:
            del self.servers[name]
            self.servers[config.name] = McpServerInstance(config=config)
        else:
            self.servers[name].config = config

        config.args = self._parse_args(config.args)
        self.save_config()

        # If it was running before, restart it
        if was_running:
            self.start_server(config.name)

        logger.info(f"Updated server {name} to {config.name}")
        return True

    def start_server(self, name: str) -> bool:
        """Start MCP server

        Args:
            name: Server name

        Returns:
            bool: Whether the start was successful
        """
        if (server := self.servers.get(name)) is None:
            logger.warning(f"Server {name} not found")
            return False
        if server.status == "running":
            logger.info(f"Server {name} is already running")
            return True
        # Distinguish between types
        if server.config.transport_type in ["sse", "streamableHTTP"]:
            server.status = "running"
            server.error_message = None
            logger.info(
                f"Remote MCP service {name} marked as running (no local process to start)",
            )
            return True
        # stdio type no longer starts the process manually, just mark it as running
        server.status = "running"
        server.error_message = None
        logger.info(
            f"Local MCP service {name} marked as running (process managed by stdio_client)",
        )

        # For stdio type services, immediately get the tool list
        if server.config.transport_type == "stdio":
            logger.info(f"Automatically getting tool list for service {name}...")

            # Create an asynchronous task to get the tool list
            async def verify_task():
                try:
                    success, tools = await self.verify_mcp_server(name)
                    if success:
                        logger.info(
                            f"Service {name} auto-get tool list successful: {len(tools)} tools",
                        )
                    else:
                        logger.warning(f"Service {name} auto-get tool list failed")
                except Exception as e:
                    logger.error(
                        f"Service {name} auto-get tool list exception: {e!s}",
                    )

            # Use asyncio.create_task to start the asynchronous task
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(verify_task())
                else:
                    # If there is no running event loop, create a new one
                    asyncio.run_coroutine_threadsafe(verify_task(), loop)
                logger.info(f"Started service {name} auto-get tool list task")
            except Exception as e:
                logger.error(
                    f"Failed to start service {name} auto-get tool list task: {e!s}",
                )

        return True

    def stop_server(self, name: str) -> bool:
        """Stop MCP server

        Args:
            name: Server name

        Returns:
            bool: Whether the stop operation was successful
        """
        if (server := self.servers.get(name)) is None:
            logger.warning(f"Server {name} not found")
            return False

        # For remote services, just mark the status
        if server.config.transport_type in ["sse", "streamableHTTP"]:
            server.status = "stopped"
            server.error_message = None
            logger.info(
                f"Remote MCP service {name} marked as stopped (no need to stop local process)",
            )
            return True

        # If not running or no PID, return directly
        if server.status != "running" or not server.pid:
            logger.info(f"Server {name} is not running")
            server.status = "stopped"
            return True

        try:
            # Get parent process
            try:
                parent = psutil.Process(server.pid)
            except psutil.NoSuchProcess:
                logger.info(f"Process {server.pid} no longer exists")
                server.status = "stopped"
                server.pid = None
                server.process = None
                return True

            # Prefer gentle termination method
            logger.debug(f"Starting to terminate process group {server.pid}")

            # 1. First try to gracefully terminate child processes
            children = []
            try:
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        logger.debug(
                            f"Sending SIGTERM signal to child process {child.pid}",
                        )
                        child.terminate()
                    except Exception as e:
                        logger.debug(
                            f"Error terminating child process {child.pid}: {e!s}",
                        )
            except Exception as e:
                logger.debug(f"Error getting child processes: {e!s}")

            # Wait for child processes to end, maximum 3 seconds
            if children:
                _, alive_children = psutil.wait_procs(children, timeout=3)

                # If some child processes couldn't terminate normally, force termination
                for child in alive_children:
                    try:
                        logger.debug(
                            f"Sending SIGKILL signal to child process {child.pid}",
                        )
                        child.kill()
                    except Exception as e:
                        logger.debug(
                            f"Error force terminating child process {child.pid}: {e!s}",
                        )

            # 2. Then terminate the parent process
            try:
                if parent.is_running():
                    logger.debug(
                        f"Sending SIGTERM signal to parent process {parent.pid}",
                    )
                    parent.terminate()

                    # Wait for parent process to end, maximum 3 seconds
                    gone, alive = psutil.wait_procs([parent], timeout=3)

                    # If parent process couldn't terminate normally, force termination
                    if alive and parent.is_running():
                        logger.debug(
                            f"Sending SIGKILL signal to parent process {parent.pid}",
                        )
                        parent.kill()
            except Exception as e:
                logger.debug(f"Error terminating parent process: {e!s}")
                # 确保进程被关闭
                try:
                    if parent.is_running():
                        parent.kill()
                except Exception:
                    pass

            # 最终检查进程是否还存在
            try:
                if parent.is_running():
                    logger.warning(f"无法完全终止进程 {parent.pid}")
                    return False
            except psutil.NoSuchProcess:
                pass  # 进程已终止，符合预期

            # 清理进程引用
            server.process = None
            server.pid = None
            server.status = "stopped"
            logger.info(f"已停止服务器 {name}")
            return True

        except Exception as e:
            server.error_message = str(e)
            logger.error(f"停止服务器 {name} 失败: {e!s}")
            return False

    def restart_server(self, name: str) -> bool:
        """Restart MCP server

        Args:
            name: Server name

        Returns:
            bool: Whether the restart was successful
        """
        if (server := self.servers.get(name)) is None:
            logger.warning(f"Server {name} not found")
            return False
        if server.config.transport_type in ["sse", "streamableHTTP"]:
            logger.info(f"Remote MCP service {name} restart only marks as running")
            server.status = "running"
            server.error_message = None
            return True
        self.stop_server(name)
        time.sleep(1)
        return self.start_server(name)

    async def call_server_method(self, name: str, method: str, params: dict = None) -> Any:
        """Call a method on a running MCP server

        Args:
            name: Server name
            method: Method name to call
            params: Method parameters

        Returns:
            Any: Method result

        Raises:
            ValueError: If server not found or not running
            Exception: If method call fails
        """
        if name not in self.servers:
            raise ValueError(f"Server {name} not found")

        server = self.servers[name]

        # Check server status based on transport type
        valid_statuses = []
        if server.config.transport_type == "stdio":
            valid_statuses = ["running"]
        else:
            # For sse/streamableHTTP servers
            valid_statuses = ["connected", "running"]

        if server.status not in valid_statuses:
            raise ValueError(f"Server {name} is not available (status: {server.status}, expected: {valid_statuses})")

        if params is None:
            params = {}

        try:
            if server.config.transport_type == "stdio":
                # For stdio servers, create a new connection
                cmd = (server.config.command or "").strip()
                args = [a for a in (server.config.args or []) if a and str(a).strip()]
                env = server.config.env or {}
                cwd = server.config.cwd or None

                stdio_params = StdioServerParameters(
                    command=cmd,
                    args=args,
                    env=env,
                    cwd=cwd
                )

                async with stdio_client(stdio_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        # Use send_request for arbitrary method calls
                        # Create the appropriate request object based on method
                        if method == "initialize":
                            from mcp.types import InitializeRequest, InitializeRequestParams, InitializeResult
                            request_params = InitializeRequestParams(**params)
                            request = InitializeRequest(
                                method="initialize",
                                params=request_params
                            )
                            result = await session.send_request(request, InitializeResult)
                            # Convert InitializeResult to dict for JSON serialization
                            if hasattr(result, 'model_dump'):
                                result = result.model_dump()
                            elif hasattr(result, '__dict__'):
                                result = result.__dict__
                        else:
                            # For other methods, use proper MCP client methods
                            try:
                                # Try to use the appropriate MCP client method
                                if method == "tools/call":
                                    from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult
                                    tool_params = CallToolRequestParams(
                                        name=params.get("name"),
                                        arguments=params.get("arguments", {})
                                    )
                                    request = CallToolRequest(
                                        method="tools/call",
                                        params=tool_params
                                    )
                                    result = await session.send_request(request, CallToolResult)
                                    # Convert result to dict for JSON serialization
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                                elif method == "tools/list":
                                    from mcp.types import ListToolsRequest, ListToolsResult
                                    request = ListToolsRequest(method="tools/list")
                                    result = await session.send_request(request, ListToolsResult)
                                    # Convert result to dict for JSON serialization
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                                elif method == "notifications/initialized":
                                    # Handle initialized notification
                                    from mcp.types import InitializedNotification
                                    notification = InitializedNotification(
                                        method="notifications/initialized"
                                        # params is optional and defaults to None
                                    )
                                    await session.send_notification(notification)
                                    # Notifications don't return a result
                                    result = {"success": True}
                                elif method.startswith("notifications/"):
                                    # Handle other notifications
                                    # Create a notification object that send_notification can handle
                                    class CustomNotification:
                                        def __init__(self, method: str, params: dict = None):
                                            self.method = method
                                            self.params = params

                                        def model_dump(self, by_alias=True, mode="json", exclude_none=True):
                                            """Provide model_dump method for compatibility with MCP session"""
                                            result = {"method": self.method}
                                            if self.params is not None:
                                                result["params"] = self.params
                                            return result

                                    notification = CustomNotification(method=method, params=params)
                                    await session.send_notification(notification)
                                    # Notifications don't return a result
                                    result = {"success": True}
                                else:
                                    # For other methods, use send_request with proper method and params
                                    result = await session.send_request(method, params or {})

                            except Exception as e:
                                # Check if this is a "Method not found" error for resource methods
                                error_msg = str(e).lower()
                                if "method not found" in error_msg and method in ["resources/list", "resources/templates/list"]:
                                    # Provide default empty response for unsupported resource methods
                                    logger.info(f"Providing default empty response for unsupported method {method}")
                                    if method == "resources/list":
                                        return {"resources": []}
                                    elif method == "resources/templates/list":
                                        return {"resourceTemplates": []}

                                logger.error(f"Error calling method {method}: {e}")
                                raise
                        return result

            elif server.config.transport_type == "sse":
                # For SSE servers, use SSE client
                base_url = server.config.url
                headers = server.config.headers or {}

                async with sse_client(base_url, headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        # Use send_request for arbitrary method calls
                        # Create the appropriate request object based on method
                        if method == "initialize":
                            from mcp.types import InitializeRequest, InitializeRequestParams, InitializeResult
                            request_params = InitializeRequestParams(**params)
                            request = InitializeRequest(
                                method="initialize",
                                params=request_params
                            )
                            result = await session.send_request(request, InitializeResult)
                            # Convert InitializeResult to dict for JSON serialization
                            if hasattr(result, 'model_dump'):
                                result = result.model_dump()
                            elif hasattr(result, '__dict__'):
                                result = result.__dict__
                        else:
                            # For other methods, use proper MCP client methods
                            try:
                                # Try to use the appropriate MCP client method
                                if method == "tools/call":
                                    from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult
                                    tool_params = CallToolRequestParams(
                                        name=params.get("name"),
                                        arguments=params.get("arguments", {})
                                    )
                                    request = CallToolRequest(
                                        method="tools/call",
                                        params=tool_params
                                    )
                                    result = await session.send_request(request, CallToolResult)
                                    # Convert result to dict for JSON serialization
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                                elif method == "tools/list":
                                    from mcp.types import ListToolsRequest, ListToolsResult
                                    request = ListToolsRequest(method="tools/list")
                                    result = await session.send_request(request, ListToolsResult)
                                    # Convert result to dict for JSON serialization
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                                elif method == "notifications/initialized":
                                    # Handle initialized notification
                                    from mcp.types import InitializedNotification
                                    notification = InitializedNotification(
                                        method="notifications/initialized"
                                        # params is optional and defaults to None
                                    )
                                    await session.send_notification(notification)
                                    # Notifications don't return a result
                                    result = {"success": True}
                                elif method.startswith("notifications/"):
                                    # Handle other notifications
                                    # Create a notification object that send_notification can handle
                                    class CustomNotification:
                                        def __init__(self, method: str, params: dict = None):
                                            self.method = method
                                            self.params = params

                                        def model_dump(self, by_alias=True, mode="json", exclude_none=True):
                                            """Provide model_dump method for compatibility with MCP session"""
                                            result = {"method": self.method}
                                            if self.params is not None:
                                                result["params"] = self.params
                                            return result

                                    notification = CustomNotification(method=method, params=params)
                                    await session.send_notification(notification)
                                    # Notifications don't return a result
                                    result = {"success": True}
                                else:
                                    # For other methods, use specific MCP types when available
                                    from mcp.types import Request

                                    # Handle specific methods with proper result types
                                    if method == "resources/list":
                                        from mcp.types import ListResourcesResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ListResourcesResult),
                                            timeout=30.0
                                        )
                                    elif method == "resources/templates/list":
                                        from mcp.types import ListResourceTemplatesResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ListResourceTemplatesResult),
                                            timeout=30.0
                                        )
                                    elif method in ["resources/read"]:
                                        from mcp.types import ReadResourceResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ReadResourceResult),
                                            timeout=30.0
                                        )
                                    elif method in ["prompts/list"]:
                                        from mcp.types import ListPromptsResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ListPromptsResult),
                                            timeout=30.0
                                        )
                                    elif method in ["prompts/get"]:
                                        from mcp.types import GetPromptResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, GetPromptResult),
                                            timeout=30.0
                                        )
                                    else:
                                        # For truly unknown methods, use a generic approach
                                        # Create a custom result type that can handle any response
                                        from typing import Any
                                        from pydantic import BaseModel

                                        class GenericResult(BaseModel):
                                            data: Any = None

                                            @classmethod
                                            def model_validate(cls, obj):
                                                if isinstance(obj, dict):
                                                    return cls(data=obj)
                                                return cls(data=obj)

                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, GenericResult),
                                            timeout=30.0
                                        )
                                        # Extract the actual data from our wrapper
                                        if hasattr(result, 'data'):
                                            result = result.data

                                    # Convert result to dict if needed
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                            except asyncio.TimeoutError:
                                raise Exception(f"Request timeout after 30 seconds for method {method}")
                            except Exception as e:
                                # Check if this is a "Method not found" error for resource methods
                                error_msg = str(e).lower()
                                if "method not found" in error_msg and method in ["resources/list", "resources/templates/list"]:
                                    # Provide default empty response for unsupported resource methods
                                    logger.info(f"Providing default empty response for unsupported method {method}")
                                    if method == "resources/list":
                                        return {"resources": []}
                                    elif method == "resources/templates/list":
                                        return {"resourceTemplates": []}

                                logger.error(f"Error calling method {method}: {e}")
                                raise
                        return result

            elif server.config.transport_type == "streamableHTTP":
                # For HTTP servers, use streamable HTTP client
                base_url = server.config.url
                headers = server.config.headers or {}

                async with streamablehttp_client(base_url, headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        # Use send_request for arbitrary method calls
                        # Create the appropriate request object based on method
                        if method == "initialize":
                            from mcp.types import InitializeRequest, InitializeRequestParams, InitializeResult
                            request_params = InitializeRequestParams(**params)
                            request = InitializeRequest(
                                method="initialize",
                                params=request_params
                            )
                            result = await session.send_request(request, InitializeResult)
                            # Convert InitializeResult to dict for JSON serialization
                            if hasattr(result, 'model_dump'):
                                result = result.model_dump()
                            elif hasattr(result, '__dict__'):
                                result = result.__dict__
                        else:
                            # For other methods, use proper MCP client methods
                            try:
                                # Try to use the appropriate MCP client method
                                if method == "tools/call":
                                    from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult
                                    tool_params = CallToolRequestParams(
                                        name=params.get("name"),
                                        arguments=params.get("arguments", {})
                                    )
                                    request = CallToolRequest(
                                        method="tools/call",
                                        params=tool_params
                                    )
                                    result = await session.send_request(request, CallToolResult)
                                    # Convert result to dict for JSON serialization
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                                elif method == "tools/list":
                                    from mcp.types import ListToolsRequest, ListToolsResult
                                    request = ListToolsRequest(method="tools/list")
                                    result = await session.send_request(request, ListToolsResult)
                                    # Convert result to dict for JSON serialization
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                                elif method == "notifications/initialized":
                                    # Handle initialized notification
                                    from mcp.types import InitializedNotification
                                    notification = InitializedNotification(
                                        method="notifications/initialized"
                                        # params is optional and defaults to None
                                    )
                                    await session.send_notification(notification)
                                    # Notifications don't return a result
                                    result = {"success": True}
                                elif method.startswith("notifications/"):
                                    # Handle other notifications
                                    # Create a notification object that send_notification can handle
                                    class CustomNotification:
                                        def __init__(self, method: str, params: dict = None):
                                            self.method = method
                                            self.params = params

                                        def model_dump(self, by_alias=True, mode="json", exclude_none=True):
                                            """Provide model_dump method for compatibility with MCP session"""
                                            result = {"method": self.method}
                                            if self.params is not None:
                                                result["params"] = self.params
                                            return result

                                    notification = CustomNotification(method=method, params=params)
                                    await session.send_notification(notification)
                                    # Notifications don't return a result
                                    result = {"success": True}
                                else:
                                    # For other methods, use specific MCP types when available
                                    from mcp.types import Request

                                    # Handle specific methods with proper result types
                                    if method == "resources/list":
                                        from mcp.types import ListResourcesResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ListResourcesResult),
                                            timeout=30.0
                                        )
                                    elif method == "resources/templates/list":
                                        from mcp.types import ListResourceTemplatesResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ListResourceTemplatesResult),
                                            timeout=30.0
                                        )
                                    elif method in ["resources/read"]:
                                        from mcp.types import ReadResourceResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ReadResourceResult),
                                            timeout=30.0
                                        )
                                    elif method in ["prompts/list"]:
                                        from mcp.types import ListPromptsResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, ListPromptsResult),
                                            timeout=30.0
                                        )
                                    elif method in ["prompts/get"]:
                                        from mcp.types import GetPromptResult
                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, GetPromptResult),
                                            timeout=30.0
                                        )
                                    else:
                                        # For truly unknown methods, use a generic approach
                                        # Create a custom result type that can handle any response
                                        from typing import Any
                                        from pydantic import BaseModel

                                        class GenericResult(BaseModel):
                                            data: Any = None

                                            @classmethod
                                            def model_validate(cls, obj):
                                                if isinstance(obj, dict):
                                                    return cls(data=obj)
                                                return cls(data=obj)

                                        request = Request(method=method, params=params)
                                        result = await asyncio.wait_for(
                                            session.send_request(request, GenericResult),
                                            timeout=30.0
                                        )
                                        # Extract the actual data from our wrapper
                                        if hasattr(result, 'data'):
                                            result = result.data

                                    # Convert result to dict if needed
                                    if hasattr(result, 'model_dump'):
                                        result = result.model_dump()
                                    elif hasattr(result, '__dict__'):
                                        result = result.__dict__
                            except asyncio.TimeoutError:
                                raise Exception(f"Request timeout after 30 seconds for method {method}")
                            except Exception as e:
                                # Check if this is a "Method not found" error for resource methods
                                error_msg = str(e).lower()
                                if "method not found" in error_msg and method in ["resources/list", "resources/templates/list"]:
                                    # Provide default empty response for unsupported resource methods
                                    logger.info(f"Providing default empty response for unsupported method {method}")
                                    if method == "resources/list":
                                        return {"resources": []}
                                    elif method == "resources/templates/list":
                                        return {"resourceTemplates": []}

                                logger.error(f"Error calling method {method}: {e}")
                                raise
                        return result

            else:
                raise ValueError(f"Unsupported transport type: {server.config.transport_type}")

        except Exception as e:
            logger.error(f"Failed to call method {method} on server {name}: {e}")
            raise

    async def verify_mcp_server(self, name: str) -> tuple[bool, list[dict]]:
        """Verify MCP server and get tools list"""
        if name not in self.servers:
            return False, []
        server = self.servers[name]
        try:
            tools = []
            if server.config.transport_type == "stdio":
                # Detailed logging and robust handling
                cmd = (server.config.command or "").strip()
                args = [a for a in (server.config.args or []) if a and str(a).strip()]
                env = server.config.env or {}
                cwd = server.config.cwd or None
                logger.debug(f"[STDIO Verification] Command: {cmd}")
                logger.debug(f"[STDIO Verification] Arguments: {args}")
                logger.debug(f"[STDIO Verification] Environment variables: {env}")
                logger.debug(f"[STDIO Verification] Working directory: {cwd}")

                # Check environment variables
                env_check_passed, env_error = self._check_environment_variables(
                    name, env,
                )
                if not env_check_passed:
                    logger.warning(
                        f"[STDIO Verification] Environment variable issues detected: {env_error}",
                    )
                    # Continue running, but log a warning
                if not cmd:
                    server.status = "error"
                    server.error_message = "Command cannot be empty!"
                    logger.error("[STDIO Verification] Command cannot be empty!")
                    return False, []
                params = StdioServerParameters(command=cmd, args=args, env=env, cwd=cwd)

                # 定义异步操作函数，用于重试
                async def connect_stdio_and_get_tools():
                    async with stdio_client(params) as (read, write):
                        async with ClientSession(read, write) as session:
                            init_result = await session.initialize()

                            # Store complete initialization result for MCP 2025-03-26 compliance
                            init_response = {
                                'protocolVersion': getattr(init_result, 'protocolVersion', '2025-03-26'),
                                'capabilities': {},
                                'serverInfo': {},
                                'instructions': getattr(init_result, 'instructions', None)
                            }

                            # Process capabilities with full field handling
                            if hasattr(init_result, 'capabilities') and init_result.capabilities:
                                caps = init_result.capabilities
                                init_response['capabilities'] = {
                                    'logging': getattr(caps, 'logging', None) or {},
                                    'prompts': getattr(caps, 'prompts', None),
                                    'resources': getattr(caps, 'resources', None),
                                    'tools': getattr(caps, 'tools', None),
                                    'experimental': getattr(caps, 'experimental', None)
                                }

                            # Store server info from initialization with complete field handling
                            if hasattr(init_result, 'serverInfo') and init_result.serverInfo:
                                server_info_obj = init_result.serverInfo
                                server.server_info = {
                                    'name': getattr(server_info_obj, 'name', ''),
                                    'version': getattr(server_info_obj, 'version', ''),
                                    'instructions': getattr(server_info_obj, 'instructions', None),
                                    'description': getattr(server_info_obj, 'description', None)
                                }
                                init_response['serverInfo'] = server.server_info
                            elif hasattr(init_result, 'server_info') and init_result.server_info:
                                server_info_obj = init_result.server_info
                                server.server_info = {
                                    'name': getattr(server_info_obj, 'name', ''),
                                    'version': getattr(server_info_obj, 'version', ''),
                                    'instructions': getattr(server_info_obj, 'instructions', None),
                                    'description': getattr(server_info_obj, 'description', None)
                                }
                                init_response['serverInfo'] = server.server_info

                            # Apply MCP compliance fixes
                            server.initialization_result = MCPComplianceEnforcer.fix_initialization_response(init_response)

                            tools_result = await session.list_tools()
                            # 打印原始工具对象格式以便调试
                            logger.debug(
                                f"[STDIO Debug] Original Tool List Type: {type(tools_result)}",
                            )
                            logger.debug(
                                f"[STDIO 调试] 原始工具列表内容: {json.dumps(tools_result, default=lambda o: str(o), indent=2)}",
                            )
                            if hasattr(tools_result, "result"):
                                logger.debug(
                                    f"[STDIO 调试] tools_result.result类型: {type(tools_result.result)}",
                                )
                                logger.debug(
                                    f"[STDIO 调试] tools_result.result内容: {json.dumps(tools_result.result, default=lambda o: str(o), indent=2)}",
                                )

                            # 正确处理ListToolsResult对象
                            tools = []
                            # 可能是列表或ListToolsResult对象，尝试转换
                            if hasattr(tools_result, "tools") and hasattr(
                                tools_result.tools, "__iter__",
                            ):
                                # 直接从tools属性获取工具列表
                                tools = list(tools_result.tools)
                                logger.debug(
                                    f"[STDIO 调试] 从tools_result.tools获取了{len(tools)}个工具",
                                )
                            elif hasattr(tools_result, "__iter__") and not isinstance(
                                tools_result, (str, bytes),
                            ):
                                # 尝试作为可迭代对象处理
                                tools = list(tools_result)
                                logger.debug(
                                    f"[STDIO 调试] 通过迭代tools_result获取了{len(tools)}个工具",
                                )
                            elif hasattr(tools_result, "result") and hasattr(
                                tools_result.result, "__iter__",
                            ):
                                # 从result属性获取
                                tools = list(tools_result.result)
                                logger.debug(
                                    f"[STDIO 调试] 从tools_result.result获取了{len(tools)}个工具",
                                )
                            else:
                                # 最后，尝试作为单个工具处理
                                tools = [tools_result] if tools_result else []
                                logger.debug(
                                    f"[STDIO 调试] 作为单个工具处理，获取了{len(tools)}个工具",
                                )
                            return tools

                try:
                    # 使用重试机制
                    success, result = await retry_async_operation(
                        connect_stdio_and_get_tools,
                        max_retries=3,  # 初始尝试 + 3次重试
                        retry_delay=1.0,
                        backoff_factor=2.0,
                    )

                    if success:
                        tools = result
                    else:
                        logger.error(
                            f"[STDIO Verification] Connection failed, still failed after retry: {result}",
                        )
                        server.status = "error"
                        server.error_message = f"STDIO verification failed, still failed after retry: {result}"
                        return False, []

                    if tools:
                        parsed_tools = self._parse_tools_list(tools)
                        # Apply MCP compliance fixes to all tools
                        server.tools = [MCPComplianceEnforcer.fix_tool_definition(tool) for tool in parsed_tools]
                        # For stdio-type services, we keep the status as "running" instead of "connected"
                        server.status = "running"
                        server.error_message = ""
                        logger.info(
                            f"[MCP Verification] Tool list retrieved successfully: {len(server.tools)} tools",
                        )
                        return True, server.tools
                except Exception as e:
                    logger.error(f"[STDIO Verification] Connection failed: {e}")
                    server.status = "error"
                    server.error_message = f"STDIO verification failed: {e}"
                    return False, []
            elif server.config.transport_type == "sse":
                # SSE verification section
                base_url = server.config.url
                if not base_url:
                    logger.error(
                        "[SSE Verification] Remote service URL cannot be empty",
                    )
                    server.status = "error"
                    server.error_message = "Remote service URL cannot be empty"
                    return False, []

                # Try connecting to different endpoints
                endpoints = [base_url]
                # If URL does not end with /mcp/sse, add it as an alternative endpoint
                if not base_url.endswith("/mcp/sse"):
                    endpoints.append(f"{base_url}/mcp/sse")
                tried = []

                try:
                    for ep in endpoints:
                        try:
                            logger.info(f"[SSE Verification] Attempting to connect to {ep}")

                            # 定义异步操作，用于重试
                            async def connect_and_get_tools() -> list[Any]:
                                try:
                                    headers = server.config.headers or {}

                                    async with sse_client(ep, headers=headers) as (
                                        read,
                                        write,
                                    ):
                                        async with ClientSession(read, write) as session:
                                            init_result = await session.initialize()

                                            # Store server info from initialization
                                            if hasattr(init_result, 'serverInfo') and init_result.serverInfo:
                                                server.server_info = {
                                                    'name': getattr(init_result.serverInfo, 'name', ''),
                                                    'version': getattr(init_result.serverInfo, 'version', ''),
                                                    'instructions': getattr(init_result.serverInfo, 'instructions', ''),
                                                    'description': getattr(init_result.serverInfo, 'description', '')
                                                }

                                            tools_result = await session.list_tools()
                                            # 打印原始工具对象格式以便调试
                                            logger.debug(
                                                f"[SSE调试] 原始工具列表类型: {type(tools_result)}",
                                            )
                                            logger.debug(
                                                f"[SSE调试] 原始工具列表内容: {json.dumps(tools_result, default=lambda o: str(o), indent=2)}",
                                            )
                                            if hasattr(tools_result, "result"):
                                                logger.debug(
                                                    f"[SSE调试] tools_result.result类型: {type(tools_result.result)}",
                                                )
                                                logger.debug(
                                                    f"[SSE调试] tools_result.result内容: {json.dumps(tools_result.result, default=lambda o: str(o), indent=2)}",
                                                )

                                            # 正确处理ListToolsResult对象
                                            tools = []
                                            if hasattr(tools_result, "tools") and hasattr(
                                                tools_result.tools, "__iter__",
                                            ):
                                                # 直接从tools属性获取工具列表
                                                tools = list(tools_result.tools)
                                                logger.debug(
                                                    f"[SSE调试] 从tools_result.tools获取了{len(tools)}个工具",
                                                )
                                            elif hasattr(
                                                tools_result, "__iter__",
                                            ) and not isinstance(
                                                tools_result, (str, bytes),
                                            ):
                                                # 尝试作为可迭代对象处理
                                                tools = list(tools_result)
                                                logger.debug(
                                                    f"[SSE调试] 通过迭代tools_result获取了{len(tools)}个工具",
                                                )
                                            elif hasattr(
                                                tools_result, "result",
                                            ) and hasattr(tools_result.result, "__iter__"):
                                                # 从result属性获取
                                                tools = list(tools_result.result)
                                                logger.debug(
                                                    f"[SSE调试] 从tools_result.result获取了{len(tools)}个工具",
                                                )
                                            else:
                                                # 最后尝试作为单个工具处理
                                                tools = (
                                                    [tools_result] if tools_result else []
                                                )
                                                logger.debug(
                                                    f"[SSE调试] 作为单个工具处理，获取了{len(tools)}个工具",
                                                )
                                            return tools
                                except Exception as e:
                                    logger.warning(
                                        f"[SSE Verification] Connection attempt failed: {e!s}",
                                    )
                                    raise  # 重新抛出异常以便重试机制捕获

                            # 使用重试机制执行操作
                            success, result = await retry_async_operation(
                                connect_and_get_tools,
                                max_retries=3,  # 4次尝试(初始+3次重试)
                                retry_delay=2.0,
                                backoff_factor=2.0,
                                exceptions_to_retry=(Exception,),
                            )

                            if success:
                                tools = result
                            else:
                                # 重试失败，记录错误
                                logger.warning(f"连接到 {ep} 重试后仍然失败: {result!s}")
                                tried.append(f"{ep}: 重试后连接失败: {result!s}")
                                continue

                            if tools:
                                parsed_tools = self._parse_tools_list(tools)
                                server.tools = parsed_tools
                                server.status = "connected"
                                server.error_message = ""
                                logger.info(
                                    f"[SSE Verification] Tool list is successfully obtained: {len(server.tools)}个工具",
                                )
                                return True, server.tools
                            else:
                                 tried.append(f"{ep}: 未获取到有效的工具列表")
                        except Exception as e:
                            logger.error(f"[SSE Verification] {ep} connection failed: {e}")
                            tried.append(f"{ep}: {e}")

                    # All endpoint attempts failed
                    server.status = "disconnected"
                    server.error_message = f"SSE verification failed for all endpoints: {'; '.join(tried)}"
                    logger.error(f"[SSE Verification] All endpoints failed: {'; '.join(tried)}")
                    return False, []
                except Exception as e:
                    logger.error(f"[SSE Verification] Overall SSE verification failed: {e}")
                    server.status = "error"
                    server.error_message = f"SSE verification failed: {e}"
                    return False, []
            elif server.config.transport_type == "streamableHTTP":
                # StreamableHTTP verification section
                base_url = server.config.url
                if not base_url:
                    logger.error(
                        "[StreamableHTTP Verification] Remote service URL cannot be empty",
                    )
                    server.status = "error"
                    server.error_message = "Remote service URL cannot be empty"
                    return False, []

                try:
                    logger.info(f"[StreamableHTTP Verification] Attempting to connect to {base_url}")

                    # 定义异步操作，用于重试
                    async def connect_and_get_tools() -> list[Any]:
                        try:
                            headers = server.config.headers or {}

                            async with streamablehttp_client(base_url, headers=headers) as (
                                read,
                                write,
                            ):
                                async with ClientSession(read, write) as session:
                                    init_result = await session.initialize()

                                    # Store server info from initialization
                                    if hasattr(init_result, 'serverInfo') and init_result.serverInfo:
                                        server.server_info = {
                                            'name': getattr(init_result.serverInfo, 'name', ''),
                                            'version': getattr(init_result.serverInfo, 'version', ''),
                                            'instructions': getattr(init_result.serverInfo, 'instructions', ''),
                                            'description': getattr(init_result.serverInfo, 'description', '')
                                        }

                                    tools_result = await session.list_tools()
                                    # 打印原始工具对象格式以便调试
                                    logger.debug(
                                        f"[StreamableHTTP调试] 原始工具列表类型: {type(tools_result)}",
                                    )
                                    logger.debug(
                                        f"[StreamableHTTP调试] 原始工具列表内容: {json.dumps(tools_result, default=lambda o: str(o), indent=2)}",
                                    )
                                    if hasattr(tools_result, "result"):
                                        logger.debug(
                                            f"[StreamableHTTP调试] tools_result.result类型: {type(tools_result.result)}",
                                        )
                                        logger.debug(
                                            f"[StreamableHTTP调试] tools_result.result内容: {json.dumps(tools_result.result, default=lambda o: str(o), indent=2)}",
                                        )

                                    # 正确处理ListToolsResult对象
                                    tools = []
                                    if hasattr(tools_result, "tools") and hasattr(
                                        tools_result.tools, "__iter__",
                                    ):
                                        # 直接从tools属性获取工具列表
                                        tools = list(tools_result.tools)
                                        logger.debug(
                                            f"[StreamableHTTP调试] 从tools_result.tools获取了{len(tools)}个工具",
                                        )
                                    elif hasattr(
                                        tools_result, "__iter__",
                                    ) and not isinstance(
                                        tools_result, (str, bytes),
                                    ):
                                        # 尝试作为可迭代对象处理
                                        tools = list(tools_result)
                                        logger.debug(
                                            f"[StreamableHTTP调试] 通过迭代tools_result获取了{len(tools)}个工具",
                                        )
                                    elif hasattr(
                                        tools_result, "result",
                                    ) and hasattr(tools_result.result, "__iter__"):
                                        # 从result属性获取
                                        tools = list(tools_result.result)
                                        logger.debug(
                                            f"[StreamableHTTP调试] 从tools_result.result获取了{len(tools)}个工具",
                                        )
                                    else:
                                        # 最后尝试作为单个工具处理
                                        tools = (
                                            [tools_result] if tools_result else []
                                        )
                                        logger.debug(
                                            f"[StreamableHTTP调试] 作为单个工具处理，获取了{len(tools)}个工具",
                                        )
                                    return tools
                        except Exception as e:
                            logger.warning(
                                f"[StreamableHTTP Verification] Connection attempt failed: {e!s}",
                            )
                            raise  # 重新抛出异常以便重试机制捕获

                    # 使用重试机制执行操作
                    success, result = await retry_async_operation(
                        connect_and_get_tools,
                        max_retries=4,  # 5次尝试(初始+4次重试)
                        retry_delay=1.0,
                        backoff_factor=1.5,
                        exceptions_to_retry=(Exception,),
                    )

                    if success:
                        tools = result
                        if tools:
                            parsed_tools = self._parse_tools_list(tools)
                            server.tools = parsed_tools
                            server.status = "connected"
                            server.error_message = ""
                            logger.info(
                                f"[StreamableHTTP Verification] Tool list is successfully obtained: {len(server.tools)}个工具",
                            )
                            return True, server.tools
                        else:
                            server.status = "disconnected"
                            server.error_message = "未获取到有效的工具列表"
                            logger.error("[StreamableHTTP Verification] 未获取到有效的工具列表")
                            return False, []
                    else:
                        # 重试失败，记录错误
                        server.status = "disconnected"
                        server.error_message = f"StreamableHTTP verification failed: {result!s}"
                        logger.error(f"[StreamableHTTP Verification] 重试后仍然失败: {result!s}")
                        return False, []
                except Exception as e:
                    server.status = "disconnected"
                    server.error_message = f"StreamableHTTP verification failed: {e!s}"
                    logger.error(f"[StreamableHTTP Verification] connection failed: {e}")
                    return False, []
            else:
                # 未知的传输类型
                logger.error(f"Unknown transport type: {server.config.transport_type}")
                server.status = "error"
                server.error_message = f"Unknown transport type: {server.config.transport_type}"
                return False, []

                # All endpoint attempts failed
                if server.config.transport_type == "stdio":
                    server.status = "error"
                else:
                    # sse/streamableHTTP类型使用disconnected状态
                    server.status = "disconnected"
                server.error_message = (
                    f"All endpoint verifications failed: {'; '.join(tried)}"
                )
                logger.error(
                    f"[SSE Verification] All endpoint verifications failed: {'; '.join(tried)}",
                )
                return False, []
            # If we reach here, all verification attempts have failed
            return False, []
        except Exception as e:
            # Set different error status based on service type
            if server.config.transport_type == "stdio":
                server.status = "error"
            else:
                # sse/streamableHTTP类型使用disconnected状态
                server.status = "disconnected"
            server.error_message = f"Error verifying server: {e!s}"
            logger.error(f"[MCP Verification] Error verifying server: {e!s}")
            return False, []

    def _parse_tools_list(self, tools) -> list[dict]:
        """Parse the tools list, uniformly processing tool objects and dictionaries

        Args:
            tools: Original tools list (could be objects or dictionaries)

        Returns:
            list[dict]: Parsed tools list
        """
        if not tools:
            return []

        # Print detailed information about the first tool object
        if len(tools) > 0:
            tool_item = tools[0]
            logger.debug(f"[Tool Analysis] First tool item type: {type(tool_item)}")
            logger.debug(
                f"[Tool Parser] First tool item content: {json.dumps(tool_item, default=lambda o: str(o), indent=2)}",
            )
            logger.debug(
                f"[Tool Parser] First tool item attributes: {dir(tool_item) if not isinstance(tool_item, dict) else list(tool_item.keys())}",
            )

        # Enhanced tool list parsing logic with proper MCP schema support
        parsed_tools = []
        for t in tools:
            # If it's a tool object, directly get attributes
            if hasattr(t, "name") and hasattr(t, "description"):
                name = str(getattr(t, "name", ""))
                desc = str(getattr(t, "description", ""))

                # Get inputSchema - this is required by MCP protocol
                input_schema = getattr(t, "inputSchema", None)
                if input_schema is None:
                    # Provide default empty schema if missing
                    input_schema = {"type": "object", "properties": {}}
                elif hasattr(input_schema, "__dict__"):
                    # Convert object to dict if needed
                    input_schema = input_schema.__dict__

                tool_dict = {
                    "name": name.strip(),
                    "description": desc.strip(),
                    "inputSchema": input_schema
                }
                parsed_tools.append(tool_dict)
                logger.debug(
                    f"[Tool Parser] Object attributes - Name: {name}, Description: {desc[:30] if desc else 'None'}..., Schema: {type(input_schema)}",
                )
            # If it's a dictionary, get dictionary values
            elif isinstance(t, dict) and "name" in t:
                name = str(t["name"])
                desc = str(t.get("description", ""))

                # Ensure inputSchema is present and valid
                input_schema = t.get("inputSchema")
                if input_schema is None:
                    input_schema = {"type": "object", "properties": {}}

                tool_dict = {
                    "name": name.strip(),
                    "description": desc.strip(),
                    "inputSchema": input_schema
                }
                parsed_tools.append(tool_dict)
                logger.debug(
                    f"[Tool Parser] Dictionary - Name: {name}, Description: {desc[:30] if desc else 'None'}..., Schema: {type(input_schema)}",
                )
            # For other cases, try to convert to string
            else:
                tool_str = str(t)
                tool_dict = {
                    "name": f"Tool-{len(parsed_tools) + 1}",
                    "description": tool_str[:200] + ("..." if len(tool_str) > 200 else ""),
                    "inputSchema": {"type": "object", "properties": {}}
                }
                parsed_tools.append(tool_dict)

        # Ensure there are at least some tools
        if not parsed_tools and tools:
            parsed_tools = [
                {
                    "name": f"Tool-{i + 1}",
                    "description": str(t)[:200] + "...",
                    "inputSchema": {"type": "object", "properties": {}}
                }
                for i, t in enumerate(tools[:10])
            ]

        return parsed_tools

    def get_server(self, name: str) -> McpServerInstance | None:
        """Get server instance by name

        Args:
            name: Server name

        Returns:
            McpServerInstance: Server instance, returns None if it doesn't exist
        """
        return self.servers.get(name)

    def get_server_status(self, name: str) -> dict[str, Any]:
        """Get server status information

        Args:
            name: Server name

        Returns:
            Dict: Status information
        """
        if name not in self.servers:
            return {"error": f"Server {name} not found"}
        server = self.servers[name]
        # Monitor status based on service type using match-case (Python 3.12 optimization)
        match server.config.transport_type:
            case "stdio":
                # stdio type service status set: stopped, running, error
                # Remove verified status, standardize to running
                if server.status == "verified":
                    server.status = "running"

                # Check process running status
                if server.status == "running" and server.pid:
                    try:
                        process = psutil.Process(server.pid)
                        if process.status() != psutil.STATUS_RUNNING:
                            server.status = "stopped"
                            server.pid = None
                            server.process = None
                            server.tools = None
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        server.status = "stopped"
                        server.pid = None
                        server.process = None
                        server.tools = None
            case "sse" | "streamableHTTP":
                # sse/streamableHTTP type service status set: connected, disconnected
                # Convert status using match-case for better performance
                match server.status:
                    case "verified" | "running":
                        server.status = "connected"
                    case "stopped":
                        server.status = "disconnected"
        # sse/streamableHTTP type does not depend on pid
        status_info = {
            "name": server.config.name,
            "status": server.status,
            "pid": server.pid if server.config.transport_type == "stdio" else None,
            "command": server.config.command,
            "args": server.config.args,
            "env": server.config.env,
            "cwd": server.config.cwd,
            "transport_type": server.config.transport_type,
            "port": server.config.port,
            "endpoint": server.config.endpoint,
            "url": server.config.url,
            "headers": server.config.headers,
            "uptime": time.time() - server.start_time if server.start_time else None,
            "auto_start": server.config.auto_start,
            "instructions": server.config.instructions,
            "server_info": server.server_info,
        }
        if server.error_message:
            status_info["error"] = server.error_message
        if server.tools is None:
            server.tools = []
        if isinstance(server.tools, list) and server.tools:
            status_info["tools"] = server.tools
        else:
            status_info["tools"] = []
        return status_info

    def get_all_servers_status(self) -> list[dict[str, Any]]:
        """Get status information for all servers

        Returns:
            List[Dict]: List of status information for all servers
        """
        return [self.get_server_status(name) for name in self.servers]

    def _normalize_path(self, path: str) -> str:
        """Normalize path for cross-platform compatibility

        Args:
            path: Original path string

        Returns:
            str: Normalized path
        """
        if not path:
            return path

        # Convert absolute paths to relative paths when possible
        if os.path.isabs(path):
            # Try to find common executable names and convert to relative
            common_executables = {
                'npx': 'npx',
                'node': 'node',
                'python': 'python',
                'python3': 'python3',
                'uv': 'uv',
                'pip': 'pip',
                'pip3': 'pip3'
            }

            basename = os.path.basename(path)
            if basename in common_executables:
                logger.info(f"Converting absolute path {path} to relative: {basename}")
                return basename

            # For other absolute paths, log a warning but keep the original
            logger.warning(f"Absolute path detected: {path}. This may not work across different environments.")

        return path

    def _get_field_with_fallback(self, config: dict, field_name: str, default=None):
        """Get field value with fallback to camelCase naming

        Args:
            config: Configuration dictionary
            field_name: Field name in snake_case
            default: Default value if field not found

        Returns:
            Field value or default
        """
        # First try snake_case (preferred)
        if field_name in config:
            return config[field_name]

        # Then try camelCase for backward compatibility
        camel_case = field_name
        if "_" in field_name:
            parts = field_name.split("_")
            camel_case = parts[0] + "".join(word.capitalize() for word in parts[1:])

        return config.get(camel_case, default)

    def import_config_from_json(self, config_json: dict) -> tuple[int, int]:
        """Import configuration from JSON

        Args:
            config_json: Configuration JSON object

        Returns:
            tuple[int, int]: Number of successfully imported servers and number of failures
        """
        success_count = 0
        failure_count = 0

        if "mcpServers" in config_json:
            for name, server_config in config_json["mcpServers"].items():
                try:
                    # Get command and normalize path
                    command = self._get_field_with_fallback(server_config, "command", "")
                    if command:
                        command = self._normalize_path(command)

                    # Get transport type with proper fallback
                    transport_type = self._get_field_with_fallback(server_config, "transport_type", "stdio")

                    # Get auto_start with proper fallback
                    auto_start = self._get_field_with_fallback(server_config, "auto_start", False)

                    config = McpServerConfig(
                        name=name,
                        command=command,
                        args=self._parse_args(self._get_field_with_fallback(server_config, "args", [])),
                        env=self._get_field_with_fallback(server_config, "env", {}),
                        cwd=self._get_field_with_fallback(server_config, "cwd"),
                        transport_type=transport_type,
                        port=self._get_field_with_fallback(server_config, "port"),
                        endpoint=self._get_field_with_fallback(server_config, "endpoint"),
                        url=self._get_field_with_fallback(server_config, "url"),
                        headers=self._get_field_with_fallback(server_config, "headers", {}),
                        auto_start=bool(auto_start),
                        instructions=self._get_field_with_fallback(server_config, "instructions", "") or self._get_field_with_fallback(server_config, "description", ""),
                    )

                    logger.info(f"Importing server '{name}' with transport_type: {transport_type}")

                    if self.add_server(config):
                        success_count += 1
                        logger.info(f"Successfully imported server: {name}")
                    else:
                        failure_count += 1
                        logger.warning(f"Failed to add server: {name}")
                except Exception as e:
                    logger.error(f"Failed to import server {name}: {e!s}")
                    failure_count += 1

        self.save_config()
        logger.info(f"Import completed: {success_count} successful, {failure_count} failed")
        return success_count, failure_count

    def _check_environment_variables(self, server_name, env_dict):
        """Check if environment variables exist, only check format not specific variables

        Args:
            server_name: Server name
            env_dict: Environment variables dictionary

        Returns:
            tuple[bool, str]: (Whether passed check, error message)
        """
        if not env_dict:
            return True, ""

        missing_vars = []

        # Check variable reference format in the environment variables dictionary
        for key, value in env_dict.items():
            if isinstance(value, str) and value.startswith("$"):
                # Handle ${VAR} or $VAR format
                var_name = value.lstrip("$").strip("{}")
                if not os.getenv(var_name):
                    missing_vars.append(f"{key}=${var_name}")

        if missing_vars:
            error_msg = f"Service {server_name} references unset environment variables: {', '.join(missing_vars)}"
            logger.warning(error_msg)
            return False, error_msg

        return True, ""


# 添加HTTP请求重试函数
async def retry_async_operation(
    operation: Callable[[], Awaitable],
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions_to_retry=(Exception,),
) -> tuple[bool, Any]:
    """
    通用异步操作重试函数，支持指数退避策略

    Args:
        operation: 要重试的异步操作函数
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟(秒)
        backoff_factor: 退避因子，每次重试延迟时间乘以此值
        exceptions_to_retry: 需要重试的异常类型

    Returns:
        tuple[bool, Any]: (成功标志, 操作结果）
    """
    last_exception = None
    current_delay = retry_delay

    for attempt in range(max_retries + 1):  # +1 是因为首次尝试
        try:
            if attempt > 0:
                logger.debug(
                    f"Retry attempt {attempt}/{max_retries}, delay: {current_delay:.2f}s",
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff_factor  # 指数退避

            result = await operation()
            return True, result

        except exceptions_to_retry as e:
            last_exception = e
            logger.debug(
                f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e!s}",
            )

            # 最后一次尝试失败
            if attempt == max_retries:
                logger.warning(
                    f"Operation failed after {max_retries + 1} attempts: {e!s}",
                )
                break

    return False, last_exception
