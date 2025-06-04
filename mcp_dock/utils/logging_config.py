"""Centralized logging configuration for MCP-Dock."""

import logging
import logging.handlers
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional, List
from collections import deque


class MemoryLogHandler(logging.Handler):
    """内存日志处理器，支持自动清理和文件保存"""

    def __init__(self, max_records: int = 1000, backup_file: Optional[str] = None):
        super().__init__()
        self.max_records = max_records
        self.backup_file = backup_file
        self.records = deque(maxlen=max_records)
        self.lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """发出日志记录"""
        try:
            with self.lock:
                # 添加新记录
                self.records.append(record)

                # 如果达到最大记录数，保存到文件（在添加后检查）
                if len(self.records) >= self.max_records and self.backup_file:
                    # 在单独的线程中执行备份，避免死锁
                    threading.Thread(target=self._backup_to_file, daemon=True).start()
        except Exception:
            self.handleError(record)

    def _backup_to_file(self) -> None:
        """将内存中的日志备份到文件"""
        if not self.backup_file:
            return

        try:
            backup_path = Path(self.backup_file)
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # 创建带时间戳的备份文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file_with_timestamp = backup_path.with_name(
                f"{backup_path.stem}_{timestamp}{backup_path.suffix}"
            )

            with open(backup_file_with_timestamp, 'a', encoding='utf-8') as f:
                f.write(f"\n# Memory log backup at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                for record in list(self.records):
                    formatted = self.format(record)
                    f.write(f"{formatted}\n")
                f.write(f"# End of backup\n\n")

            # 清空内存记录
            self.records.clear()

        except Exception as e:
            # 避免在日志处理器中产生无限递归
            print(f"Failed to backup memory logs: {e}", file=sys.stderr)

    def get_recent_logs(self, count: Optional[int] = None) -> List[str]:
        """获取最近的日志记录"""
        with self.lock:
            records = list(self.records)
            if count:
                records = records[-count:]
            return [self.format(record) for record in records]

    def clear_logs(self) -> None:
        """清空内存日志"""
        with self.lock:
            self.records.clear()


class RotatingFileHandlerWithCleanup(logging.handlers.TimedRotatingFileHandler):
    """带自动清理功能的轮转文件处理器"""

    def __init__(self, filename: str, when: str = 'midnight', interval: int = 1,
                 backupCount: int = 30, encoding: Optional[str] = None,
                 delay: bool = False, utc: bool = False, atTime=None):
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc, atTime)
        self.cleanup_thread = None
        self.start_cleanup_thread()

    def start_cleanup_thread(self) -> None:
        """启动清理线程"""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=self._cleanup_old_logs, daemon=True)
            self.cleanup_thread.start()

    def _cleanup_old_logs(self) -> None:
        """清理旧日志文件"""
        while True:
            try:
                # 每天检查一次
                time.sleep(24 * 3600)

                if self.backupCount > 0:
                    # 获取日志文件目录
                    log_dir = Path(self.baseFilename).parent
                    log_name = Path(self.baseFilename).stem

                    # 查找所有相关的日志文件
                    pattern = f"{log_name}.*"
                    log_files = list(log_dir.glob(pattern))

                    # 按修改时间排序
                    log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

                    # 删除超过保留数量的文件
                    for old_file in log_files[self.backupCount:]:
                        try:
                            old_file.unlink()
                        except OSError:
                            pass

            except Exception:
                # 静默处理清理错误
                pass


def setup_logging(
    level: Optional[int] = None,
    log_file: str = "mcp_dock.log",
    force_reconfigure: bool = False,
    enable_memory_handler: bool = True,
    memory_max_records: int = 1000,
    log_retention_days: int = 30
) -> None:
    """Setup centralized logging configuration with enhanced features.

    Args:
        level: Logging level (defaults to INFO or env var MCP_DOCK_LOG_LEVEL)
        log_file: Log file path
        force_reconfigure: Force reconfiguration even if already configured
        enable_memory_handler: Enable in-memory log handler
        memory_max_records: Maximum records in memory before backup
        log_retention_days: Days to retain log files
    """
    # Check if logging is already configured
    root_logger = logging.getLogger()
    if root_logger.handlers and not force_reconfigure:
        return

    # Clear existing handlers if force reconfiguring
    if force_reconfigure:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # Determine log level
    if level is None:
        log_level_str = os.getenv('MCP_DOCK_LOG_LEVEL', 'INFO').upper()
        level = getattr(logging, log_level_str, logging.INFO)

    # Create enhanced formatter with more details
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handlers
    file_handlers = []

    try:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler with automatic cleanup
        rotating_handler = RotatingFileHandlerWithCleanup(
            filename=str(log_path),
            when='midnight',
            interval=1,
            backupCount=log_retention_days,
            encoding='utf-8'
        )
        rotating_handler.setFormatter(formatter)
        file_handlers.append(rotating_handler)

        # Memory handler for terminal logs
        if enable_memory_handler:
            memory_backup_file = log_path.with_name(f"{log_path.stem}_memory_backup.log")
            memory_handler = MemoryLogHandler(
                max_records=memory_max_records,
                backup_file=str(memory_backup_file)
            )
            memory_handler.setFormatter(formatter)
            file_handlers.append(memory_handler)

            # Store reference for later access
            setattr(root_logger, '_memory_handler', memory_handler)

    except (OSError, PermissionError) as e:
        # If file logging fails, continue with console only
        print(f"Warning: Failed to setup file logging: {e}", file=sys.stderr)

    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    for handler in file_handlers:
        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    # Ensure logging is configured
    setup_logging()
    return logging.getLogger(name)


def get_recent_memory_logs(count: Optional[int] = None) -> List[str]:
    """获取最近的内存日志记录

    Args:
        count: 要获取的日志条数，None 表示获取所有

    Returns:
        日志记录列表
    """
    root_logger = logging.getLogger()
    memory_handler = getattr(root_logger, '_memory_handler', None)

    if memory_handler and isinstance(memory_handler, MemoryLogHandler):
        return memory_handler.get_recent_logs(count)

    return []


def clear_memory_logs() -> None:
    """清空内存日志"""
    root_logger = logging.getLogger()
    memory_handler = getattr(root_logger, '_memory_handler', None)

    if memory_handler and isinstance(memory_handler, MemoryLogHandler):
        memory_handler.clear_logs()


def get_log_stats() -> dict:
    """获取日志统计信息

    Returns:
        包含日志统计信息的字典
    """
    root_logger = logging.getLogger()
    memory_handler = getattr(root_logger, '_memory_handler', None)

    stats = {
        'memory_logs_count': 0,
        'memory_max_records': 0,
        'handlers_count': len(root_logger.handlers),
        'log_level': logging.getLevelName(root_logger.level)
    }

    if memory_handler and isinstance(memory_handler, MemoryLogHandler):
        with memory_handler.lock:
            stats['memory_logs_count'] = len(memory_handler.records)
            stats['memory_max_records'] = memory_handler.max_records

    return stats


def configure_service_logging(
    log_dir: str = "/var/log/mcp-dock",
    log_level: str = "INFO",
    enable_syslog: bool = True
) -> None:
    """配置系统服务日志

    Args:
        log_dir: 日志目录
        log_level: 日志级别
        enable_syslog: 是否启用 syslog
    """
    # 确保日志目录存在
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 设置日志文件路径
    log_file = os.path.join(log_dir, "mcp-dock.log")

    # 配置日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 重新配置日志
    setup_logging(
        level=level,
        log_file=log_file,
        force_reconfigure=True,
        log_retention_days=30
    )

    # 添加 syslog 处理器（如果启用）
    if enable_syslog:
        try:
            syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
            syslog_formatter = logging.Formatter(
                'mcp-dock[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            syslog_handler.setLevel(level)

            root_logger = logging.getLogger()
            root_logger.addHandler(syslog_handler)

        except Exception as e:
            print(f"Warning: Failed to setup syslog: {e}", file=sys.stderr)