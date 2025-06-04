#!/bin/bash
# MCP-Dock Service Management Script
# This script provides convenient commands to manage the MCP-Dock service

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
SERVICE_NAME="mcp-dock"
LOG_DIR="/var/log/mcp-dock"
CONFIG_DIR="/etc/mcp-dock"
INSTALL_DIR="/opt/mcp-dock"

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

# 显示服务状态
show_status() {
    log_info "MCP-Dock Service Status:"
    systemctl status "$SERVICE_NAME" --no-pager || true
    echo
    
    # 显示端口使用情况
    log_info "Port Usage:"
    ss -tuln | grep ":8000 " || echo "Port 8000 is not in use"
    echo
    
    # 显示最近的日志
    log_info "Recent Logs (last 10 lines):"
    journalctl -u "$SERVICE_NAME" -n 10 --no-pager || true
}

# 启动服务
start_service() {
    log_info "Starting MCP-Dock service..."
    systemctl start "$SERVICE_NAME"
    sleep 2
    show_status
}

# 停止服务
stop_service() {
    log_info "Stopping MCP-Dock service..."
    systemctl stop "$SERVICE_NAME"
    sleep 2
    log_info "Service stopped"
}

# 重启服务
restart_service() {
    log_info "Restarting MCP-Dock service..."
    systemctl restart "$SERVICE_NAME"
    sleep 2
    show_status
}

# 重新加载配置
reload_service() {
    log_info "Reloading MCP-Dock service configuration..."
    systemctl reload "$SERVICE_NAME" || restart_service
    sleep 2
    show_status
}

# 启用服务
enable_service() {
    log_info "Enabling MCP-Dock service for auto-start..."
    systemctl enable "$SERVICE_NAME"
    log_info "Service enabled for auto-start"
}

# 禁用服务
disable_service() {
    log_info "Disabling MCP-Dock service auto-start..."
    systemctl disable "$SERVICE_NAME"
    log_info "Service auto-start disabled"
}

# 查看日志
view_logs() {
    local lines="${1:-50}"
    log_info "Viewing MCP-Dock service logs (last $lines lines):"
    journalctl -u "$SERVICE_NAME" -n "$lines" --no-pager
}

# 跟踪日志
follow_logs() {
    log_info "Following MCP-Dock service logs (press Ctrl+C to stop):"
    journalctl -u "$SERVICE_NAME" -f
}

# 检查配置
check_config() {
    log_info "Checking MCP-Dock configuration..."
    
    # 检查配置文件
    if [[ -f "$CONFIG_DIR/mcp.config.json" ]]; then
        log_info "✓ MCP configuration file exists"
        if python3 -m json.tool "$CONFIG_DIR/mcp.config.json" >/dev/null 2>&1; then
            log_info "✓ MCP configuration file is valid JSON"
        else
            log_error "✗ MCP configuration file has invalid JSON syntax"
        fi
    else
        log_warn "✗ MCP configuration file not found"
    fi
    
    if [[ -f "$CONFIG_DIR/proxy_config.json" ]]; then
        log_info "✓ Proxy configuration file exists"
        if python3 -m json.tool "$CONFIG_DIR/proxy_config.json" >/dev/null 2>&1; then
            log_info "✓ Proxy configuration file is valid JSON"
        else
            log_error "✗ Proxy configuration file has invalid JSON syntax"
        fi
    else
        log_warn "✗ Proxy configuration file not found"
    fi
    
    # 检查权限
    log_info "Checking file permissions..."
    ls -la "$CONFIG_DIR"/ || true
    echo
    ls -la "$LOG_DIR"/ || true
}

# 更新服务
update_service() {
    log_info "Updating MCP-Dock service..."
    
    # 停止服务
    systemctl stop "$SERVICE_NAME" || true
    
    # 备份当前配置
    backup_dir="/tmp/mcp-dock-backup-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r "$CONFIG_DIR"/* "$backup_dir/" 2>/dev/null || true
    log_info "Configuration backed up to: $backup_dir"
    
    # 这里可以添加更新逻辑
    log_warn "Update functionality not implemented yet"
    log_info "Please manually update the installation and restart the service"
    
    # 重启服务
    systemctl start "$SERVICE_NAME"
    show_status
}

# 卸载服务
uninstall_service() {
    log_warn "This will completely remove MCP-Dock service and all its data!"
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Uninstallation cancelled"
        return
    fi
    
    log_info "Uninstalling MCP-Dock service..."
    
    # 停止并禁用服务
    systemctl stop "$SERVICE_NAME" || true
    systemctl disable "$SERVICE_NAME" || true
    
    # 删除服务文件
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    
    # 删除用户和组
    userdel mcp-dock 2>/dev/null || true
    groupdel mcp-dock 2>/dev/null || true
    
    # 删除文件和目录
    rm -rf "$INSTALL_DIR" "$LOG_DIR" "$CONFIG_DIR" "/var/lib/mcp-dock"
    
    log_info "MCP-Dock service uninstalled successfully"
}

# 显示帮助信息
show_help() {
    echo "MCP-Dock Service Management Script"
    echo
    echo "Usage: $0 <command> [options]"
    echo
    echo "Commands:"
    echo "  status              Show service status and recent logs"
    echo "  start               Start the service"
    echo "  stop                Stop the service"
    echo "  restart             Restart the service"
    echo "  reload              Reload service configuration"
    echo "  enable              Enable service for auto-start"
    echo "  disable             Disable service auto-start"
    echo "  logs [lines]        View service logs (default: 50 lines)"
    echo "  follow              Follow service logs in real-time"
    echo "  config              Check configuration files"
    echo "  update              Update the service (backup configs first)"
    echo "  uninstall           Completely remove the service"
    echo "  help                Show this help message"
    echo
    echo "Examples:"
    echo "  $0 status           # Show current status"
    echo "  $0 logs 100         # Show last 100 log lines"
    echo "  $0 restart          # Restart the service"
    echo
}

# 主函数
main() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 1
    fi
    
    local command="$1"
    shift || true
    
    case "$command" in
        "status")
            show_status
            ;;
        "start")
            check_root
            start_service
            ;;
        "stop")
            check_root
            stop_service
            ;;
        "restart")
            check_root
            restart_service
            ;;
        "reload")
            check_root
            reload_service
            ;;
        "enable")
            check_root
            enable_service
            ;;
        "disable")
            check_root
            disable_service
            ;;
        "logs")
            view_logs "${1:-50}"
            ;;
        "follow")
            follow_logs
            ;;
        "config")
            check_config
            ;;
        "update")
            check_root
            update_service
            ;;
        "uninstall")
            check_root
            uninstall_service
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
