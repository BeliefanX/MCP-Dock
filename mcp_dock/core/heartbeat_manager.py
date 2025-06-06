"""
Heartbeat Manager for MCP-Dock

Manages heartbeat mechanisms across different transport protocols with enhanced monitoring.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from threading import Lock

from mcp_dock.utils.logging_config import get_logger, log_mcp_request, log_performance

logger = get_logger(__name__)


@dataclass
class HeartbeatConfig:
    """Heartbeat configuration"""
    heartbeat_interval_seconds: int = 10
    heartbeat_check_interval_seconds: int = 1
    heartbeat_log_interval_seconds: int = 60
    session_timeout_seconds: int = 300
    cleanup_interval_seconds: int = 300
    
    # Performance monitoring
    performance_monitoring_enabled: bool = True
    response_time_threshold_ms: float = 1000.0
    error_rate_threshold_percent: float = 5.0
    latency_monitoring: bool = True
    
    # Logging configuration
    enhanced_heartbeat_logging: bool = True
    include_client_info: bool = True
    include_performance_metrics: bool = True
    structured_logging: bool = True
    
    # Adaptive heartbeat
    adaptive_heartbeat_enabled: bool = True
    min_interval_seconds: int = 5
    max_interval_seconds: int = 30
    load_based_adjustment: bool = True
    error_based_adjustment: bool = True


@dataclass
class HeartbeatMetrics:
    """Heartbeat performance metrics"""
    total_heartbeats: int = 0
    successful_heartbeats: int = 0
    failed_heartbeats: int = 0
    average_response_time_ms: float = 0.0
    last_heartbeat_time: float = 0.0
    error_rate_percent: float = 0.0
    response_times: List[float] = field(default_factory=list)
    
    def add_response_time(self, response_time_ms: float):
        """Add a response time measurement"""
        self.response_times.append(response_time_ms)
        # Keep only last 100 measurements
        if len(self.response_times) > 100:
            self.response_times.pop(0)
        
        # Update average
        self.average_response_time_ms = sum(self.response_times) / len(self.response_times)
    
    def record_heartbeat(self, success: bool, response_time_ms: float = 0.0):
        """Record a heartbeat attempt"""
        self.total_heartbeats += 1
        self.last_heartbeat_time = time.time()
        
        if success:
            self.successful_heartbeats += 1
            if response_time_ms > 0:
                self.add_response_time(response_time_ms)
        else:
            self.failed_heartbeats += 1
        
        # Update error rate
        if self.total_heartbeats > 0:
            self.error_rate_percent = (self.failed_heartbeats / self.total_heartbeats) * 100


class HeartbeatManager:
    """Manages heartbeat mechanisms across different transport protocols"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.metrics: Dict[str, HeartbeatMetrics] = {}
        self.metrics_lock = Lock()
        self._running = False
        
        logger.info("Heartbeat Manager initialized with enhanced monitoring")
    
    def _load_config(self, config_path: Optional[str] = None) -> HeartbeatConfig:
        """Load heartbeat configuration from file"""
        if not config_path:
            # Default to project config directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            config_path = os.path.join(project_root, "config", "heartbeat.config.json")
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Extract nested configuration
                perf_config = config_data.get("performance_monitoring", {})
                log_config = config_data.get("logging", {})
                adaptive_config = config_data.get("adaptive_heartbeat", {})
                
                return HeartbeatConfig(
                    heartbeat_interval_seconds=config_data.get("heartbeat_interval_seconds", 10),
                    heartbeat_check_interval_seconds=config_data.get("heartbeat_check_interval_seconds", 1),
                    heartbeat_log_interval_seconds=config_data.get("heartbeat_log_interval_seconds", 60),
                    session_timeout_seconds=config_data.get("session_timeout_seconds", 300),
                    cleanup_interval_seconds=config_data.get("cleanup_interval_seconds", 300),
                    
                    # Performance monitoring
                    performance_monitoring_enabled=perf_config.get("enabled", True),
                    response_time_threshold_ms=perf_config.get("response_time_threshold_ms", 1000.0),
                    error_rate_threshold_percent=perf_config.get("error_rate_threshold_percent", 5.0),
                    latency_monitoring=perf_config.get("latency_monitoring", True),
                    
                    # Logging
                    enhanced_heartbeat_logging=log_config.get("enhanced_heartbeat_logging", True),
                    include_client_info=log_config.get("include_client_info", True),
                    include_performance_metrics=log_config.get("include_performance_metrics", True),
                    structured_logging=log_config.get("structured_logging", True),
                    
                    # Adaptive heartbeat
                    adaptive_heartbeat_enabled=adaptive_config.get("enabled", True),
                    min_interval_seconds=adaptive_config.get("min_interval_seconds", 5),
                    max_interval_seconds=adaptive_config.get("max_interval_seconds", 30),
                    load_based_adjustment=adaptive_config.get("load_based_adjustment", True),
                    error_based_adjustment=adaptive_config.get("error_based_adjustment", True)
                )
            else:
                logger.info(f"Heartbeat config file not found at {config_path}, using defaults")
                return HeartbeatConfig()
                
        except Exception as e:
            logger.error(f"Error loading heartbeat config: {e}, using defaults")
            return HeartbeatConfig()
    
    def get_session_metrics(self, session_id: str) -> HeartbeatMetrics:
        """Get or create metrics for a session"""
        with self.metrics_lock:
            if session_id not in self.metrics:
                self.metrics[session_id] = HeartbeatMetrics()
            return self.metrics[session_id]
    
    def record_heartbeat(self, session_id: str, success: bool, response_time_ms: float = 0.0):
        """Record a heartbeat for a session"""
        metrics = self.get_session_metrics(session_id)
        metrics.record_heartbeat(success, response_time_ms)
        
        # Log performance if monitoring is enabled
        if self.config.performance_monitoring_enabled and self.config.include_performance_metrics:
            if response_time_ms > self.config.response_time_threshold_ms:
                logger.warning(f"Slow heartbeat response: {response_time_ms:.2f}ms for session {session_id[:8]}...")
    
    def get_adaptive_interval(self, session_id: str, system_load: float = 0.0) -> int:
        """Calculate adaptive heartbeat interval based on metrics and system load"""
        if not self.config.adaptive_heartbeat_enabled:
            return self.config.heartbeat_interval_seconds
        
        metrics = self.get_session_metrics(session_id)
        base_interval = self.config.heartbeat_interval_seconds
        
        # Adjust based on error rate
        if self.config.error_based_adjustment and metrics.error_rate_percent > self.config.error_rate_threshold_percent:
            # Increase interval if error rate is high
            base_interval = min(base_interval * 1.5, self.config.max_interval_seconds)
        
        # Adjust based on response time
        if metrics.average_response_time_ms > self.config.response_time_threshold_ms:
            # Increase interval if responses are slow
            base_interval = min(base_interval * 1.2, self.config.max_interval_seconds)
        
        # Adjust based on system load
        if self.config.load_based_adjustment and system_load > 0.8:
            # Increase interval under high load
            base_interval = min(base_interval * 1.3, self.config.max_interval_seconds)
        
        # Ensure within bounds
        return max(self.config.min_interval_seconds, min(int(base_interval), self.config.max_interval_seconds))
    
    def cleanup_session_metrics(self, session_id: str):
        """Clean up metrics for a session"""
        with self.metrics_lock:
            if session_id in self.metrics:
                del self.metrics[session_id]
    
    def get_overall_metrics(self) -> Dict[str, Any]:
        """Get overall heartbeat metrics across all sessions"""
        with self.metrics_lock:
            if not self.metrics:
                return {
                    "total_sessions": 0,
                    "total_heartbeats": 0,
                    "overall_success_rate": 100.0,
                    "average_response_time_ms": 0.0,
                    "sessions_with_issues": 0
                }
            
            total_heartbeats = sum(m.total_heartbeats for m in self.metrics.values())
            total_successful = sum(m.successful_heartbeats for m in self.metrics.values())
            total_failed = sum(m.failed_heartbeats for m in self.metrics.values())
            
            # Calculate weighted average response time
            total_response_time = 0.0
            total_measurements = 0
            sessions_with_issues = 0
            
            for metrics in self.metrics.values():
                if metrics.response_times:
                    total_response_time += sum(metrics.response_times)
                    total_measurements += len(metrics.response_times)
                
                # Count sessions with issues
                if (metrics.error_rate_percent > self.config.error_rate_threshold_percent or
                    metrics.average_response_time_ms > self.config.response_time_threshold_ms):
                    sessions_with_issues += 1
            
            return {
                "total_sessions": len(self.metrics),
                "total_heartbeats": total_heartbeats,
                "successful_heartbeats": total_successful,
                "failed_heartbeats": total_failed,
                "overall_success_rate": (total_successful / total_heartbeats * 100) if total_heartbeats > 0 else 100.0,
                "average_response_time_ms": (total_response_time / total_measurements) if total_measurements > 0 else 0.0,
                "sessions_with_issues": sessions_with_issues,
                "config": {
                    "heartbeat_interval": self.config.heartbeat_interval_seconds,
                    "adaptive_enabled": self.config.adaptive_heartbeat_enabled,
                    "performance_monitoring": self.config.performance_monitoring_enabled
                }
            }
