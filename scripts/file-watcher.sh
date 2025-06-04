#!/bin/bash
# MCP-Dock File Watcher and Auto-Restart Script
# This script monitors code changes and automatically restarts the service

set -euo pipefail

# 配置变量
WATCH_DIR="${1:-/opt/mcp-dock}"
SERVICE_NAME="mcp-dock"
EXCLUDE_PATTERNS="*.log,*.pyc,__pycache__,*.tmp,.git,node_modules"
DEBOUNCE_TIME=5  # 秒
RESTART_DELAY=2  # 秒

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG:${NC} $1"
}

# 检查依赖
check_dependencies() {
    if ! command -v inotifywait >/dev/null 2>&1; then
        log_error "inotifywait is required but not installed"
        log_info "Install it with: sudo apt-get install inotify-tools"
        exit 1
    fi
    
    if ! command -v systemctl >/dev/null 2>&1; then
        log_error "systemctl is required but not found"
        exit 1
    fi
}

# 检查服务状态
check_service_status() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        return 0
    else
        return 1
    fi
}

# 重启服务
restart_service() {
    log_info "Restarting $SERVICE_NAME service..."
    
    if systemctl restart "$SERVICE_NAME"; then
        log_info "Service restarted successfully"
        
        # 等待服务启动
        sleep "$RESTART_DELAY"
        
        # 检查服务状态
        if check_service_status; then
            log_info "Service is running normally"
        else
            log_error "Service failed to start properly"
            systemctl status "$SERVICE_NAME" --no-pager || true
        fi
    else
        log_error "Failed to restart service"
        systemctl status "$SERVICE_NAME" --no-pager || true
    fi
}

# 处理文件变化
handle_file_change() {
    local file="$1"
    local event="$2"
    
    log_debug "File change detected: $file ($event)"
    
    # 检查是否是需要重启的文件类型
    case "$file" in
        *.py|*.json|*.toml|*.yaml|*.yml|*.sh)
            log_info "Code/config file changed: $file"
            return 0
            ;;
        *)
            log_debug "Ignoring file change: $file"
            return 1
            ;;
    esac
}

# 防抖动处理
debounce_restart() {
    local last_restart_file="/tmp/mcp-dock-last-restart"
    local current_time=$(date +%s)
    local last_restart_time=0
    
    if [[ -f "$last_restart_file" ]]; then
        last_restart_time=$(cat "$last_restart_file")
    fi
    
    local time_diff=$((current_time - last_restart_time))
    
    if [[ $time_diff -lt $DEBOUNCE_TIME ]]; then
        log_debug "Restart debounced (${time_diff}s < ${DEBOUNCE_TIME}s)"
        return 1
    fi
    
    echo "$current_time" > "$last_restart_file"
    return 0
}

# 主监控循环
start_monitoring() {
    log_info "Starting file monitoring for: $WATCH_DIR"
    log_info "Service: $SERVICE_NAME"
    log_info "Debounce time: ${DEBOUNCE_TIME}s"
    log_info "Exclude patterns: $EXCLUDE_PATTERNS"
    echo
    
    # 构建 inotifywait 排除参数
    local exclude_args=""
    IFS=',' read -ra PATTERNS <<< "$EXCLUDE_PATTERNS"
    for pattern in "${PATTERNS[@]}"; do
        exclude_args="$exclude_args --exclude $pattern"
    done
    
    # 监控文件变化
    inotifywait -m -r \
        --format '%w%f %e' \
        --event modify,create,delete,move \
        $exclude_args \
        "$WATCH_DIR" | while read file event; do
        
        if handle_file_change "$file" "$event"; then
            if debounce_restart; then
                restart_service
            fi
        fi
    done
}

# 信号处理
cleanup() {
    log_info "Received termination signal, stopping file watcher..."
    exit 0
}

trap cleanup SIGTERM SIGINT SIGQUIT

# 显示帮助
show_help() {
    echo "MCP-Dock File Watcher and Auto-Restart Script"
    echo
    echo "Usage: $0 [watch_directory]"
    echo
    echo "Arguments:"
    echo "  watch_directory     Directory to monitor (default: /opt/mcp-dock)"
    echo
    echo "Environment Variables:"
    echo "  DEBOUNCE_TIME       Minimum time between restarts in seconds (default: 5)"
    echo "  RESTART_DELAY       Delay after restart before checking status (default: 2)"
    echo "  EXCLUDE_PATTERNS    Comma-separated patterns to exclude (default: *.log,*.pyc,__pycache__,*.tmp,.git,node_modules)"
    echo
    echo "Examples:"
    echo "  $0                          # Monitor /opt/mcp-dock"
    echo "  $0 /path/to/mcp-dock        # Monitor custom directory"
    echo "  DEBOUNCE_TIME=10 $0         # Use 10-second debounce"
    echo
    echo "Requirements:"
    echo "  - inotify-tools package (sudo apt-get install inotify-tools)"
    echo "  - systemctl command"
    echo "  - Root privileges to restart service"
    echo
}

# 主函数
main() {
    # 检查帮助参数
    if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
        show_help
        exit 0
    fi
    
    # 检查是否以 root 权限运行
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # 检查依赖
    check_dependencies
    
    # 检查监控目录
    if [[ ! -d "$WATCH_DIR" ]]; then
        log_error "Watch directory does not exist: $WATCH_DIR"
        exit 1
    fi
    
    # 检查服务是否存在
    if ! systemctl list-unit-files | grep -q "^$SERVICE_NAME.service"; then
        log_error "Service $SERVICE_NAME is not installed"
        exit 1
    fi
    
    # 开始监控
    start_monitoring
}

# 执行主函数
main "$@"
