#!/bin/bash
# MCP-Dock Startup Script
# This script checks if there are already processes running or if the port is in use
# If so, it will terminate these processes, then start the application using uv

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

# Check if required commands are available
check_required_commands() {
    local missing_commands=()
    
    for cmd in uv lsof kill pgrep; do
        if ! command -v $cmd &> /dev/null; then
            missing_commands+=($cmd)
        fi
    done
    
    if [ ${#missing_commands[@]} -ne 0 ]; then
        log_error "Error: The following commands are not installed: ${missing_commands[*]}"
        
        if [[ " ${missing_commands[*]} " =~ " uv " ]]; then
            echo -e "Install uv command: curl -LsSf https://astral.sh/uv/install.sh | sh"
        fi
        
        exit 1
    fi
}

# Check if uv is installed
check_uv() {
    if ! command -v uv &> /dev/null; then
        log_error "Error: uv is not installed."
        echo -e "Please install uv using the following command:"
        echo -e "    pip install uv"
        exit 1
    fi
    
    log_debug "uv is installed: $(uv --version 2>&1 | head -n 1)"
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
    
    # Perform checks
    check_required_commands
    check_uv
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
