# Changelog

All notable changes to MCP-Dock will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-19

### Added
- Initial release of MCP-Dock
- Unified management platform for Model Context Protocol (MCP) services
- Support for stdio and SSE transport types
- Web-based user interface for service management
- Automatic dependency installation (Node.js/npm/npx and uv)
- Multi-language support (English and Chinese)
- RESTful API for service management
- Real-time service status monitoring
- Configuration management through JSON files
- Docker-style service containerization
- Cross-platform support (Linux, macOS, Windows)

### Features
- **Service Management**: Start, stop, and monitor MCP services
- **Protocol Conversion**: Convert between different MCP transport protocols
- **Web Interface**: Intuitive web UI for service configuration and monitoring
- **API Gateway**: RESTful API for programmatic service management
- **Auto-Installation**: Automatic detection and installation of required dependencies
- **Multi-Transport**: Support for stdio and SSE transport protocols
- **Configuration**: JSON-based service configuration
- **Logging**: Comprehensive logging and error handling
- **Internationalization**: Support for multiple languages

### Technical Details
- Built with Python 3.12+ and FastAPI
- Frontend using vanilla JavaScript with modern ES6+ features
- Package management with uv
- Dependency management for Node.js services
- Cross-platform shell scripts for service management
- Comprehensive error handling and logging

### Documentation
- Complete README with installation and usage instructions
- Chinese documentation (README_CN.md)
- API documentation
- Troubleshooting guide
- Development setup instructions

---

## Release Notes

### v0.1.0 - Initial Release

This is the first public release of MCP-Dock, providing a comprehensive solution for managing Model Context Protocol services. The platform offers both web-based and API-driven management capabilities, making it easy to deploy and manage MCP services in various environments.

**Key Highlights:**
- Zero-configuration startup with automatic dependency installation
- Support for popular MCP services out of the box
- Intuitive web interface for non-technical users
- Powerful API for developers and automation
- Cross-platform compatibility

**Getting Started:**
```bash
git clone https://github.com/BeliefanX/MCP-Dock.git
cd MCP-Dock
./start.sh
```

**Next Steps:**
- Enhanced service discovery and auto-configuration
- Plugin system for custom MCP services
- Advanced monitoring and analytics
- Container orchestration support
- Cloud deployment templates
