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


def clean_tool_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean tool arguments to handle empty strings and null values properly.

    This function addresses the issue where empty strings are passed as parameters
    but should be treated as undefined/null for certain API requirements.

    Args:
        arguments: Original tool arguments

    Returns:
        Cleaned arguments with empty strings converted to None where appropriate
    """
    if not isinstance(arguments, dict):
        return arguments

    cleaned = {}
    for key, value in arguments.items():
        # Handle empty strings that should be treated as undefined
        if isinstance(value, str) and value.strip() == "":
            # For cursor-related parameters, empty strings should be None
            if "cursor" in key.lower() or key.lower() in ["start_cursor", "end_cursor", "next_cursor"]:
                # Don't include the parameter at all if it's empty
                continue
            else:
                cleaned[key] = value
        elif isinstance(value, dict):
            # Recursively clean nested dictionaries
            cleaned[key] = clean_tool_arguments(value)
        else:
            cleaned[key] = value

    return cleaned

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

                    # Clean tool arguments for tools/call method
                    if method == "tools/call" and "arguments" in params:
                        params["arguments"] = clean_tool_arguments(params["arguments"])

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for HTTP
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool)
                                   for tool in result.tools]
                        else:
                            tools = []

                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))

        except Exception as e:
            logger.error(f"Error converting stdio to StreamableHTTP: {e}")
            return MCPErrorHandler.handle_conversion_error(
                e,
                "Stdio to StreamableHTTP conversion",
                message.get("id"),
                "stdio",
                "streamableHTTP"
            )

    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert stdio message stream to StreamableHTTP format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            # Ensure proper JSON serialization without double encoding
            if isinstance(converted, str):
                yield converted
            else:
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

                    # Clean tool arguments for tools/call method
                    if method == "tools/call" and "arguments" in params:
                        params["arguments"] = clean_tool_arguments(params["arguments"])

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for SSE
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool) 
                                   for tool in result.tools]
                        else:
                            tools = []
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                        
        except Exception as e:
            logger.error(f"Error converting stdio to SSE: {e}")
            return MCPErrorHandler.handle_conversion_error(
                e,
                "Stdio to SSE conversion",
                message.get("id"),
                "stdio",
                "sse"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert stdio message stream to SSE format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            # Ensure proper JSON serialization without double encoding
            if isinstance(converted, str):
                # If already a JSON string, don't double-encode
                try:
                    # Validate it's proper JSON
                    json.loads(converted)
                    yield f"data: {converted}\n\n"
                except json.JSONDecodeError:
                    # If not valid JSON, encode it
                    yield f"data: {json.dumps(converted)}\n\n"
            else:
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

                    # Clean tool arguments for tools/call method
                    if method == "tools/call" and "arguments" in params:
                        params["arguments"] = clean_tool_arguments(params["arguments"])

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for HTTP
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool) 
                                   for tool in result.tools]
                        else:
                            tools = []
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                        
        except Exception as e:
            logger.error(f"Error converting SSE to StreamableHTTP: {e}")
            return MCPErrorHandler.handle_conversion_error(
                e,
                "SSE to StreamableHTTP conversion",
                message.get("id"),
                "sse",
                "streamableHTTP"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert SSE message stream to StreamableHTTP format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            # Ensure proper JSON serialization without double encoding
            if isinstance(converted, str):
                yield converted
            else:
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

                    # Clean tool arguments for tools/call method
                    if method == "tools/call" and "arguments" in params:
                        params["arguments"] = clean_tool_arguments(params["arguments"])

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for SSE
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool) 
                                   for tool in result.tools]
                        else:
                            tools = []
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                        
        except Exception as e:
            logger.error(f"Error converting StreamableHTTP to SSE: {e}")
            return MCPErrorHandler.handle_conversion_error(
                e,
                "StreamableHTTP to SSE conversion",
                message.get("id"),
                "streamableHTTP",
                "sse"
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert StreamableHTTP message stream to SSE format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            # Ensure proper JSON serialization without double encoding
            if isinstance(converted, str):
                # If already a JSON string, don't double-encode
                try:
                    # Validate it's proper JSON
                    json.loads(converted)
                    yield f"data: {converted}\n\n"
                except json.JSONDecodeError:
                    # If not valid JSON, encode it
                    yield f"data: {json.dumps(converted)}\n\n"
            else:
                yield f"data: {json.dumps(converted)}\n\n"

class SSEToStdioConverter(ProtocolConverter):
    """Converts SSE protocol messages to stdio format"""

    def __init__(self, server_config):
        self.server_config = server_config

    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert SSE message to stdio format"""
        try:
            # Create SSE connection
            async with sse_client(self.server_config.url, headers=self.server_config.headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    method = message.get("method")
                    params = message.get("params", {})

                    # Clean tool arguments for tools/call method
                    if method == "tools/call" and "arguments" in params:
                        params["arguments"] = clean_tool_arguments(params["arguments"])

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for stdio
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool)
                                   for tool in result.tools]
                        else:
                            tools = []

                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))

        except Exception as e:
            logger.error(f"Error converting SSE to stdio: {e}")
            return MCPErrorHandler.handle_conversion_error(
                e,
                "SSE to stdio conversion",
                message.get("id"),
                "sse",
                "stdio"
            )

    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert SSE message stream to stdio format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            # Ensure proper JSON serialization without double encoding
            if isinstance(converted, str):
                yield converted
            else:
                yield json.dumps(converted)

class StreamableHTTPToStdioConverter(ProtocolConverter):
    """Converts StreamableHTTP protocol messages to stdio format"""

    def __init__(self, server_config):
        self.server_config = server_config

    async def convert_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert StreamableHTTP message to stdio format"""
        try:
            # Create StreamableHTTP connection
            async with streamablehttp_client(self.server_config.url, headers=self.server_config.headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    method = message.get("method")
                    params = message.get("params", {})

                    # Clean tool arguments for tools/call method
                    if method == "tools/call" and "arguments" in params:
                        params["arguments"] = clean_tool_arguments(params["arguments"])

                    if method == "tools/list":
                        result = await session.list_tools()
                        # Convert to dict format for stdio
                        if hasattr(result, 'tools'):
                            tools = [MCPComplianceEnforcer.fix_tool_definition(tool.__dict__ if hasattr(tool, '__dict__') else tool)
                                   for tool in result.tools]
                        else:
                            tools = []

                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {"tools": tools}
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))
                    else:
                        # Generic method call
                        result = await session.send_request(method, params)
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": result
                        }
                        return MCPComplianceEnforcer.ensure_jsonrpc_response(response, message.get("id"))

        except Exception as e:
            logger.error(f"Error converting StreamableHTTP to stdio: {e}")
            return MCPErrorHandler.handle_conversion_error(
                e,
                "StreamableHTTP to stdio conversion",
                message.get("id"),
                "streamableHTTP",
                "stdio"
            )

    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
        """Convert StreamableHTTP message stream to stdio format"""
        async for message in message_stream:
            converted = await self.convert_message(message)
            # Ensure proper JSON serialization without double encoding
            if isinstance(converted, str):
                yield converted
            else:
                yield json.dumps(converted)

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
            elif source_protocol == "sse" and target_protocol == "stdio":
                self.converters[converter_key] = SSEToStdioConverter(server_config)
            elif source_protocol == "sse" and target_protocol == "streamableHTTP":
                self.converters[converter_key] = SSEToStreamableHTTPConverter(server_config)
            elif source_protocol == "streamableHTTP" and target_protocol == "stdio":
                self.converters[converter_key] = StreamableHTTPToStdioConverter(server_config)
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
            return MCPErrorHandler.handle_conversion_error(
                ValueError(f"Unsupported protocol conversion: {source_protocol} -> {target_protocol}"),
                "Protocol conversion not supported",
                message.get("id"),
                source_protocol,
                target_protocol
            )
    
    async def convert_stream(self, message_stream: AsyncIterator[Dict[str, Any]], source_protocol: str, target_protocol: str, server_config) -> AsyncIterator[str]:
        """Convert a message stream between protocols"""
        converter = self.get_converter(source_protocol, target_protocol, server_config)
        if converter:
            async for converted_message in converter.convert_stream(message_stream):
                yield converted_message
        else:
            error_response = MCPErrorHandler.handle_conversion_error(
                ValueError(f"Unsupported protocol conversion: {source_protocol} -> {target_protocol}"),
                "Protocol conversion not supported",
                None,
                source_protocol,
                target_protocol
            )
            if target_protocol == "sse":
                yield f"data: {json.dumps(error_response)}\n\n"
            else:
                yield json.dumps(error_response)

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
                # Ensure proper JSON serialization without double encoding
                if isinstance(message, str):
                    # If already a JSON string, don't double-encode
                    try:
                        # Validate it's proper JSON
                        json.loads(message)
                        yield f"data: {message}\n\n"
                    except json.JSONDecodeError:
                        # If not valid JSON, encode it
                        yield f"data: {json.dumps(message)}\n\n"
                else:
                    yield f"data: {json.dumps(message)}\n\n"
            else:
                # Ensure proper JSON serialization without double encoding
                if isinstance(message, str):
                    yield message
                else:
                    yield json.dumps(message)

# Global converter instance
universal_converter = UniversalProtocolConverter()

def get_universal_converter() -> UniversalProtocolConverter:
    """Get the global universal converter instance"""
    return universal_converter
