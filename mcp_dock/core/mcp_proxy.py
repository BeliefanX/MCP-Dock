"""
MCP Proxy Module - Responsible for forwarding and aggregating MCP service requests
"""

import asyncio
import json
import os
import sys
import traceback
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

# Import MCP client libraries
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from mcp_dock.utils.logging_config import get_logger
from mcp_dock.core.mcp_compliance import MCPComplianceEnforcer, MCPErrorHandler
from mcp_dock.core.protocol_converter import get_universal_converter

logger = get_logger(__name__)


class ConnectionRetryManager:
    """Manages connection retries with exponential backoff"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def retry_with_backoff(self, operation, *args, **kwargs):
        """Execute operation with exponential backoff retry"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Operation failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Operation failed after {self.max_retries + 1} attempts: {e}")

        raise last_exception


class JsonRpcErrorCodes:
    """Standard JSON-RPC error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32099
    SERVER_ERROR_END = -32000


class ProtocolAdapter(ABC):
    """Abstract base class for MCP protocol adapters"""

    @abstractmethod
    async def create_session(self, server_config) -> AsyncIterator[ClientSession]:
        """Create a client session for the specific protocol"""
        pass

    @abstractmethod
    async def get_tools(self, server_config) -> list[dict[str, Any]]:
        """Get tools list for the specific protocol"""
        pass


class StdioProtocolAdapter(ProtocolAdapter):
    """Adapter for stdio protocol"""

    @asynccontextmanager
    async def create_session(self, server_config) -> AsyncIterator[ClientSession]:
        """Create stdio client session"""
        params = StdioServerParameters(
            command=server_config.command,
            args=server_config.args,
            env=server_config.env,
            cwd=server_config.cwd,
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def get_tools(self, server_config) -> list[dict[str, Any]]:
        """Get tools from stdio server"""
        try:
            async with self.create_session(server_config) as session:
                tools_result = await session.list_tools()
                return self._extract_tools(tools_result)
        except Exception as e:
            logger.error(f"Failed to get STDIO tools: {e}")
            return []

    def _extract_tools(self, tools_result) -> list[dict[str, Any]]:
        """Extract tools from MCP response"""
        if hasattr(tools_result, 'tools'):
            return tools_result.tools
        elif isinstance(tools_result, dict) and 'tools' in tools_result:
            return tools_result['tools']
        elif isinstance(tools_result, list):
            return tools_result
        return []


class SSEProtocolAdapter(ProtocolAdapter):
    """Adapter for SSE protocol"""

    @asynccontextmanager
    async def create_session(self, server_config) -> AsyncIterator[ClientSession]:
        """Create SSE client session"""
        if not server_config.url:
            raise ValueError("SSE server URL cannot be empty")

        async with sse_client(server_config.url, headers=server_config.headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def get_tools(self, server_config) -> list[dict[str, Any]]:
        """Get tools from SSE server"""
        try:
            async with self.create_session(server_config) as session:
                tools_result = await session.list_tools()
                return self._extract_tools(tools_result)
        except Exception as e:
            logger.error(f"Failed to get SSE tools: {e}")
            return []

    def _extract_tools(self, tools_result) -> list[dict[str, Any]]:
        """Extract tools from MCP response"""
        if hasattr(tools_result, 'tools'):
            return tools_result.tools
        elif isinstance(tools_result, dict) and 'tools' in tools_result:
            return tools_result['tools']
        elif isinstance(tools_result, list):
            return tools_result
        return []


class StreamableHTTPProtocolAdapter(ProtocolAdapter):
    """Adapter for streamable HTTP protocol"""

    @asynccontextmanager
    async def create_session(self, server_config) -> AsyncIterator[ClientSession]:
        """Create streamable HTTP client session"""
        if not server_config.url:
            raise ValueError("HTTP server URL cannot be empty")

        async with streamablehttp_client(server_config.url, headers=server_config.headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def get_tools(self, server_config) -> list[dict[str, Any]]:
        """Get tools from HTTP server"""
        try:
            async with self.create_session(server_config) as session:
                tools_result = await session.list_tools()
                return self._extract_tools(tools_result)
        except Exception as e:
            logger.error(f"Failed to get HTTP tools: {e}")
            return []

    def _extract_tools(self, tools_result) -> list[dict[str, Any]]:
        """Extract tools from MCP response"""
        if hasattr(tools_result, 'tools'):
            return tools_result.tools
        elif isinstance(tools_result, dict) and 'tools' in tools_result:
            return tools_result['tools']
        elif isinstance(tools_result, list):
            return tools_result
        return []


class ProtocolAdapterFactory:
    """Factory for creating protocol adapters"""

    _adapters = {
        "stdio": StdioProtocolAdapter,
        "sse": SSEProtocolAdapter,
        "streamableHTTP": StreamableHTTPProtocolAdapter,
    }

    @classmethod
    def create_adapter(cls, transport_type: str) -> ProtocolAdapter:
        """Create appropriate protocol adapter"""
        adapter_class = cls._adapters.get(transport_type)
        if not adapter_class:
            raise ValueError(f"Unsupported transport type: {transport_type}")
        return adapter_class()


@dataclass(slots=True)
class McpProxyConfig:
    """MCP Proxy Configuration"""

    name: str
    server_name: str  # Target MCP service name
    endpoint: str = "/mcp"  # Externally exposed endpoint path
    transport_type: str = "streamableHTTP"  # Externally exposed transport type
    exposed_tools: list[str] = field(
        default_factory=list,
    )  # List of tools to expose externally, empty means expose all
    auto_start: bool = False  # Whether to automatically start when the management tool starts
    description: str = ""  # Custom description for the proxy service


@dataclass(slots=True)
class McpProxyInstance:
    """MCP Proxy Instance"""

    config: McpProxyConfig
    status: str = "stopped"  # stopped, running, error
    error_message: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)  # Proxy tool list


class McpProxyManager:
    """MCP Proxy Manager"""

    # Singleton instance
    _instance = None

    @classmethod
    def get_instance(cls, mcp_manager=None):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls(mcp_manager)
        return cls._instance

    def __init__(self, mcp_manager=None):
        # If instance already exists, return it directly
        if McpProxyManager._instance is not None:
            return

        self.proxies: dict[str, McpProxyInstance] = {}
        self.mcp_manager = mcp_manager  # Reference to MCP service manager

        # Configuration file path
        # Get the directory where this file is located, then go up to find config
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # Go up from core/ to mcp_dock/
        self.config_dir = os.path.join(project_root, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, "proxy_config.json")

        # Load configuration
        self._load_config()

        # Save singleton
        McpProxyManager._instance = self

    async def initialize(self):
        """Asynchronous initialization method, contains logic for auto-starting proxies"""
        return await self._auto_start_proxies()

    async def _auto_start_proxies(self):
        """Start all proxies marked for auto-start"""
        auto_start_count = 0
        for name, proxy in self.proxies.items():
            if not proxy.config.auto_start:
                continue

            logger.info(f"Auto-starting proxy: {name}")
            try:
                # Check if the target MCP service is available
                if self.mcp_manager and proxy.config.server_name in self.mcp_manager.servers:
                    target_server = self.mcp_manager.servers[proxy.config.server_name]

                    # Check server status based on transport type
                    valid_statuses = []
                    if target_server.config.transport_type == "stdio":
                        valid_statuses = ["running", "verified"]
                    else:
                        # For sse/streamableHTTP servers
                        valid_statuses = ["connected", "running", "verified"]

                    logger.info(f"Checking proxy {name} target service {proxy.config.server_name}: status={target_server.status}, valid_statuses={valid_statuses}")

                    if target_server.status in valid_statuses:
                        # Mark proxy as running if target service is available
                        proxy.status = "running"
                        proxy.error_message = None

                        # Copy tools from target server if available
                        if target_server.tools:
                            proxy.tools = target_server.tools.copy() if isinstance(target_server.tools, list) else []
                            logger.info(f"Copied {len(proxy.tools)} tools from target service to proxy {name}")
                        else:
                            # For services without tools yet (e.g., stdio services still loading),
                            # schedule a delayed tool update
                            logger.info(f"Target service {proxy.config.server_name} has no tools yet, will retry after delay")
                            asyncio.create_task(self._delayed_proxy_tool_update(name))

                        auto_start_count += 1
                        logger.info(f"Proxy {name} auto-started successfully")
                    else:
                        proxy.status = "error"
                        proxy.error_message = f"Target service {proxy.config.server_name} is not available (status: {target_server.status}, expected: {valid_statuses})"
                        logger.warning(f"Proxy {name} auto-start failed: target service status {target_server.status} not in {valid_statuses}")
                else:
                    proxy.status = "error"
                    proxy.error_message = f"Target service {proxy.config.server_name} not found"
                    logger.warning(f"Proxy {name} auto-start failed: target service not found")
            except Exception as e:
                proxy.status = "error"
                proxy.error_message = str(e)
                logger.error(f"Proxy {name} auto-start exception: {e!s}")

        return auto_start_count

    async def _delayed_proxy_tool_update(self, proxy_name: str, max_retries: int = 5, delay: int = 2):
        """Delayed proxy tool update for services that need time to load tools

        Args:
            proxy_name: Name of the proxy to update
            max_retries: Maximum number of retry attempts
            delay: Delay in seconds between retries
        """
        for attempt in range(max_retries):
            await asyncio.sleep(delay)

            if proxy_name not in self.proxies:
                logger.warning(f"Proxy {proxy_name} no longer exists, stopping delayed tool update")
                return

            proxy = self.proxies[proxy_name]
            server_name = proxy.config.server_name

            if not self.mcp_manager or server_name not in self.mcp_manager.servers:
                logger.warning(f"Target service {server_name} no longer exists, stopping delayed tool update for proxy {proxy_name}")
                return

            target_server = self.mcp_manager.servers[server_name]

            # Check if target server now has tools
            if target_server.tools:
                proxy.tools = target_server.tools.copy() if isinstance(target_server.tools, list) else []
                logger.info(f"Delayed tool update successful for proxy {proxy_name}: copied {len(proxy.tools)} tools from target service")
                return
            else:
                logger.info(f"Delayed tool update attempt {attempt + 1}/{max_retries} for proxy {proxy_name}: target service still has no tools")

        # If we reach here, all retries failed
        logger.warning(f"Delayed tool update failed for proxy {proxy_name} after {max_retries} attempts")

    def _load_config(self) -> None:
        """Load proxy configuration from config file"""
        logger.info(f"Loading proxy configuration: {self.config_path}")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                # Process mcpProxies field
                if "mcpProxies" in config:
                    for name, proxy_config in config["mcpProxies"].items():
                        proxy = McpProxyConfig(
                            name=name,
                            server_name=proxy_config.get("server_name", ""),
                            endpoint=proxy_config.get("endpoint", "/mcp"),
                            transport_type=proxy_config.get(
                                "transport_type", "streamableHTTP",
                            ),
                            exposed_tools=proxy_config.get("exposed_tools", []),
                            auto_start=proxy_config.get("auto_start", False),
                            description=proxy_config.get("description", ""),
                        )
                        self.proxies[name] = McpProxyInstance(config=proxy)
                logger.info(f"Loaded {len(self.proxies)} proxy configurations")
            except Exception as e:
                logger.error(f"Failed to load proxy configuration: {e!s}")
        else:
            logger.info(
                "Proxy configuration file does not exist, using default settings",
            )

    def save_config(self) -> None:
        """Save proxy configuration to file"""
        config = {"mcpProxies": {}}
        for name, proxy in self.proxies.items():
            cfg = proxy.config
            config["mcpProxies"][name] = {
                "server_name": cfg.server_name,
                "endpoint": cfg.endpoint,
                "transport_type": cfg.transport_type,
                "exposed_tools": cfg.exposed_tools,
                "auto_start": cfg.auto_start,
                "description": cfg.description,
            }
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=4)
            logger.info(f"Proxy configuration saved to: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save proxy configuration: {e!s}")

    def add_proxy(self, config: McpProxyConfig) -> bool:
        """Add new MCP proxy configuration

        Args:
            config: MCP proxy configuration

        Returns:
            bool: Whether the addition was successful
        """
        if config.name in self.proxies:
            logger.warning(f"Proxy {config.name} already exists")
            return False

        # Add new proxy
        self.proxies[config.name] = McpProxyInstance(config=config)

        # Save configuration to file
        self.save_config()

        logger.info(f"Successfully added proxy {config.name}")
        return True

    def remove_proxy(self, name: str) -> bool:
        """Remove MCP proxy configuration

        Args:
            name: Proxy name

        Returns:
            bool: Whether the removal was successful
        """
        if name not in self.proxies:
            logger.warning(f"Proxy {name} does not exist")
            return False

        del self.proxies[name]
        logger.info(f"Removed proxy {name}")
        # Save configuration to file
        self.save_config()
        return True

    def update_proxy(self, name: str, config: McpProxyConfig) -> bool:
        """Update MCP proxy configuration

        Args:
            name: Current proxy name
            config: New MCP proxy configuration

        Returns:
            bool: Whether the update was successful
        """
        if name not in self.proxies:
            logger.warning(f"Proxy {name} does not exist")
            return False

        # If name changes, remove old configuration and add new one
        if name != config.name:
            del self.proxies[name]
        # Update proxy configuration
        self.proxies[config.name] = McpProxyInstance(config=config)

        logger.info(f"Updated proxy {name} to {config.name}")
        # Save configuration to file
        self.save_config()
        return True

    def get_proxy_status(self, name: str) -> dict[str, Any]:
        """Get proxy status

        Args:
            name: Proxy name

        Returns:
            dict[str, Any]: Proxy status information
        """
        if name not in self.proxies:
            raise ValueError(f"Proxy {name} does not exist")

        proxy = self.proxies[name]
        return {
            "name": proxy.config.name,
            "server_name": proxy.config.server_name,
            "endpoint": proxy.config.endpoint,
            "transport_type": proxy.config.transport_type,
            "status": proxy.status,
            "error_message": proxy.error_message,
            "tools_count": len(proxy.tools),
            "tools": proxy.tools,
            "exposed_tools": proxy.config.exposed_tools,
            "auto_start": proxy.config.auto_start,
            "description": proxy.config.description,
        }

    def get_all_proxy_statuses(self) -> list[dict[str, Any]]:
        """Get status information for all proxies

        Returns:
            list[dict[str, Any]]: List of status information for all proxies
        """
        return [self.get_proxy_status(name) for name in self.proxies]

    def get_all_proxies_status(self) -> list[dict[str, Any]]:
        """Alias for get_all_proxy_statuses for API compatibility

        Returns:
            list[dict[str, Any]]: List of status information for all proxies
        """
        return self.get_all_proxy_statuses()

    def get_all_proxies(self) -> dict[str, dict[str, Any]]:
        """Get all proxies as a dictionary

        Returns:
            dict[str, dict[str, Any]]: Dictionary of proxy name to proxy status information
        """
        result = {}
        for name in self.proxies:
            try:
                result[name] = self.get_proxy_status(name)
            except Exception as e:
                logger.error(f"Error getting status for proxy {name}: {e}")
                # Include basic info even if there's an error
                proxy = self.proxies[name]
                result[name] = {
                    "name": proxy.config.name,
                    "server_name": proxy.config.server_name,
                    "endpoint": proxy.config.endpoint,
                    "transport_type": proxy.config.transport_type,
                    "status": "error",
                    "error_message": str(e),
                    "tools_count": 0,
                    "tools": [],
                    "exposed_tools": proxy.config.exposed_tools,
                    "auto_start": proxy.config.auto_start,
                    "description": proxy.config.description,
                }
        return result

    async def update_proxy_tools(self, name: str) -> tuple[bool, list[dict[str, Any]]]:
        """Update proxy tool list

        Args:
            name: Proxy name

        Returns:
            tuple[bool, list[dict[str, Any]]]: (Whether the update was successful, tool list)
        """
        if name not in self.proxies:
            logger.error(f"Proxy {name} does not exist")
            return False, []

        proxy = self.proxies[name]
        server_name = proxy.config.server_name

        if not self.mcp_manager or server_name not in self.mcp_manager.servers:
            proxy.status = "error"
            proxy.error_message = f"Target service {server_name} does not exist"
            logger.error(f"Target service {server_name} does not exist")
            return False, []

        server = self.mcp_manager.servers[server_name]

        # Check server status based on transport type
        valid_statuses = []
        if server.config.transport_type == "stdio":
            valid_statuses = ["running", "verified"]
        else:
            # For sse/streamableHTTP servers
            valid_statuses = ["connected", "running", "verified"]

        if server.status not in valid_statuses:
            logger.error(
                f"Target service {server_name} is not available, current status: {server.status}, expected: {valid_statuses}",
            )
            proxy.status = "error"
            proxy.error_message = f"Target service {server_name} is not available (status: {server.status})"
            return False, []

        # Get the tool list from the target service
        if not server.tools:
            proxy.status = "error"
            proxy.error_message = f"Target service {server_name} has no tool list"
            return False, []

        logger.info(f"Starting to update tool list for proxy {name}")

        try:
            # If service status is valid and it has tools, use them directly
            if server.status in valid_statuses and server.tools:
                logger.info(
                    f"Using already available tool list from server {server_name}: {len(server.tools)} tools",
                )
                tools = server.tools.copy() if isinstance(server.tools, list) else []

                # Apply tool filtering
                if proxy.config.exposed_tools:
                    # If exposed tools list is specified, only expose tools with matching names
                    filtered_tools = [
                        t
                        for t in tools
                        if t.get("name", "") in proxy.config.exposed_tools
                    ]
                    logger.info(f"Filtered tool list: {len(filtered_tools)} tools from {len(tools)} total")
                    logger.info(f"Exposed tools filter: {proxy.config.exposed_tools}")
                    logger.info(f"Available tool names: {[t.get('name', '') for t in tools]}")
                    proxy.tools = filtered_tools
                else:
                    # Otherwise expose all tools
                    proxy.tools = tools

                proxy.status = "running"
                proxy.error_message = None
                logger.info(
                    f"Successfully updated tool list for proxy {name} with {len(proxy.tools)} tools",
                )
                return True, proxy.tools

            # Get tools using protocol adapter
            try:
                adapter = ProtocolAdapterFactory.create_adapter(server.config.transport_type)
                logger.info(
                    f"[{server.config.transport_type.upper()} Verification] Starting to get tool list for {server_name}",
                )
                tools = await adapter.get_tools(server.config)
                logger.info(
                    f"[{server.config.transport_type.upper()} Verification] Tool list retrieved successfully: {len(tools)} tools",
                )
            except ValueError as e:
                logger.error(f"Unsupported transport type: {e}")
                proxy.status = "error"
                proxy.error_message = str(e)
                return False, []

            # Update proxy tool list
            if tools:
                # Filter tools to be exposed
                if proxy.config.exposed_tools:
                    # If exposed tools list is specified, only expose tools with matching names
                    filtered_tools = [
                        t
                        for t in tools
                        if t.get("name", "") in proxy.config.exposed_tools
                    ]
                    logger.info(f"Filtered tool list: {len(filtered_tools)} tools from {len(tools)} total")
                    logger.info(f"Exposed tools filter: {proxy.config.exposed_tools}")
                    proxy.tools = filtered_tools
                else:
                    # Otherwise expose all tools
                    proxy.tools = tools

                # Update proxy status to running
                proxy.status = "running"
                proxy.error_message = None
                logger.info(
                    f"Successfully updated tool list for proxy {name} with {len(proxy.tools)} tools",
                )
                return True, proxy.tools
            logger.error("Failed to get tool list, result is empty")
            proxy.status = "error"
            proxy.error_message = "Failed to get tool list, result is empty"
            return False, []
        except Exception as e:
            logger.exception(f"Error updating tool list for proxy {name}: {e!s}")
            proxy.status = "error"
            proxy.error_message = str(e)
            return False, []

    async def proxy_request(
        self, name: str, request_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Proxy JSON-RPC request to target MCP service

        Args:
            name: Proxy name
            request_data: Request data

        Returns:
            dict[str, Any]: Response data
        """
        if name not in self.proxies:
            raise ValueError(f"Proxy {name} does not exist")

        proxy = self.proxies[name]
        server_name = proxy.config.server_name

        if not self.mcp_manager or server_name not in self.mcp_manager.servers:
            raise ValueError(f"Target service {server_name} does not exist")

        try:
            # Use the service manager to call the server instead of creating new connections
            # This avoids the need to create new stdio processes
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")

            # Special handling for list_tools - return proxy's filtered tools
            if method == "list_tools" or method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": proxy.tools},
                }

            # For other methods, delegate to the service manager
            result = await self.mcp_manager.call_server_method(
                server_name, method, params
            )

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }

        except Exception as e:
            logger.error(f"Error during proxy request: {e}")
            # Print complete stack trace for debugging
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.error("Exception stack trace: " + "".join(tb_lines))

            # Return a JSON-RPC error response
            if isinstance(request_data, dict) and "id" in request_data:
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32603,  # Internal error
                        "message": f"Proxy request processing error: {e!s}",
                    },
                }
            raise

    async def _process_jsonrpc_request(
        self,
        session: ClientSession,
        request_data: dict[str, Any],
        proxy: McpProxyInstance,
    ) -> dict[str, Any]:
        """Process JSON-RPC request

        Args:
            session: MCP client session
            request_data: Request data
            proxy: Proxy instance

        Returns:
            dict[str, Any]: Response data
        """
        # Handle resource methods with default empty responses for MCP Inspector compatibility
        if "method" in request_data:
            method = request_data["method"]
            if method == "resources/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": {"resources": []}
                }
            elif method == "resources/templates/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": {"resourceTemplates": []}
                }

        # Check if the method in the request is in the exposed tools list (only if exposed_tools is not empty)
        if proxy.config.exposed_tools and len(proxy.config.exposed_tools) > 0 and "method" in request_data:
            if request_data["method"] not in proxy.config.exposed_tools:
                # Provide default empty responses for resource methods to satisfy MCP Inspector
                if request_data["method"] == "resources/list":
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "result": {"resources": []}
                    }
                elif request_data["method"] == "resources/templates/list":
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "result": {"resourceTemplates": []}
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "error": {
                            "code": -32601,  # Method not found
                            "message": f"Method {request_data['method']} is not exposed in this proxy",
                        },
                    }

        try:
            # JSON-RPC 2.0 specification processing
            if isinstance(request_data, dict):
                # Single request
                method = request_data.get("method")
                params = request_data.get("params", {})

                # Directly call the MCP method
                if method == "list_tools" or method == "tools/list":
                    # Special handling for tool list requests, directly return the proxy's filtered tool list
                    result = {"tools": proxy.tools}
                    return {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "result": result,
                    }
                # Other methods are forwarded directly
                # send_request expects method name and params directly
                response = await session.send_request(method, params or {})
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": response,
                }
            if isinstance(request_data, list):
                # Batch request
                results = []
                for req in request_data:
                    # Recursively process each request
                    result = await self._process_jsonrpc_request(session, req, proxy)
                    results.append(result)
                return results
            # Invalid request
            raise ValueError("Invalid JSON-RPC request format")

        except Exception as e:
            logger.error(f"JSON-RPC request processing failed: {e}")
            # Print the full stack trace for debugging
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.error("Exception stack trace: " + "".join(tb_lines))

            if isinstance(request_data, dict) and "id" in request_data:
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32603,  # Internal error
                        "message": f"JSON-RPC request processing error: {e!s}",
                    },
                }
            raise

    async def create_proxy_stream(self, name: str, request_data: dict[str, Any]):
        """Create a proxy stream response generator with improved resource management

        Args:
            name: Proxy name
            request_data: Request data

        Returns:
            Response generator
        """
        if name not in self.proxies:
            error_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32000,
                        "message": f"Proxy {name} does not exist",
                    },
                },
            )
            yield error_msg
            return

        proxy = self.proxies[name]
        server_name = proxy.config.server_name

        if not self.mcp_manager or server_name not in self.mcp_manager.servers:
            error_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32000,
                        "message": f"Target service {server_name} does not exist",
                    },
                },
            )
            yield error_msg
            return

        server = self.mcp_manager.servers[server_name]

        try:
            # Use protocol adapter for backend connection based on server's transport type
            backend_adapter = ProtocolAdapterFactory.create_adapter(server.config.transport_type)

            # Create session and process streaming response
            async with backend_adapter.create_session(server.config) as session:
                # Process streaming response with proxy transport type consideration
                # The proxy's transport_type determines the output format for external clients
                async for chunk in self._process_stream_request(
                    session, request_data, proxy,
                ):
                    yield chunk

        except ValueError as e:
            # Handle unsupported transport type
            error_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32000,
                        "message": f"Unsupported transport type: {e}",
                    },
                },
            )
            yield error_msg
        except Exception as e:
            logger.error(f"Creating proxy stream failed: {e}")
            # Print full stack trace for debugging
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.error("Exception stack trace: " + "".join(tb_lines))

            error_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Proxy request processing error: {e!s}",
                    },
                },
            )
            yield error_msg

    async def _process_stream_request(
        self,
        session: ClientSession,
        request_data: dict[str, Any],
        proxy: McpProxyInstance,
    ):
        """Process stream request with improved data handling

        Args:
            session: MCP client session
            request_data: Request data
            proxy: Proxy instance

        Returns:
            Response generator
        """
        # Validate request format
        if not isinstance(request_data, dict):
            error_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32600,  # Invalid Request
                        "message": "Invalid request format",
                    },
                },
            )
            yield error_msg
            return

        # Handle resource methods with default empty responses for MCP Inspector compatibility
        if "method" in request_data:
            method = request_data["method"]
            if method == "resources/list":
                result_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": {"resources": []}
                })
                yield result_msg
                return
            elif method == "resources/templates/list":
                result_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": {"resourceTemplates": []}
                })
                yield result_msg
                return

        # Check if the method in the request is in the exposed tools list (only if exposed_tools is not empty)
        if proxy.config.exposed_tools and len(proxy.config.exposed_tools) > 0 and "method" in request_data:
            if request_data["method"] not in proxy.config.exposed_tools:
                # Provide default empty responses for resource methods to satisfy MCP Inspector
                if request_data["method"] == "resources/list":
                    result_msg = json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "result": {"resources": []}
                    })
                    yield result_msg
                    return
                elif request_data["method"] == "resources/templates/list":
                    result_msg = json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "result": {"resourceTemplates": []}
                    })
                    yield result_msg
                    return
                else:
                    error_msg = json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request_data.get("id"),
                            "error": {
                                "code": -32601,  # Method not found
                                "message": f"Method {request_data['method']} is not exposed in this proxy",
                            },
                        },
                    )
                    yield error_msg
                    return

        try:
            # Process JSON-RPC call and return results as stream
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")

            if method == "list_tools" or method == "tools/list":
                # Special handling for tool list requests, directly return the proxy's filtered tool list
                result = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"tools": proxy.tools},
                    },
                )
                yield result
            else:
                # Forward streaming request with proper error handling
                try:
                    # Check if session supports streaming
                    if hasattr(session, 'call_raw_stream'):
                        response_stream = await session.call_raw_stream(method, params)
                        async for chunk in response_stream:
                            # Format output based on proxy's transport type
                            formatted_chunk = self._format_response_for_proxy(chunk, proxy)
                            yield formatted_chunk
                    else:
                        # Fallback to regular call if streaming not supported
                        # send_request expects method name and params directly
                        response = await session.send_request(method, params or {})
                        result = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": response,
                        }
                        # Format output based on proxy's transport type
                        formatted_result = self._format_response_for_proxy(result, proxy)
                        yield formatted_result
                except AttributeError as e:
                    logger.warning(f"Session does not support streaming for method {method}: {e}")
                    # Fallback to regular call
                    # send_request expects method name and params directly
                    response = await session.send_request(method, params or {})
                    result = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": response,
                    }
                    # Format output based on proxy's transport type
                    formatted_result = self._format_response_for_proxy(result, proxy)
                    yield formatted_result

        except Exception as e:
            logger.error(f"Processing stream request failed: {e}")
            # Print full stack trace for debugging
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.error("Exception stack trace: " + "".join(tb_lines))

            error_msg = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "error": {
                        "code": -32603,  # Internal error
                        "message": f"Stream request processing error: {e!s}",
                    },
                },
            )
            yield error_msg

    def _format_response_for_proxy(self, response_data: Any, proxy: McpProxyInstance) -> str:
        """Format response data according to proxy's transport type

        Args:
            response_data: Raw response data from backend
            proxy: Proxy instance with configuration

        Returns:
            str: Formatted response string
        """
        # Parse response data if it's a string
        if isinstance(response_data, str):
            try:
                response_dict = json.loads(response_data)
            except json.JSONDecodeError:
                # If not valid JSON, wrap it in a JSON-RPC response
                return json.dumps({"data": response_data})
        elif isinstance(response_data, dict):
            response_dict = response_data
        elif isinstance(response_data, list):
            return json.dumps(response_data)
        else:
            # Convert other types to string and wrap in JSON
            return json.dumps({"data": str(response_data)})

        # Ensure MCP Inspector compatibility for initialize responses
        if (isinstance(response_dict, dict) and
            response_dict.get("jsonrpc") == "2.0" and
            "result" in response_dict):

            result = response_dict["result"]

            # Check if this is an initialize response that needs fixing
            if ("protocolVersion" in result and
                "capabilities" in result and
                "serverInfo" in result):

                # Apply MCP compliance fixes
                response_dict["result"] = MCPComplianceEnforcer.fix_initialization_response(result)

                # Add proxy-specific instructions if missing
                if response_dict["result"]["serverInfo"].get("instructions") is None:
                    proxy_name = proxy.config.name
                    response_dict["result"]["serverInfo"]["instructions"] = (
                        f"MCP-Dock proxy server for {proxy_name}. "
                        f"This server provides access to tools from the underlying MCP service through a unified interface."
                    )

        # Return the formatted JSON string
        return json.dumps(response_dict)


