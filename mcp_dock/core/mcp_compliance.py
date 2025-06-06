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

    @staticmethod
    def validate_jsonrpc_response(response: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate JSON-RPC 2.0 response format

        Args:
            response: JSON-RPC response data

        Returns:
            tuple: (is_valid, error_message)
        """
        # Check required fields
        if "jsonrpc" not in response:
            return False, "Missing required field: jsonrpc"

        if response["jsonrpc"] != "2.0":
            return False, "jsonrpc field must be '2.0'"

        if "id" not in response:
            return False, "Missing required field: id"

        # Must have either result or error, but not both
        has_result = "result" in response
        has_error = "error" in response

        if not has_result and not has_error:
            return False, "Response must contain either 'result' or 'error'"

        if has_result and has_error:
            return False, "Response cannot contain both 'result' and 'error'"

        # Validate error structure if present
        if has_error:
            error = response["error"]
            if not isinstance(error, dict):
                return False, "Error field must be an object"

            if "code" not in error:
                return False, "Error object must contain 'code' field"

            if "message" not in error:
                return False, "Error object must contain 'message' field"

            if not isinstance(error["code"], int):
                return False, "Error code must be an integer"

            if not isinstance(error["message"], str):
                return False, "Error message must be a string"

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

        # Remove description from serverInfo if present (deprecated in v2025-03-26)
        if "description" in server_info:
            server_info.pop("description")

        # Ensure instructions field is only included if it has a non-empty value
        if "instructions" in fixed_response:
            instructions_value = fixed_response["instructions"]
            if not instructions_value or not str(instructions_value).strip():
                fixed_response.pop("instructions")

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

    @staticmethod
    def ensure_jsonrpc_response(response: Dict[str, Any], request_id: Any = None) -> Dict[str, Any]:
        """Ensure response conforms to JSON-RPC 2.0 specification

        Args:
            response: Original response data
            request_id: Request ID to use if missing

        Returns:
            Fixed JSON-RPC response
        """
        # If already a valid JSON-RPC response, validate and return
        if isinstance(response, dict) and "jsonrpc" in response:
            is_valid, error_msg = MCPComplianceValidator.validate_jsonrpc_response(response)
            if is_valid:
                return response
            else:
                logger.warning(f"Invalid JSON-RPC response detected: {error_msg}")

        # Fix or create proper JSON-RPC response
        fixed_response = {
            "jsonrpc": "2.0",
            "id": response.get("id", request_id)
        }

        # Determine if this should be a result or error response
        if isinstance(response, dict):
            if "error" in response:
                # Error response
                error = response["error"]
                if isinstance(error, dict) and "code" in error and "message" in error:
                    fixed_response["error"] = error
                else:
                    # Fix malformed error
                    fixed_response["error"] = {
                        "code": -32603,  # Internal error
                        "message": str(error) if error else "Internal error"
                    }
            else:
                # Result response - use the entire response as result if no specific result field
                if "result" in response:
                    fixed_response["result"] = response["result"]
                else:
                    # Remove jsonrpc and id from response to avoid duplication
                    result_data = {k: v for k, v in response.items() if k not in ["jsonrpc", "id"]}
                    fixed_response["result"] = result_data if result_data else response
        else:
            # Non-dict response, wrap as result
            fixed_response["result"] = response

        return fixed_response

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
