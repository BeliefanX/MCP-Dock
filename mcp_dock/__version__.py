"""
MCP-Dock Version Information
"""

__version__ = "0.1.0"
__version_info__ = (0, 1, 0)

# Application metadata
APP_NAME = "MCP-Dock"
APP_DESCRIPTION = "A Unified Management Platform for Model Context Protocol (MCP) Services"
APP_AUTHOR = "MCP-Dock Team"
APP_LICENSE = "GPL v3"
APP_URL = "https://github.com/BeliefanX/MCP-Dock"

def get_version() -> str:
    """Get the current version string."""
    return __version__

def get_version_info() -> tuple[int, int, int]:
    """Get the current version as a tuple."""
    return __version_info

def get_app_info() -> dict[str, str]:
    """Get application information."""
    return {
        "name": APP_NAME,
        "version": __version__,
        "description": APP_DESCRIPTION,
        "author": APP_AUTHOR,
        "license": APP_LICENSE,
        "url": APP_URL,
    }
