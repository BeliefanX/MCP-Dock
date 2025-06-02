"""
MCP-Dock API Routing Package
"""

# Add debug information
print("========================")
print("routes package __init__.py imported")
print("========================")

# Import all route modules to ensure they can be automatically discovered by FastAPI
from . import proxy

# Add more debug information
print("========================")
print(f"proxy module imported successfully: {proxy}")
print(f"proxy.router object: {proxy.router}")
print("========================")
