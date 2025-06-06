"""
MCP Compliance Module - Ensures strict compliance with MCP 2025-03-26 specification
"""

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

from mcp_dock.utils.logging_config import get_logger

logger = get_logger(__name__)

# MCP 2025-03-26 Protocol Version
MCP_PROTOCOL_VERSION = "2025-03-26"

@dataclass
class MCPCapabilities:
    """MCP Capabilities structure according to 2025-03-26 specification"""
    
    # Server capabilities
    logging: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    tools: Optional[Dict[str, Any]] = None
    experimental: Optional[Dict[str, Any]] = None
    
    # Client capabilities
    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Ensure default values for required fields"""
        if self.logging is None:
            self.logging = {}

@dataclass
class MCPServerInfo:
    """MCP Server Info structure according to 2025-03-26 specification"""
    
    name: str
    version: str
    instructions: Optional[str] = None
    description: Optional[str] = None

@dataclass
class MCPInitializationResult:
    """Complete MCP Initialization Result according to 2025-03-26 specification"""
    
    protocolVersion: str = MCP_PROTOCOL_VERSION
    capabilities: MCPCapabilities = field(default_factory=MCPCapabilities)
    serverInfo: MCPServerInfo = field(default_factory=lambda: MCPServerInfo(name="", version=""))
    instructions: Optional[str] = None

class MCPComplianceValidator:
    """Validates MCP messages for compliance with 2025-03-26 specification"""
    
    @staticmethod
    def validate_initialization_request(request: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate MCP initialization request
        
        Args:
            request: Initialization request data
            
        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = ["protocolVersion", "capabilities", "clientInfo"]
        
        for field in required_fields:
            if field not in request:
                return False, f"Missing required field: {field}"
        
        # Validate protocol version
        protocol_version = request.get("protocolVersion")
        if not isinstance(protocol_version, str):
            return False, "protocolVersion must be a string"
        
        # Validate capabilities
        capabilities = request.get("capabilities")
        if not isinstance(capabilities, dict):
            return False, "capabilities must be an object"
        
        # Validate clientInfo
        client_info = request.get("clientInfo")
        if not isinstance(client_info, dict):
            return False, "clientInfo must be an object"
        
        if "name" not in client_info:
            return False, "clientInfo must contain 'name' field"
        
        return True, None
    
    @staticmethod
    def validate_initialization_response(response: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate MCP initialization response
        
        Args:
            response: Initialization response data
            
        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = ["protocolVersion", "capabilities", "serverInfo"]
        
        for field in required_fields:
            if field not in response:
                return False, f"Missing required field: {field}"
        
        # Validate protocol version
        protocol_version = response.get("protocolVersion")
        if not isinstance(protocol_version, str):
            return False, "protocolVersion must be a string"
        
        # Validate capabilities
        capabilities = response.get("capabilities")
        if not isinstance(capabilities, dict):
            return False, "capabilities must be an object"
        
        # Validate serverInfo
        server_info = response.get("serverInfo")
        if not isinstance(server_info, dict):
            return False, "serverInfo must be an object"
        
        if "name" not in server_info:
            return False, "serverInfo must contain 'name' field"
        
        if "version" not in server_info:
            return False, "serverInfo must contain 'version' field"
        
        return True, None
    
    @staticmethod
    def validate_tool_definition(tool: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate MCP tool definition
        
        Args:
            tool: Tool definition data
            
        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = ["name", "description", "inputSchema"]
        
        for field in required_fields:
            if field not in tool:
                return False, f"Missing required field: {field}"
        
        # Validate name
        if not isinstance(tool["name"], str) or not tool["name"].strip():
            return False, "Tool name must be a non-empty string"
        
        # Validate description
        if not isinstance(tool["description"], str):
            return False, "Tool description must be a string"
        
        # Validate inputSchema
        input_schema = tool["inputSchema"]
        if not isinstance(input_schema, dict):
            return False, "Tool inputSchema must be an object"
        
        if "type" not in input_schema:
            return False, "Tool inputSchema must contain 'type' field"
        
        return True, None

class MCPComplianceEnforcer:
    """Enforces MCP compliance by fixing common issues"""
    
    @staticmethod
    def fix_initialization_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Fix initialization response to ensure MCP 2025-03-26 compliance
        
        Args:
            response: Original initialization response
            
        Returns:
            Fixed initialization response
        """
        fixed_response = response.copy()
        
        # Ensure protocol version
        if "protocolVersion" not in fixed_response:
            fixed_response["protocolVersion"] = MCP_PROTOCOL_VERSION
        
        # Ensure capabilities
        if "capabilities" not in fixed_response:
            fixed_response["capabilities"] = {}
        
        capabilities = fixed_response["capabilities"]
        
        # Ensure logging capability is an object, not null
        if capabilities.get("logging") is None:
            capabilities["logging"] = {}
        
        # Ensure tools capability has proper structure
        if "tools" in capabilities and capabilities["tools"] is not None:
            if not isinstance(capabilities["tools"], dict):
                capabilities["tools"] = {}
            if capabilities["tools"].get("listChanged") is None:
                capabilities["tools"]["listChanged"] = True
        
        # Ensure resources capability has proper structure
        if "resources" in capabilities and capabilities["resources"] is not None:
            if not isinstance(capabilities["resources"], dict):
                capabilities["resources"] = {"subscribe": False, "listChanged": False}
            else:
                if "subscribe" not in capabilities["resources"]:
                    capabilities["resources"]["subscribe"] = False
                if "listChanged" not in capabilities["resources"]:
                    capabilities["resources"]["listChanged"] = False
        
        # Ensure serverInfo
        if "serverInfo" not in fixed_response:
            fixed_response["serverInfo"] = {"name": "Unknown", "version": "1.0.0"}
        
        server_info = fixed_response["serverInfo"]
        
        # Ensure required serverInfo fields
        if "name" not in server_info:
            server_info["name"] = "Unknown"
        if "version" not in server_info:
            server_info["version"] = "1.0.0"
        
        # Remove instructions from serverInfo if present (MCP v2025-03-26 compliance)
        # Instructions should be a top-level field, not in serverInfo
        if "instructions" in server_info:
            instructions_value = server_info.pop("instructions")
            # Move instructions to top-level if it has a valid value
            if instructions_value and str(instructions_value).strip():
                fixed_response["instructions"] = str(instructions_value).strip()
        
        return fixed_response
    
    @staticmethod
    def fix_tool_definition(tool: Dict[str, Any]) -> Dict[str, Any]:
        """Fix tool definition to ensure MCP compliance
        
        Args:
            tool: Original tool definition
            
        Returns:
            Fixed tool definition
        """
        fixed_tool = tool.copy()
        
        # Ensure required fields
        if "name" not in fixed_tool:
            fixed_tool["name"] = f"Tool-{id(tool)}"
        
        if "description" not in fixed_tool:
            fixed_tool["description"] = "No description provided"
        
        if "inputSchema" not in fixed_tool:
            fixed_tool["inputSchema"] = {"type": "object", "properties": {}}
        
        # Ensure inputSchema has proper structure
        input_schema = fixed_tool["inputSchema"]
        if not isinstance(input_schema, dict):
            fixed_tool["inputSchema"] = {"type": "object", "properties": {}}
        elif "type" not in input_schema:
            input_schema["type"] = "object"
            if "properties" not in input_schema:
                input_schema["properties"] = {}
        
        return fixed_tool

class MCPErrorHandler:
    """Handles MCP-specific errors according to JSON-RPC 2.0 and MCP specifications"""
    
    # Standard JSON-RPC error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific error codes (server error range)
    MCP_PROTOCOL_ERROR = -32000
    MCP_TRANSPORT_ERROR = -32001
    MCP_CAPABILITY_ERROR = -32002
    MCP_RESOURCE_ERROR = -32003
    MCP_TOOL_ERROR = -32004
    
    @staticmethod
    def create_error_response(request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
        """Create a standard JSON-RPC error response
        
        Args:
            request_id: Request ID from original request
            code: Error code
            message: Error message
            data: Optional additional error data
            
        Returns:
            JSON-RPC error response
        """
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        if data is not None:
            error_response["error"]["data"] = data
        
        return error_response
    
    @staticmethod
    def create_mcp_error_response(request_id: Any, error_type: str, message: str, details: Any = None) -> Dict[str, Any]:
        """Create an MCP-specific error response
        
        Args:
            request_id: Request ID from original request
            error_type: Type of MCP error
            message: Error message
            details: Optional error details
            
        Returns:
            MCP error response
        """
        error_codes = {
            "protocol": MCPErrorHandler.MCP_PROTOCOL_ERROR,
            "transport": MCPErrorHandler.MCP_TRANSPORT_ERROR,
            "capability": MCPErrorHandler.MCP_CAPABILITY_ERROR,
            "resource": MCPErrorHandler.MCP_RESOURCE_ERROR,
            "tool": MCPErrorHandler.MCP_TOOL_ERROR,
        }
        
        code = error_codes.get(error_type, MCPErrorHandler.INTERNAL_ERROR)
        
        return MCPErrorHandler.create_error_response(request_id, code, message, details)
