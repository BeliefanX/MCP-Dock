"""
MCP-Dock - A Unified Management Platform for Model Context Protocol (MCP) Services
"""

import argparse
import os

from mcp_dock.utils.logging_config import setup_logging, get_logger, configure_service_logging
from mcp_dock.__version__ import get_app_info
from .api.gateway import start_api

# Check if running as a service
is_service_mode = os.getenv('MCP_DOCK_SERVICE_MODE', 'false').lower() == 'true'

if is_service_mode:
    # Configure service logging
    configure_service_logging(
        log_dir=os.getenv('MCP_DOCK_LOG_DIR', '/var/log/mcp-dock'),
        log_level=os.getenv('MCP_DOCK_LOG_LEVEL', 'INFO'),
        enable_syslog=True
    )
else:
    # Configure regular logging
    setup_logging()

logger = get_logger(__name__)


def main():
    """Main entry function"""
    app_info = get_app_info()

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description=app_info["description"],
        prog=app_info["name"]
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{app_info['name']} v{app_info['version']}"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="API service listening address",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="API service listening port",
    )
    parser.add_argument("--config", help="Configuration file path")
    args = parser.parse_args()

    logger.info(
        f"Starting {app_info['name']} v{app_info['version']}, listening at: {args.host}:{args.port}",
    )

    # Start API service
    start_api(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
