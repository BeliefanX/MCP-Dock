#!/bin/bash
# MCP-Dock Service Installation Script
# This script installs MCP-Dock as a system service on Debian/Ubuntu systems

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
INSTALL_DIR="/opt/mcp-dock"
SERVICE_USER="mcp-dock"
SERVICE_GROUP="mcp-dock"
LOG_DIR="/var/log/mcp-dock"
CONFIG_DIR="/etc/mcp-dock"
DATA_DIR="/var/lib/mcp-dock"
SERVICE_FILE="/etc/systemd/system/mcp-dock.service"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# 检查是否以 root 权限运行
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# 检查系统兼容性
check_system() {
    log_info "Checking system compatibility..."
    
    # 检查是否是 Debian/Ubuntu 系统
    if [[ ! -f /etc/debian_version ]]; then
        log_error "This script is designed for Debian/Ubuntu systems"
        exit 1
    fi
    
    # 检查 systemd
    if ! command -v systemctl >/dev/null 2>&1; then
        log_error "systemd is required but not found"
        exit 1
    fi
    
    log_info "System compatibility check passed"
}

# 安装依赖
install_dependencies() {
    log_info "Installing system dependencies..."
    
    # 更新包列表
    apt-get update
    
    # 安装必要的包
    apt-get install -y \
        curl \
        wget \
        git \
        python3 \
        python3-pip \
        python3-venv \
        nodejs \
        npm \
        build-essential \
        pkg-config \
        libssl-dev
    
    # 安装 uv
    if ! command -v uv >/dev/null 2>&1; then
        log_info "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # 确保 uv 在系统路径中
        if [[ -f /root/.cargo/bin/uv ]]; then
            cp /root/.cargo/bin/uv /usr/local/bin/
        fi
    fi
    
    log_info "Dependencies installed successfully"
}

# 创建系统用户
create_user() {
    log_info "Creating system user and group..."
    
    # 创建组
    if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
        groupadd --system "$SERVICE_GROUP"
        log_info "Created group: $SERVICE_GROUP"
    fi
    
    # 创建用户
    if ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
        useradd --system \
            --gid "$SERVICE_GROUP" \
            --home-dir "$INSTALL_DIR" \
            --no-create-home \
            --shell /bin/false \
            --comment "MCP-Dock service user" \
            "$SERVICE_USER"
        log_info "Created user: $SERVICE_USER"
    fi
}

# 创建目录结构
create_directories() {
    log_info "Creating directory structure..."
    
    # 创建主要目录
    for dir in "$INSTALL_DIR" "$LOG_DIR" "$CONFIG_DIR" "$DATA_DIR"; do
        mkdir -p "$dir"
        log_debug "Created directory: $dir"
    done
    
    # 创建 bin 目录
    mkdir -p "$INSTALL_DIR/bin"
    
    # 设置权限
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR" "$LOG_DIR" "$CONFIG_DIR" "$DATA_DIR"
    chmod 755 "$INSTALL_DIR" "$CONFIG_DIR"
    chmod 750 "$LOG_DIR" "$DATA_DIR"
    
    log_info "Directory structure created successfully"
}

# 安装 MCP-Dock
install_mcp_dock() {
    log_info "Installing MCP-Dock..."
    
    # 获取当前脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    
    # 复制项目文件
    log_info "Copying project files..."
    cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"
    
    # 复制服务脚本
    cp "$SCRIPT_DIR/mcp-dock-service" "$INSTALL_DIR/bin/"
    chmod +x "$INSTALL_DIR/bin/mcp-dock-service"
    
    # 复制配置文件
    if [[ -f "$PROJECT_DIR/mcp_dock/config/mcp.config.json" ]]; then
        cp "$PROJECT_DIR/mcp_dock/config/mcp.config.json" "$CONFIG_DIR/"
    fi
    
    if [[ -f "$PROJECT_DIR/mcp_dock/config/proxy_config.json" ]]; then
        cp "$PROJECT_DIR/mcp_dock/config/proxy_config.json" "$CONFIG_DIR/"
    fi
    
    # 安装 Python 依赖
    log_info "Installing Python dependencies..."
    cd "$INSTALL_DIR"
    sudo -u "$SERVICE_USER" uv sync
    
    # 设置权限
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
    
    log_info "MCP-Dock installed successfully"
}

# 安装 systemd 服务
install_systemd_service() {
    log_info "Installing systemd service..."
    
    # 获取当前脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    
    # 复制服务文件
    cp "$PROJECT_DIR/systemd/mcp-dock.service" "$SERVICE_FILE"
    
    # 重新加载 systemd
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable mcp-dock.service
    
    log_info "Systemd service installed and enabled"
}

# 主安装函数
main() {
    log_info "Starting MCP-Dock service installation..."
    
    # 检查权限
    check_root
    
    # 检查系统
    check_system
    
    # 安装依赖
    install_dependencies
    
    # 创建用户
    create_user
    
    # 创建目录
    create_directories
    
    # 安装 MCP-Dock
    install_mcp_dock
    
    # 安装 systemd 服务
    install_systemd_service
    
    log_info "Installation completed successfully!"
    echo
    log_info "Next steps:"
    echo "  1. Edit configuration files in $CONFIG_DIR"
    echo "  2. Start the service: sudo systemctl start mcp-dock"
    echo "  3. Check status: sudo systemctl status mcp-dock"
    echo "  4. View logs: sudo journalctl -u mcp-dock -f"
    echo
}

# 执行主函数
main "$@"
