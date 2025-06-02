"""
MCP Unified Management Tool - Main Entry
"""

import argparse
import sys

from mcp_dock.utils.logging_config import setup_logging, get_logger
from .api.gateway import start_api

# Configure logging (globally unique)
setup_logging()
logger = get_logger(__name__)


def main():
    """Main entry function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="MCP Unified Management Tool")
    parser.add_argument(
        "--host", default="0.0.0.0", help="API service listening address",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="API service listening port",
    )
    parser.add_argument("--config", help="Configuration file path")
    args = parser.parse_args()

    logger.info(
        f"Starting MCP Unified Management Tool, listening at: {args.host}:{args.port}",
    )

    # Start API service
    start_api(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
