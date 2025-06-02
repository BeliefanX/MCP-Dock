#!/usr/bin/env python3
"""
MCP Unified Management Tool Startup Script
"""
import os
import sys
import time
import uvicorn
import argparse
import traceback

from mcp_dock.utils.logging_config import setup_logging, get_logger

# Configure logging with file output
setup_logging(log_file="mcp_dock.log")
logger = get_logger("mcp_dock")

def main():
    """Main function: Start the MCP-Dock"""
    parser = argparse.ArgumentParser(description="MCP-Dock")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to listen on")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    
    args = parser.parse_args()
    
    # Configure logging级别
    log_level = "DEBUG" if args.debug else "INFO"
    
    logger.info("Starting MCP-Dock...")
    logger.info(f"Host: {args.host}, Port: {args.port}, Debug mode: {'Enabled' if args.debug else 'Disabled'}")
    
    # Add current directory to Python path to ensure correct module import
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Record start time
        start_time = time.time()
        
        # Start server using uv run
        import subprocess
        
        # Use uv run to start the server
        cmd = [
            "uv", "run", "uvicorn", "mcp_dock.api.gateway:app",
            "--host", args.host,
            "--port", str(args.port),
            "--log-level", log_level.lower()
        ]
        
        if not args.no_reload:
            cmd.append("--reload")
            
        logger.info(f"Executing command: {' '.join(cmd)}")
        
        # Execute the command
        result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
        sys.exit(result.returncode)
        
        # Fallback to direct uvicorn.run if uv is not available
        # uvicorn.run(
        #     "mcp_dock.api.gateway:app", 
        #     host=args.host, 
        #     port=args.port,
        #     reload=not args.no_reload,
        #     log_level=log_level.lower()
        # )
    except KeyboardInterrupt:
        logger.info("Received termination signal, gracefully shutting down...")
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        logger.critical(traceback.format_exc())
        sys.exit(1)
