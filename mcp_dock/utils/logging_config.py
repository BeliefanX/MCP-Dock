"""Centralized logging configuration for MCP-Dock."""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any


class MCPLogFormatter(logging.Formatter):
    """Enhanced formatter for MCP-Dock with structured logging support"""

    def __init__(self, include_mcp_fields: bool = True):
        self.include_mcp_fields = include_mcp_fields
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        # Base format
        base_format = '%(asctime)s - %(name)s - %(levelname)s'

        # Add MCP-specific fields if available
        mcp_fields = []
        if self.include_mcp_fields:
            if hasattr(record, 'protocol_version'):
                mcp_fields.append(f"protocol={record.protocol_version}")
            if hasattr(record, 'request_id'):
                mcp_fields.append(f"req_id={record.request_id}")
            if hasattr(record, 'method'):
                mcp_fields.append(f"method={record.method}")
            if hasattr(record, 'duration_ms'):
                mcp_fields.append(f"duration={record.duration_ms}ms")
            if hasattr(record, 'error_code'):
                mcp_fields.append(f"error_code={record.error_code}")

        # Construct format string
        if mcp_fields:
            format_str = f"{base_format} [{' | '.join(mcp_fields)}] - %(message)s"
        else:
            format_str = f"{base_format} - %(message)s"

        # Apply format
        formatter = logging.Formatter(format_str)
        return formatter.format(record)


def setup_logging(
    level: Optional[int] = None,
    log_file: str = "mcp_dock.log",
    force_reconfigure: bool = False
) -> None:
    """Setup centralized logging configuration.
    
    Args:
        level: Logging level (defaults to INFO or env var MCP_DOCK_LOG_LEVEL)
        log_file: Log file path
        force_reconfigure: Force reconfiguration even if already configured
    """
    # Check if logging is already configured
    root_logger = logging.getLogger()
    if root_logger.handlers and not force_reconfigure:
        return
    
    # Clear existing handlers if force reconfiguring
    if force_reconfigure:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # Determine log level
    if level is None:
        log_level_str = os.getenv('MCP_DOCK_LOG_LEVEL', 'INFO').upper()
        level = getattr(logging, log_level_str, logging.INFO)
    
    # Create enhanced formatter
    formatter = MCPLogFormatter(include_mcp_fields=True)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # File handler
    try:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setFormatter(formatter)
        file_handlers = [file_handler]
    except (OSError, PermissionError):
        # If file logging fails, continue with console only
        file_handlers = []
    
    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    for handler in file_handlers:
        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    # Ensure logging is configured
    setup_logging()
    return logging.getLogger(name)


def log_mcp_request(logger: logging.Logger, level: int, message: str,
                   request_id: Optional[str] = None, method: Optional[str] = None,
                   protocol_version: str = "2025-03-26", **kwargs) -> None:
    """Log an MCP request with structured fields

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        request_id: MCP request ID
        method: MCP method name
        protocol_version: MCP protocol version
        **kwargs: Additional fields
    """
    extra = {
        'protocol_version': protocol_version,
        'request_id': request_id,
        'method': method,
        **kwargs
    }
    # Remove None values
    extra = {k: v for k, v in extra.items() if v is not None}
    logger.log(level, message, extra=extra)


def log_mcp_error(logger: logging.Logger, message: str, error: Exception,
                 request_id: Optional[str] = None, method: Optional[str] = None,
                 error_code: Optional[int] = None, **kwargs) -> None:
    """Log an MCP error with structured fields

    Args:
        logger: Logger instance
        message: Log message
        error: Exception that occurred
        request_id: MCP request ID
        method: MCP method name
        error_code: MCP error code
        **kwargs: Additional fields
    """
    extra = {
        'request_id': request_id,
        'method': method,
        'error_code': error_code,
        'error_type': type(error).__name__,
        **kwargs
    }
    # Remove None values
    extra = {k: v for k, v in extra.items() if v is not None}
    logger.error(f"{message}: {str(error)}", extra=extra)


def log_performance(logger: logging.Logger, message: str, duration_ms: float,
                   request_id: Optional[str] = None, method: Optional[str] = None,
                   **kwargs) -> None:
    """Log performance metrics with structured fields

    Args:
        logger: Logger instance
        message: Log message
        duration_ms: Duration in milliseconds
        request_id: MCP request ID
        method: MCP method name
        **kwargs: Additional fields
    """
    extra = {
        'duration_ms': round(duration_ms, 2),
        'request_id': request_id,
        'method': method,
        **kwargs
    }
    # Remove None values
    extra = {k: v for k, v in extra.items() if v is not None}
    logger.info(message, extra=extra)


class PerformanceTimer:
    """Context manager for measuring performance"""

    def __init__(self, logger: logging.Logger, operation: str,
                 request_id: Optional[str] = None, method: Optional[str] = None):
        self.logger = logger
        self.operation = operation
        self.request_id = request_id
        self.method = method
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration_ms = (time.time() - self.start_time) * 1000
            log_performance(
                self.logger,
                f"{self.operation} completed",
                duration_ms,
                self.request_id,
                self.method
            )