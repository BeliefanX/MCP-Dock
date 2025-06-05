"""
Protocol Converter Module - Handles complete MCP protocol conversions between all transport types
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, AsyncIterator, Optional
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client

from mcp_dock.core.mcp_compliance import MCPComplianceEnforcer, MCPErrorHandler
from mcp_dock.utils.logging_config import get_logger

logger = get_logger(__name__)

class ProtocolConverter(ABC):
    """Abstract base class for protocol converters"""
    
    @abstractmethod
    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a message from source to target protocol format"""
        pass
    
    @abstractmethod
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert a stream of messages from source to target protocol format"""
        pass

class StdioToStreamableHTTPConverter(ProtocolConverter):
    """Converts stdio protocol messages to StreamableHTTP format"""

    def __init__(self, server_config):
        self.server_config = server_config

    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert stdio message to StreamableHTTP format"""
        try:
            # Create stdio connection
            params = StdioServerParameters(
                command=self.server_config.command,
                args=self.server_config.args,
                env=self.server_config.env,
                cwd=self.server_config.cwd,
            )

            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    method = message.get("method")
                    params = message.get("params", {})

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for HTTP
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool)
                                   for tool in result.tools]
                        else:
                            tools = []

                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }

        except Exception as e:
            logger.error(f"Error converting stdio to StreamableHTTP: {e}")
            return MCPErrorHandler.create_error_response(
                message.get("id"),
                MCPErrorHandler.MCP_TRANSPORT_ERROR,
                f"Stdio to StreamableHTTP conversion failed: {str(e)}"
            )

    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert stdio message stream to StreamableHTTP format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            yield json.dumps(converted)

class StdioToSSEConverter(ProtocolConverter):
    """Converts stdio protocol messages to SSE format"""
    
    def __init__(self, server_config):
        self.server_config = server_config
    
    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert stdio message to SSE format"""
        try:
            # Create stdio connection
            params = StdioServerParameters(
                command=self.server_config.command,
                args=self.server_config.args,
                env=self.server_config.env,
                cwd=self.server_config.cwd,
            )
            
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    method = message.get("method")
                    params = message.get("params", {})
                    
                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for SSE
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool) 
                                   for tool in result.tools]
                        else:
                            tools = []
                        
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        
        except Exception as e:
            logger.error(f"Error converting stdio to SSE: {e}")
            return MCPErrorHandler.create_error_response(
                message.get("id"), 
                MCPErrorHandler.MCP_TRANSPORT_ERROR,
                f"Stdio to SSE conversion failed: {str(e)}"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert stdio message stream to SSE format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            yield f"data: {json.dumps(converted)}\n\n"

class SSEToStreamableHTTPConverter(ProtocolConverter):
    """Converts SSE protocol messages to StreamableHTTP format"""
    
    def __init__(self, server_config):
        self.server_config = server_config
    
    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert SSE message to StreamableHTTP format"""
        try:
            # Create SSE connection
            async with sse_client(self.server_config.url, headers=self.server_config.headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    method = message.get("method")
                    params = message.get("params", {})
                    
                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for HTTP
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool) 
                                   for tool in result.tools]
                        else:
                            tools = []
                        
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        
        except Exception as e:
            logger.error(f"Error converting SSE to StreamableHTTP: {e}")
            return MCPErrorHandler.create_error_response(
                message.get("id"), 
                MCPErrorHandler.MCP_TRANSPORT_ERROR,
                f"SSE to StreamableHTTP conversion failed: {str(e)}"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert SSE message stream to StreamableHTTP format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            yield json.dumps(converted)

class StreamableHTTPToSSEConverter(ProtocolConverter):
    """Converts StreamableHTTP protocol messages to SSE format"""
    
    def __init__(self, server_config):
        self.server_config = server_config
    
    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert StreamableHTTP message to SSE format"""
        try:
            # Create StreamableHTTP connection
            async with streamablehttp_client(self.server_config.url, headers=self.server_config.headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    method = message.get("method")
                    params = message.get("params", {})
                    
                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for SSE
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool) 
                                   for tool in result.tools]
                        else:
                            tools = []
                        
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        
        except Exception as e:
            logger.error(f"Error converting StreamableHTTP to SSE: {e}")
            return MCPErrorHandler.create_error_response(
                message.get("id"), 
                MCPErrorHandler.MCP_TRANSPORT_ERROR,
                f"StreamableHTTP to SSE conversion failed: {str(e)}"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert StreamableHTTP message stream to SSE format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            yield f"data: {json.dumps(converted)}\n\n"

class UniversalProtocolConverter:
    """Universal converter that handles all protocol conversion combinations"""
    
    def __init__(self):
        self.converters = {}
    
    def get_converter(self, source_protocol: str, target_protocol: str, server_config) -> Optional[ProtocolConverter]:
        """Get appropriate converter for source->target protocol conversion"""
        
        converter_key = f"{source_protocol}_to_{target_protocol}"
        
        if converter_key not in self.converters:
            if source_protocol == "stdio" and target_protocol == "sse":
                self.converters[converter_key] = StdioToSSEConverter(server_config)
            elif source_protocol == "stdio" and target_protocol == "streamableHTTP":
                self.converters[converter_key] = StdioToStreamableHTTPConverter(server_config)
            elif source_protocol == "sse" and target_protocol == "streamableHTTP":
                self.converters[converter_key] = SSEToStreamableHTTPConverter(server_config)
            elif source_protocol == "streamableHTTP" and target_protocol == "sse":
                self.converters[converter_key] = StreamableHTTPToSSEConverter(server_config)
            elif source_protocol == target_protocol:
                # Direct pass-through for same protocol
                self.converters[converter_key] = DirectPassThroughConverter(source_protocol, server_config)
            else:
                logger.warning(f"No converter available for {source_protocol} -> {target_protocol}")
                return None
        
        return self.converters[converter_key]
    
    async def convert_message(self, message: Dict[str, Any], source_protocol: str, target_protocol: str, server_config) -> Dict[str, Any]:
        """Convert a single message between protocols"""
        converter = self.get_converter(source_protocol, target_protocol, server_config)
        if converter:
            return await converter.convert_message(message)
        else:
            return MCPErrorHandler.create_error_response(
                message.get("id"),
                MCPErrorHandler.MCP_TRANSPORT_ERROR,
                f"Unsupported protocol conversion: {source_protocol} -> {target_protocol}"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]], source_protocol: str, target_protocol: str, server_config) -> AsyncIterator[str]:
        """Convert a message stream between protocols"""
        converter = self.get_converter(source_protocol, target_protocol, server_config)
        if converter:
            async for converted_message in converter.convert_stream(message_stream):
                yield converted_message
        else:
            error_msg = f"Unsupported protocol conversion: {source_protocol} -> {target_protocol}"
            yield f"data: {json.dumps(MCPErrorHandler.create_error_response(None, MCPErrorHandler.MCP_TRANSPORT_ERROR, error_msg))}\n\n"

class DirectPassThroughConverter(ProtocolConverter):
    """Direct pass-through converter for same-protocol conversions"""
    
    def __init__(self, protocol: str, server_config):
        self.protocol = protocol
        self.server_config = server_config
    
    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Pass message through without conversion"""
        return message
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Pass message stream through with appropriate formatting"""
        async for message in message_stream:
            if self.protocol == "sse":
                yield f"data: {json.dumps(message)}\n\n"
            else:
                yield json.dumps(message)

# Global converter instance
universal_converter = UniversalProtocolConverter()

def get_universal_converter() -> UniversalProtocolConverter:
    """Get the global universal converter instance"""
    return universal_converter
