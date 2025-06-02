"""Centralized logging configuration for MCP-Dock."""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


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
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
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