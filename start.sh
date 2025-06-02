#!/bin/bash
# MCP-Dock Startup Script
# This script checks if there are already processes running or if the port is in use
# If so, it will terminate these processes, then start the application using uv
# It also automatically installs required dependencies (Node.js/npm/npx and uv)

# Define colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Define port
PORT=8000

# Log functions
log_info() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log_debug() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Add to PATH and shell profile
add_to_path() {
    local new_path="$1"
    local shell_profile=""

    # Determine shell profile file
    if [[ -n "$ZSH_VERSION" ]]; then
        shell_profile="$HOME/.zshrc"
    elif [[ -n "$BASH_VERSION" ]]; then
        shell_profile="$HOME/.bashrc"
    else
        # Default to .bashrc
        shell_profile="$HOME/.bashrc"
    fi

    # Add to current session
    export PATH="$new_path:$PATH"

    # Add to shell profile if not already present
    if [[ -f "$shell_profile" ]] && ! grep -q "$new_path" "$shell_profile"; then
        echo "export PATH=\"$new_path:\$PATH\"" >> "$shell_profile"
        log_info "Added $new_path to $shell_profile"
    fi
}

# Check and install Node.js/npm/npx
check_and_install_nodejs() {
    log_debug "Checking Node.js installation..."

    if command -v node &> /dev/null && command -v npm &> /dev/null && command -v npx &> /dev/null; then
        local node_version=$(node --version 2>/dev/null)
        local npm_version=$(npm --version 2>/dev/null)
        log_debug "Node.js is installed: $node_version, npm: $npm_version"
        return 0
    fi

    log_warn "Node.js/npm/npx not found. Installing Node.js..."

    local os=$(detect_os)
    local install_success=false

    case "$os" in
        "linux")
            # Try different installation methods for Linux
            if command -v curl &> /dev/null; then
                log_info "Installing Node.js using NodeSource repository..."
                curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && \
                sudo apt-get install -y nodejs && install_success=true
            elif command -v wget &> /dev/null; then
                log_info "Installing Node.js using NodeSource repository (wget)..."
                wget -qO- https://deb.nodesource.com/setup_lts.x | sudo -E bash - && \
                sudo apt-get install -y nodejs && install_success=true
            fi

            # Fallback: try package manager
            if [[ "$install_success" == false ]]; then
                if command -v apt-get &> /dev/null; then
                    log_info "Trying to install Node.js via apt-get..."
                    sudo apt-get update && sudo apt-get install -y nodejs npm && install_success=true
                elif command -v yum &> /dev/null; then
                    log_info "Trying to install Node.js via yum..."
                    sudo yum install -y nodejs npm && install_success=true
                elif command -v dnf &> /dev/null; then
                    log_info "Trying to install Node.js via dnf..."
                    sudo dnf install -y nodejs npm && install_success=true
                fi
            fi
            ;;
        "macos")
            if command -v brew &> /dev/null; then
                log_info "Installing Node.js using Homebrew..."
                brew install node && install_success=true
            else
                log_warn "Homebrew not found. Please install Homebrew first or install Node.js manually."
                log_info "Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                log_info "Or download Node.js from: https://nodejs.org/"
            fi
            ;;
        *)
            log_warn "Unsupported operating system for automatic Node.js installation."
            log_info "Please install Node.js manually from: https://nodejs.org/"
            ;;
    esac

    if [[ "$install_success" == true ]]; then
        # Refresh PATH and verify installation
        hash -r
        if command -v node &> /dev/null && command -v npm &> /dev/null; then
            local node_version=$(node --version 2>/dev/null)
            local npm_version=$(npm --version 2>/dev/null)
            log_info "Node.js installation successful: $node_version, npm: $npm_version"

            # Ensure npx is available (usually comes with npm 5.2+)
            if ! command -v npx &> /dev/null; then
                log_warn "npx not found, installing..."
                npm install -g npx
            fi
            return 0
        else
            log_error "Node.js installation failed. Please install manually."
            return 1
        fi
    else
        log_error "Failed to install Node.js automatically."
        log_info "Please install Node.js manually:"
        log_info "  - Download from: https://nodejs.org/"
        log_info "  - Or use your system's package manager"
        return 1
    fi
}

# Enhanced uv installation with better error handling
check_and_install_uv() {
    log_debug "Checking uv installation..."

    if command -v uv &> /dev/null; then
        local uv_version=$(uv --version 2>/dev/null | head -n 1)
        log_debug "uv is installed: $uv_version"
        return 0
    fi

    log_warn "uv not found. Installing uv..."

    # Try official installation script
    if command -v curl &> /dev/null; then
        log_info "Installing uv using official installer..."
        if curl -LsSf https://astral.sh/uv/install.sh | sh; then
            # Add uv to PATH
            local uv_bin_path="$HOME/.cargo/bin"
            if [[ -d "$uv_bin_path" ]]; then
                add_to_path "$uv_bin_path"
            fi

            # Refresh PATH and verify installation
            hash -r
            if command -v uv &> /dev/null; then
                local uv_version=$(uv --version 2>/dev/null | head -n 1)
                log_info "uv installation successful: $uv_version"
                return 0
            fi
        fi
    fi

    # Fallback: try pip installation
    if command -v pip &> /dev/null || command -v pip3 &> /dev/null; then
        log_info "Trying to install uv via pip..."
        local pip_cmd="pip"
        if command -v pip3 &> /dev/null; then
            pip_cmd="pip3"
        fi

        if $pip_cmd install uv; then
            hash -r
            if command -v uv &> /dev/null; then
                local uv_version=$(uv --version 2>/dev/null | head -n 1)
                log_info "uv installation successful via pip: $uv_version"
                return 0
            fi
        fi
    fi

    log_error "Failed to install uv automatically."
    log_info "Please install uv manually:"
    log_info "  - Official installer: curl -LsSf https://astral.sh/uv/install.sh | sh"
    log_info "  - Via pip: pip install uv"
    log_info "  - Via pipx: pipx install uv"
    return 1
}

# Check if required commands are available
check_required_commands() {
    local missing_commands=()

    for cmd in lsof kill pgrep; do
        if ! command -v $cmd &> /dev/null; then
            missing_commands+=($cmd)
        fi
    done

    if [ ${#missing_commands[@]} -ne 0 ]; then
        log_error "Error: The following system commands are not installed: ${missing_commands[*]}"
        log_info "Please install these commands using your system's package manager."
        exit 1
    fi
}



# Check and terminate existing MCP processes
check_existing_processes() {
    log_warn "Checking existing processes..."
    PYTHON_PIDS=$(pgrep -f "python.*run.py|uvicorn.*mcp_dock")

    if [ ! -z "$PYTHON_PIDS" ]; then
        log_warn "Found MCP-Dock Python processes running, Process IDs: $PYTHON_PIDS"
        log_warn "Terminating these processes..."
        
        # 终止进程
        for PID in $PYTHON_PIDS; do
            echo -e "  Terminating process PID: $PID"
            kill -15 $PID 2>/dev/null
            
            # 等待进程结束
            sleep 0.5
            
            # 检查进程是否仍然存在
            if kill -0 $PID 2>/dev/null; then
                log_warn "  Process $PID could not be gracefully terminated, forcing termination..."
                kill -9 $PID 2>/dev/null
            fi
        done
        
        # 短暂延迟确保进程完全终止
        sleep 1
        
        # 再次检查进程是否存在
        REMAINING_PIDS=$(pgrep -f "python.*run.py|uvicorn.*mcp_dock")
        if [ ! -z "$REMAINING_PIDS" ]; then
            log_error "Unable to terminate all processes, remaining processes: $REMAINING_PIDS"
            exit 1
        fi
        
        log_info "Previous processes have been terminated"
    else
        log_info "No MCP-Dock Python processes found"
    fi
}

# Check and release port
check_port() {
    log_warn "Checking if port $PORT is in use..."
    if lsof -i :$PORT -t &> /dev/null; then
        PORT_PID=$(lsof -i :$PORT -t)
        PORT_PROCESS=$(ps -p $PORT_PID -o comm= 2>/dev/null || echo "Unknown process")
        log_warn "Port $PORT is in use by process ID: $PORT_PID ($PORT_PROCESS)"
        log_warn "Terminating the process using the port..."
        
        # Attempt to terminate process gracefully
        kill -15 $PORT_PID 2>/dev/null
        
        # Wait for a short period
        # 等待一小段时间
        sleep 1
        
        # 检查端口是否仍被占用
        if lsof -i :$PORT -t &> /dev/null; then
            log_warn "Graceful termination failed, attempting forced termination..."
            kill -9 $PORT_PID 2>/dev/null
            sleep 1
        fi
        
        # 最终检查
        if lsof -i :$PORT -t &> /dev/null; then
            log_error "Unable to release port $PORT, please manually terminate the process or change the port"
            exit 1
        fi
        
        log_info "Process using the port has been terminated"
    else
        log_info "Port $PORT is not in use"
    fi
}

# Check and create virtual environment with Python version from .python-version
setup_virtualenv() {
    log_warn "Checking Python virtual environment..."
    PYTHON_VERSION=$(cat .python-version 2>/dev/null || echo "3.12.2")
    if [ ! -d ".venv" ]; then
        log_warn "Virtual environment does not exist, creating with Python ${PYTHON_VERSION}..."
        if ! uv venv .venv --python "${PYTHON_VERSION}"; then
            log_error "Failed to create virtual environment with Python ${PYTHON_VERSION}"
            log_error "Please ensure Python ${PYTHON_VERSION} is installed or run: uv python install ${PYTHON_VERSION}"
            exit 1
        fi
        log_info "Virtual environment created successfully with Python ${PYTHON_VERSION}"
    else
        log_info "Virtual environment already exists"
    fi
}

# Install dependencies using uv sync
install_dependencies() {
    log_warn "Installing/updating dependencies..."
    
    # Use uv sync to install dependencies from pyproject.toml
    uv sync
    
    if [ $? -ne 0 ]; then
        log_error "Failed to install dependencies, please check pyproject.toml file and network connection"
        exit 1
    fi
    
    log_info "Dependencies installation completed"
}

# Check environment variables
check_environment_variables() {
    log_debug "Checking environment variables..."
    
    # 通用环境变量检查 - 只检查文件是否存在且可读
    if [ -f "mcp.config.json" ]; then
        log_debug "Configuration file found: mcp.config.json"
    else
        log_warn "Warning: mcp.config.json configuration file not found"
    fi
    
    # 检查.env文件
    if [ -f ".env" ]; then
        log_debug "Found .env file, environment variables will be loaded automatically"
    fi
}

# Main function
main() {
    log_info "Preparing to start MCP-Dock..."

    # Perform dependency checks and installations
    log_info "Checking and installing required dependencies..."
    check_required_commands

    # Check and install Node.js/npm/npx (required for stdio MCP services)
    if ! check_and_install_nodejs; then
        log_warn "Node.js installation failed. Some MCP services may not work."
        log_warn "You can continue, but stdio-based MCP services using npx will fail."
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Installation aborted by user."
            exit 1
        fi
    fi

    # Check and install uv (required for Python package management)
    if ! check_and_install_uv; then
        log_error "uv installation failed. Cannot continue without uv."
        exit 1
    fi

    # Continue with other checks
    check_existing_processes
    check_port
    check_environment_variables
    setup_virtualenv
    install_dependencies

    # Set Python path to ensure modules can be found correctly
    export PYTHONPATH="$PYTHONPATH:$(pwd)"

    # Start application
    log_info "Starting MCP-Dock..."

    # Use uv run to start the application
    if [ "$1" == "--background" ]; then
        log_info "Starting in background mode, logs will be written to mcp_dock.log"
        nohup uv run uvicorn mcp_dock.api.gateway:app --host 0.0.0.0 --port $PORT --reload --log-level info > mcp_dock.log 2>&1 &
        echo $! > mcp_dock.pid
        log_info "MCP-Dock started in background mode, PID: $(cat mcp_dock.pid)"
    else
        log_info "Starting in foreground mode"
        uv run uvicorn mcp_dock.api.gateway:app --host 0.0.0.0 --port $PORT --reload --log-level info
    fi
}

# Execute main function
main $@
