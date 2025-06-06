"""
SSE Session Manager for MCP-Dock

Manages SSE sessions for MCP Inspector compatibility.
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from threading import Lock
from collections import deque

from mcp_dock.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PendingMessage:
    """Represents a pending message with metadata"""
    message: Dict[str, Any]
    timestamp: float
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0  # 30 seconds timeout


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    max_sessions_per_client: int = 10  # Increased from 5 to 10
    max_sessions_per_proxy: int = 50   # Increased from 20 to 50
    session_creation_window: int = 60  # Time window in seconds
    burst_allowance: int = 3           # Allow burst connections
    adaptive_scaling: bool = True      # Enable adaptive scaling
    warning_threshold: float = 0.8     # Warn when approaching limits


@dataclass
class SSESession:
    """Represents an SSE session"""
    session_id: str
    proxy_name: str
    client_host: str
    created_at: float
    pending_messages: deque = field(default_factory=deque)
    is_initialized: bool = False
    last_activity: float = field(default_factory=time.time)
    message_timeout: float = 30.0  # Message timeout in seconds


class SSESessionManager:
    """Manages SSE sessions for MCP Inspector compatibility"""

    _instance: Optional['SSESessionManager'] = None
    _lock = Lock()

    def __init__(self):
        self.sessions: Dict[str, SSESession] = {}
        self.session_lock = Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 60  # 1 minute
        self._session_timeout = 300  # 5 minutes
        self._running = False

        # Load rate limiting configuration
        self.rate_limit_config = self._load_rate_limit_config()
        self._client_session_history: Dict[str, List[float]] = {}  # Track session creation times per client

        # Performance optimization: cache for rate limit calculations
        self._rate_limit_cache: Dict[str, tuple[float, bool, str]] = {}  # client_host -> (timestamp, allowed, reason)
        self._cache_ttl = 5.0  # Cache TTL in seconds

        # Rate limit violation tracking for monitoring and diagnostics
        self._rate_limit_violations: Dict[str, List[Dict[str, Any]]] = {}  # client_host -> [violation_records]
        self._violation_history_limit = 100  # Keep last 100 violations per client
        self._violation_window = 3600  # 1 hour window for violation tracking
    
    @classmethod
    def get_instance(cls) -> 'SSESessionManager':
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _load_rate_limit_config(self) -> RateLimitConfig:
        """Load rate limiting configuration from file or use defaults"""
        try:
            # Get config directory path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # Go up from core/ to mcp_dock/
            config_path = os.path.join(project_root, "config", "rate_limit.config.json")

            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # Create config with loaded values, using defaults for missing fields
                config = RateLimitConfig(
                    max_sessions_per_client=config_data.get("max_sessions_per_client", 10),
                    max_sessions_per_proxy=config_data.get("max_sessions_per_proxy", 50),
                    session_creation_window=config_data.get("session_creation_window", 60),
                    burst_allowance=config_data.get("burst_allowance", 3),
                    adaptive_scaling=config_data.get("adaptive_scaling", True),
                    warning_threshold=config_data.get("warning_threshold", 0.8)
                )

                logger.info(f"📋 Loaded rate limit configuration from {config_path}")
                logger.info(f"   📊 Max sessions per client: {config.max_sessions_per_client}")
                logger.info(f"   📊 Max sessions per proxy: {config.max_sessions_per_proxy}")
                logger.info(f"   ⏱️ Session creation window: {config.session_creation_window}s")

                return config
            else:
                # Create default config file
                default_config = RateLimitConfig()
                self._save_rate_limit_config(default_config, config_path)
                logger.info(f"📋 Created default rate limit configuration at {config_path}")
                return default_config

        except Exception as e:
            logger.warning(f"⚠️ Failed to load rate limit configuration: {e}")
            logger.info("📋 Using default rate limit configuration")
            return RateLimitConfig()

    def _save_rate_limit_config(self, config: RateLimitConfig, config_path: str) -> None:
        """Save rate limiting configuration to file"""
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            config_data = {
                "max_sessions_per_client": config.max_sessions_per_client,
                "max_sessions_per_proxy": config.max_sessions_per_proxy,
                "session_creation_window": config.session_creation_window,
                "burst_allowance": config.burst_allowance,
                "adaptive_scaling": config.adaptive_scaling,
                "warning_threshold": config.warning_threshold,
                "_description": "Rate limiting configuration for SSE sessions",
                "_last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            logger.info(f"💾 Saved rate limit configuration to {config_path}")

        except Exception as e:
            logger.error(f"💥 Failed to save rate limit configuration: {e}")

    def reload_rate_limit_config(self) -> bool:
        """Reload rate limiting configuration from file

        Returns:
            bool: True if configuration was reloaded successfully
        """
        try:
            old_config = self.rate_limit_config
            new_config = self._load_rate_limit_config()

            # Clear cache when configuration changes
            if (old_config.max_sessions_per_client != new_config.max_sessions_per_client or
                old_config.max_sessions_per_proxy != new_config.max_sessions_per_proxy or
                old_config.session_creation_window != new_config.session_creation_window):
                self._rate_limit_cache.clear()
                logger.info("🧹 Cleared rate limit cache due to configuration change")

            self.rate_limit_config = new_config
            logger.info("🔄 Rate limit configuration reloaded successfully")
            return True

        except Exception as e:
            logger.error(f"💥 Failed to reload rate limit configuration: {e}")
            return False

    def start_cleanup_task(self) -> None:
        """Start the background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(f"🧹 Started SSE session cleanup task (interval: {self._cleanup_interval}s, timeout: {self._session_timeout}s)")

    def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task"""
        self._running = False
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("🛑 Stopped SSE session cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while self._running:
            try:
                cleaned_count = self.cleanup_expired_sessions(self._session_timeout)
                if cleaned_count > 0:
                    logger.info(f"🧹 Automatic cleanup removed {cleaned_count} expired sessions")

                # Wait for next cleanup cycle
                await asyncio.sleep(self._cleanup_interval)

            except asyncio.CancelledError:
                logger.info("🧹 Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"💥 Error in cleanup loop: {e}")
                await asyncio.sleep(self._cleanup_interval)  # Continue after error
    
    def _check_rate_limits(self, proxy_name: str, client_host: str) -> tuple[bool, str]:
        """Check if session creation should be rate limited with performance optimization

        Returns:
            tuple[bool, str]: (is_allowed, reason_if_denied)
        """
        current_time = time.time()

        # Check cache first for performance optimization
        cache_key = f"{client_host}:{proxy_name}"
        if cache_key in self._rate_limit_cache:
            cached_time, cached_allowed, cached_reason = self._rate_limit_cache[cache_key]
            if current_time - cached_time < self._cache_ttl:
                return cached_allowed, cached_reason

        # Clean up old entries in client session history (optimized)
        cutoff_time = current_time - self.rate_limit_config.session_creation_window
        clients_to_remove = []

        for client_ip, timestamps in self._client_session_history.items():
            # Filter timestamps more efficiently
            recent_timestamps = [t for t in timestamps if t > cutoff_time]
            if recent_timestamps:
                self._client_session_history[client_ip] = recent_timestamps
            else:
                clients_to_remove.append(client_ip)

        # Remove empty entries
        for client_ip in clients_to_remove:
            del self._client_session_history[client_ip]

        # Check sessions per client limit with burst allowance
        client_sessions = self._client_session_history.get(client_host, [])
        effective_client_limit = self.rate_limit_config.max_sessions_per_client

        # Apply burst allowance if adaptive scaling is enabled
        if self.rate_limit_config.adaptive_scaling and len(client_sessions) > 0:
            # Allow burst if client has been inactive recently
            last_session_time = max(client_sessions) if client_sessions else 0
            time_since_last = current_time - last_session_time
            if time_since_last > 30:  # 30 seconds of inactivity allows burst
                effective_client_limit += self.rate_limit_config.burst_allowance

        if len(client_sessions) >= effective_client_limit:
            reason = f"Client {client_host} exceeded rate limit ({len(client_sessions)}/{effective_client_limit} sessions in {self.rate_limit_config.session_creation_window}s)"
            # Record violation for monitoring
            self._record_rate_limit_violation(client_host, proxy_name, "client_limit", reason, {
                "client_sessions": len(client_sessions),
                "effective_limit": effective_client_limit,
                "window_seconds": self.rate_limit_config.session_creation_window,
                "adaptive_scaling_applied": self.rate_limit_config.adaptive_scaling and effective_client_limit > self.rate_limit_config.max_sessions_per_client
            })
            # Cache negative result
            self._rate_limit_cache[cache_key] = (current_time, False, reason)
            return False, reason

        # Check sessions per proxy limit
        proxy_session_count = sum(1 for session in self.sessions.values() if session.proxy_name == proxy_name)
        if proxy_session_count >= self.rate_limit_config.max_sessions_per_proxy:
            reason = f"Proxy {proxy_name} exceeded session limit ({proxy_session_count}/{self.rate_limit_config.max_sessions_per_proxy} active sessions)"
            # Record violation for monitoring
            self._record_rate_limit_violation(client_host, proxy_name, "proxy_limit", reason, {
                "proxy_sessions": proxy_session_count,
                "proxy_limit": self.rate_limit_config.max_sessions_per_proxy
            })
            # Cache negative result
            self._rate_limit_cache[cache_key] = (current_time, False, reason)
            return False, reason

        # Cache positive result
        self._rate_limit_cache[cache_key] = (current_time, True, "")
        return True, ""

    def _record_rate_limit_violation(self, client_host: str, proxy_name: str, violation_type: str, reason: str, details: Dict[str, Any]) -> None:
        """Record a rate limit violation for monitoring and analysis

        Args:
            client_host: Client IP address
            proxy_name: Proxy name
            violation_type: Type of violation (client_limit, proxy_limit)
            reason: Human-readable reason
            details: Additional violation details
        """
        current_time = time.time()

        # Create violation record with enhanced diagnostic information
        violation_record = {
            "timestamp": current_time,
            "client_host": client_host,
            "proxy_name": proxy_name,
            "violation_type": violation_type,
            "reason": reason,
            "details": details,
            "session_id": None,  # Will be set if available
            "user_agent": None,  # Could be extracted from request headers
            "request_path": None,  # Could be extracted from request
            "severity": self._calculate_violation_severity(violation_type, details)
        }

        # Initialize client violation history if needed
        if client_host not in self._rate_limit_violations:
            self._rate_limit_violations[client_host] = []

        # Add violation record
        self._rate_limit_violations[client_host].append(violation_record)

        # Cleanup old violations (keep only recent ones)
        cutoff_time = current_time - self._violation_window
        self._rate_limit_violations[client_host] = [
            v for v in self._rate_limit_violations[client_host]
            if v["timestamp"] > cutoff_time
        ]

        # Limit history size
        if len(self._rate_limit_violations[client_host]) > self._violation_history_limit:
            self._rate_limit_violations[client_host] = self._rate_limit_violations[client_host][-self._violation_history_limit:]

        # Enhanced structured logging with diagnostic context
        logger.warning(
            f"🚫 RATE LIMIT VIOLATION: {violation_type}",
            extra={
                "event_type": "rate_limit_violation",
                "client_host": client_host,
                "proxy_name": proxy_name,
                "violation_type": violation_type,
                "reason": reason,
                "severity": violation_record["severity"],
                "violation_count_1h": len(self._rate_limit_violations[client_host]),
                "details": details,
                "mcp_protocol_version": "2025-03-26",
                "component": "sse_session_manager"
            }
        )

    def _calculate_violation_severity(self, violation_type: str, details: Dict[str, Any]) -> str:
        """Calculate severity level for a rate limit violation

        Args:
            violation_type: Type of violation
            details: Violation details

        Returns:
            Severity level (low, medium, high, critical)
        """
        if violation_type == "client_limit":
            sessions = details.get("client_sessions", 0)
            limit = details.get("effective_limit", 0)
            if sessions > limit * 2:
                return "critical"
            elif sessions > limit * 1.5:
                return "high"
            elif sessions > limit * 1.2:
                return "medium"
            else:
                return "low"
        elif violation_type == "proxy_limit":
            sessions = details.get("proxy_sessions", 0)
            limit = details.get("proxy_limit", 0)
            if sessions > limit * 1.5:
                return "critical"
            elif sessions > limit * 1.2:
                return "high"
            else:
                return "medium"

        return "medium"  # Default severity

    def register_session(self, session_id: str, proxy_name: str, client_host: str) -> bool:
        """Register a new SSE session with enhanced logging and rate limiting

        Returns:
            bool: True if session was registered successfully, False if rate limited
        """
        with self.session_lock:
            # Check rate limits
            is_allowed, deny_reason = self._check_rate_limits(proxy_name, client_host)
            if not is_allowed:
                logger.warning(f"🚫 SESSION REGISTRATION DENIED: {session_id}")
                logger.warning(f"   📍 Proxy: {proxy_name} | Client: {client_host}")
                logger.warning(f"   ⚠️ Reason: {deny_reason}")
                # Don't record failed session attempts in history to prevent accumulation
                return False

            # Check for duplicate sessions
            if session_id in self.sessions:
                existing_session = self.sessions[session_id]
                logger.warning(f"🔄 DUPLICATE SESSION DETECTED: {session_id}")
                logger.warning(f"   📍 Existing: proxy={existing_session.proxy_name}, client={existing_session.client_host}, age={time.time() - existing_session.created_at:.2f}s")
                logger.warning(f"   📍 New: proxy={proxy_name}, client={client_host}")
                logger.warning(f"   🧹 Replacing existing session")

            # Record session creation time for rate limiting ONLY for successful registrations
            current_time = time.time()
            if client_host not in self._client_session_history:
                self._client_session_history[client_host] = []
            self._client_session_history[client_host].append(current_time)

            session = SSESession(
                session_id=session_id,
                proxy_name=proxy_name,
                client_host=client_host,
                created_at=current_time
            )
            self.sessions[session_id] = session
            total_sessions = len(self.sessions)

            # Optimized logging - reduce noise for normal operations
            if total_sessions <= 10 or total_sessions % 10 == 0:
                # Log every session when count is low, or every 10th session when high
                logger.info(f"🔗 SSE SESSION REGISTERED: {session_id[:8]}...")
                logger.info(f"   📍 Proxy: {proxy_name} | Client: {client_host}")
                logger.info(f"   📊 Total Active Sessions: {total_sessions}")
            else:
                # Minimal logging for high-frequency registrations
                logger.debug(f"🔗 Session registered: {session_id[:8]}... (proxy: {proxy_name}, total: {total_sessions})")

            # Log session distribution by proxy (only when needed)
            proxy_counts = {}
            for sid, sess in self.sessions.items():
                proxy = sess.proxy_name
                proxy_counts[proxy] = proxy_counts.get(proxy, 0) + 1

            # Only log distribution if there are multiple proxies or high session count
            if len(proxy_counts) > 1 or total_sessions > 20:
                logger.debug(f"   📈 Session Distribution: {proxy_counts}")

            # Warn if approaching limits (using configurable threshold)
            client_session_count = len(self._client_session_history.get(client_host, []))
            proxy_session_count = proxy_counts.get(proxy_name, 0)

            client_warning_threshold = int(self.rate_limit_config.max_sessions_per_client * self.rate_limit_config.warning_threshold)
            proxy_warning_threshold = int(self.rate_limit_config.max_sessions_per_proxy * self.rate_limit_config.warning_threshold)

            if client_session_count >= client_warning_threshold:
                logger.warning(f"   ⚠️ Client {client_host} approaching session limit: {client_session_count}/{self.rate_limit_config.max_sessions_per_client}")

            if proxy_session_count >= proxy_warning_threshold:
                logger.warning(f"   ⚠️ Proxy {proxy_name} approaching session limit: {proxy_session_count}/{self.rate_limit_config.max_sessions_per_proxy}")

            return True

    def has_session(self, session_id: str) -> bool:
        """Check if a session exists"""
        with self.session_lock:
            return session_id in self.sessions

    def unregister_session(self, session_id: str) -> None:
        """Unregister an SSE session with optimized logging"""
        with self.session_lock:
            if session_id in self.sessions:
                session = self.sessions.pop(session_id)
                session_age = time.time() - session.created_at
                remaining_sessions = len(self.sessions)
                pending_messages = len(session.pending_messages)

                # Optimized logging based on session characteristics
                should_log_details = (
                    remaining_sessions <= 10 or  # Low session count
                    remaining_sessions % 10 == 0 or  # Every 10th session
                    pending_messages > 0 or  # Had pending messages
                    session_age < 1.0 or  # Very short session
                    not session.is_initialized  # Never initialized
                )

                if should_log_details:
                    logger.info(f"🔌 SSE SESSION UNREGISTERED: {session_id[:8]}...")
                    logger.info(f"   📍 Proxy: {session.proxy_name} | Client: {session.client_host}")
                    logger.info(f"   ⏱️ Session Age: {session_age:.2f}s | Pending Messages: {pending_messages}")
                    logger.info(f"   📊 Remaining Active Sessions: {remaining_sessions}")
                else:
                    logger.debug(f"🔌 Session unregistered: {session_id[:8]}... (age: {session_age:.1f}s, remaining: {remaining_sessions})")

                # Always warn about potential issues
                if pending_messages > 0:
                    logger.warning(f"   ⚠️ Session {session_id[:8]}... had {pending_messages} undelivered messages")
                if session_age < 1.0:
                    logger.warning(f"   ⚠️ Very short session duration: {session_age:.3f}s - possible connection issue")
                if not session.is_initialized and session_age > 30:
                    logger.warning(f"   ⚠️ Session {session_id[:8]}... never initialized after {session_age:.1f}s")
            else:
                logger.warning(f"🔍 Attempted to unregister non-existent session: {session_id[:8]}...")

    def get_session(self, session_id: str) -> Optional[SSESession]:
        """Get session by ID"""
        with self.session_lock:
            session = self.sessions.get(session_id)
            if session:
                session.last_activity = time.time()
            return session

    def add_message(self, session_id: str, message: Dict[str, Any], priority: bool = False) -> bool:
        """Add a message to session's pending messages queue

        Args:
            session_id: Session ID
            message: Message to add
            priority: If True, add to front of queue

        Returns:
            bool: True if message was added successfully
        """
        with self.session_lock:
            session = self.sessions.get(session_id)
            if session:
                pending_msg = PendingMessage(
                    message=message,
                    timestamp=time.time()
                )

                if priority:
                    session.pending_messages.appendleft(pending_msg)
                else:
                    session.pending_messages.append(pending_msg)

                session.last_activity = time.time()
                logger.debug(f"Added message to session {session_id}: {message.get('method', 'response')}")
                return True
            return False

    def get_pending_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get and clear pending messages for a session"""
        with self.session_lock:
            session = self.sessions.get(session_id)
            if session:
                messages = []
                current_time = time.time()

                # Process messages, removing expired ones
                while session.pending_messages:
                    pending_msg = session.pending_messages.popleft()

                    # Check if message has expired
                    if current_time - pending_msg.timestamp > pending_msg.timeout:
                        logger.warning(f"Message expired in session {session_id}: {pending_msg.message.get('method', 'response')}")
                        continue

                    messages.append(pending_msg.message)

                if messages:
                    session.last_activity = time.time()

                return messages
            return []

    def cleanup_expired_sessions(self, session_timeout: int = 300) -> int:
        """Clean up expired sessions with intelligent activity-based cleanup

        Args:
            session_timeout: Session timeout in seconds (default: 300 = 5 minutes)
        """
        return self.smart_cleanup_sessions(session_timeout)

    def smart_cleanup_sessions(self, session_timeout: int = 300) -> int:
        """Intelligent session cleanup based on activity patterns and resource usage

        Args:
            session_timeout: Base session timeout in seconds

        Returns:
            Number of sessions cleaned up
        """
        expired_sessions = []
        current_time = time.time()

        # Adaptive thresholds based on system load
        total_sessions = len(self.sessions)
        max_pending_messages = 100

        # Adjust cleanup aggressiveness based on session count
        if total_sessions > 100:
            # More aggressive cleanup when many sessions
            activity_threshold = session_timeout * 0.5  # 2.5 minutes instead of 5
            max_pending_messages = 50
        elif total_sessions > 50:
            activity_threshold = session_timeout * 0.75  # 3.75 minutes
            max_pending_messages = 75
        else:
            activity_threshold = session_timeout  # Normal timeout

        cleanup_stats = {
            "total_checked": 0,
            "expired_by_inactivity": 0,
            "expired_by_age": 0,
            "expired_by_pending_overflow": 0,
            "expired_by_initialization_timeout": 0
        }

        with self.session_lock:
            for session_id, session in self.sessions.items():
                cleanup_stats["total_checked"] += 1
                should_expire = False
                expire_reason = ""

                session_age = current_time - session.created_at
                activity_age = current_time - session.last_activity
                pending_count = len(session.pending_messages)

                # 1. Check activity-based timeout
                if activity_age > activity_threshold:
                    should_expire = True
                    expire_reason = f"inactivity ({activity_age:.1f}s > {activity_threshold:.1f}s)"
                    cleanup_stats["expired_by_inactivity"] += 1

                # 2. Check absolute age timeout (prevent very old sessions)
                elif session_age > session_timeout * 3:  # 15 minutes max age
                    should_expire = True
                    expire_reason = f"maximum age ({session_age:.1f}s > {session_timeout * 3:.1f}s)"
                    cleanup_stats["expired_by_age"] += 1

                # 3. Check pending message overflow
                elif pending_count > max_pending_messages:
                    should_expire = True
                    expire_reason = f"pending message overflow ({pending_count} > {max_pending_messages})"
                    cleanup_stats["expired_by_pending_overflow"] += 1

                # 4. Check uninitialized sessions that are too old
                elif not session.is_initialized and session_age > 60:  # 1 minute for initialization
                    should_expire = True
                    expire_reason = f"initialization timeout ({session_age:.1f}s, not initialized)"
                    cleanup_stats["expired_by_initialization_timeout"] += 1

                if should_expire:
                    expired_sessions.append((session_id, session, expire_reason))

            # Perform cleanup with detailed logging
            for session_id, session, reason in expired_sessions:
                self.sessions.pop(session_id)

                # Reduce log noise - only log significant cleanups
                if cleanup_stats["total_checked"] <= 10 or len(expired_sessions) <= 3:
                    logger.info(f"🧹 Cleaned up session {session_id[:8]}... (proxy: {session.proxy_name}, reason: {reason})")
                elif len(expired_sessions) <= 10:
                    logger.debug(f"🧹 Cleaned up session {session_id[:8]}... (reason: {reason})")

            # Summary logging for bulk cleanups
            if len(expired_sessions) > 3:
                logger.info(f"🧹 Bulk cleanup completed: {len(expired_sessions)} sessions removed")
                logger.info(f"   📊 Cleanup breakdown: {cleanup_stats}")

        return len(expired_sessions)

    def get_session_count(self) -> int:
        """Get total number of active sessions"""
        with self.session_lock:
            return len(self.sessions)

    def get_session_stats(self) -> Dict[str, Any]:
        """Get comprehensive session statistics for monitoring and diagnostics"""
        with self.session_lock:
            current_time = time.time()
            stats = {
                "total_sessions": len(self.sessions),
                "sessions_by_proxy": {},
                "sessions_by_client": {},
                "sessions_by_age": {"<1min": 0, "1-5min": 0, "5-30min": 0, ">30min": 0},
                "sessions_by_activity": {"<1min": 0, "1-5min": 0, "5-30min": 0, ">30min": 0},
                "sessions_by_status": {"initialized": 0, "uninitialized": 0},
                "sessions_with_pending_messages": 0,
                "total_pending_messages": 0,
                "oldest_session_age": 0,
                "newest_session_age": 0,
                "average_session_age": 0,
                "average_activity_age": 0,
                "sessions_detail": [],
                "health_metrics": {
                    "sessions_needing_cleanup": 0,
                    "sessions_with_high_pending": 0,
                    "uninitialized_old_sessions": 0,
                    "memory_usage_estimate": 0
                },
                "rate_limiting": {
                    "max_sessions_per_client": self.rate_limit_config.max_sessions_per_client,
                    "max_sessions_per_proxy": self.rate_limit_config.max_sessions_per_proxy,
                    "session_creation_window": self.rate_limit_config.session_creation_window,
                    "burst_allowance": self.rate_limit_config.burst_allowance,
                    "adaptive_scaling": self.rate_limit_config.adaptive_scaling,
                    "warning_threshold": self.rate_limit_config.warning_threshold,
                    "active_client_histories": len(self._client_session_history),
                    "clients_near_limit": [],
                    "cache_size": len(self._rate_limit_cache)
                },
                "performance_metrics": {
                    "cleanup_interval": self._cleanup_interval,
                    "session_timeout": self._session_timeout,
                    "cleanup_running": self._running
                }
            }

            if not self.sessions:
                return stats

            session_ages = []
            activity_ages = []

            for session_id, session in self.sessions.items():
                session_age = current_time - session.created_at
                activity_age = current_time - session.last_activity
                pending_count = len(session.pending_messages)

                session_ages.append(session_age)
                activity_ages.append(activity_age)

                # Count by proxy
                proxy = session.proxy_name
                stats["sessions_by_proxy"][proxy] = stats["sessions_by_proxy"].get(proxy, 0) + 1

                # Count by client
                client = session.client_host
                stats["sessions_by_client"][client] = stats["sessions_by_client"].get(client, 0) + 1

                # Count by age
                if session_age < 60:
                    stats["sessions_by_age"]["<1min"] += 1
                elif session_age < 300:
                    stats["sessions_by_age"]["1-5min"] += 1
                elif session_age < 1800:
                    stats["sessions_by_age"]["5-30min"] += 1
                else:
                    stats["sessions_by_age"][">30min"] += 1

                # Count by activity
                if activity_age < 60:
                    stats["sessions_by_activity"]["<1min"] += 1
                elif activity_age < 300:
                    stats["sessions_by_activity"]["1-5min"] += 1
                elif activity_age < 1800:
                    stats["sessions_by_activity"]["5-30min"] += 1
                else:
                    stats["sessions_by_activity"][">30min"] += 1

                # Count by status
                if session.is_initialized:
                    stats["sessions_by_status"]["initialized"] += 1
                else:
                    stats["sessions_by_status"]["uninitialized"] += 1

                # Count pending messages
                if pending_count > 0:
                    stats["sessions_with_pending_messages"] += 1
                    stats["total_pending_messages"] += pending_count

                # Health metrics
                if activity_age > self._session_timeout:
                    stats["health_metrics"]["sessions_needing_cleanup"] += 1
                if pending_count > 50:
                    stats["health_metrics"]["sessions_with_high_pending"] += 1
                if not session.is_initialized and session_age > 60:
                    stats["health_metrics"]["uninitialized_old_sessions"] += 1

                # Estimate memory usage (rough calculation)
                stats["health_metrics"]["memory_usage_estimate"] += (
                    200 +  # Base session object
                    pending_count * 100 +  # Pending messages
                    len(session_id) * 2  # Session ID storage
                )

                # Session detail
                stats["sessions_detail"].append({
                    "session_id": session_id,  # Full session ID for debugging
                    "session_id_short": session_id[:8] + "...",  # Truncated for display
                    "proxy_name": session.proxy_name,
                    "client_host": session.client_host,
                    "age_seconds": round(session_age, 1),
                    "last_activity_seconds": round(activity_age, 1),
                    "pending_messages": pending_count,
                    "is_initialized": session.is_initialized,
                    "health_status": self._get_session_health_status(session, current_time)
                })

            # Calculate averages
            stats["oldest_session_age"] = round(max(session_ages), 1) if session_ages else 0
            stats["newest_session_age"] = round(min(session_ages), 1) if session_ages else 0
            stats["average_session_age"] = round(sum(session_ages) / len(session_ages), 1) if session_ages else 0
            stats["average_activity_age"] = round(sum(activity_ages) / len(activity_ages), 1) if activity_ages else 0

            # Add rate limiting statistics
            cutoff_time = current_time - self.rate_limit_config.session_creation_window
            for client_ip, timestamps in self._client_session_history.items():
                recent_sessions = [t for t in timestamps if t > cutoff_time]
                warning_threshold = int(self.rate_limit_config.max_sessions_per_client * self.rate_limit_config.warning_threshold)
                if len(recent_sessions) >= warning_threshold:
                    stats["rate_limiting"]["clients_near_limit"].append({
                        "client": client_ip,
                        "recent_sessions": len(recent_sessions),
                        "limit": self.rate_limit_config.max_sessions_per_client,
                        "warning_threshold": warning_threshold
                    })

            return stats

    def _get_session_health_status(self, session: SSESession, current_time: float) -> str:
        """Get health status for a session

        Args:
            session: Session to check
            current_time: Current timestamp

        Returns:
            Health status string
        """
        session_age = current_time - session.created_at
        activity_age = current_time - session.last_activity
        pending_count = len(session.pending_messages)

        # Check for critical issues
        if not session.is_initialized and session_age > 60:
            return "critical_uninitialized"
        if pending_count > 100:
            return "critical_pending_overflow"
        if activity_age > self._session_timeout:
            return "critical_inactive"

        # Check for warnings
        if pending_count > 50:
            return "warning_high_pending"
        if activity_age > self._session_timeout * 0.8:
            return "warning_inactive"
        if not session.is_initialized and session_age > 30:
            return "warning_slow_init"

        # Normal status
        if session.is_initialized:
            return "healthy"
        else:
            return "initializing"

    def get_session_health_summary(self) -> Dict[str, Any]:
        """Get a summary of session health metrics

        Returns:
            Health summary with recommendations
        """
        with self.session_lock:
            current_time = time.time()
            health_summary = {
                "total_sessions": len(self.sessions),
                "healthy_sessions": 0,
                "warning_sessions": 0,
                "critical_sessions": 0,
                "recommendations": [],
                "status_breakdown": {}
            }

            status_counts = {}

            for session in self.sessions.values():
                status = self._get_session_health_status(session, current_time)
                status_counts[status] = status_counts.get(status, 0) + 1

                if status.startswith("critical"):
                    health_summary["critical_sessions"] += 1
                elif status.startswith("warning"):
                    health_summary["warning_sessions"] += 1
                else:
                    health_summary["healthy_sessions"] += 1

            health_summary["status_breakdown"] = status_counts

            # Generate recommendations
            if health_summary["critical_sessions"] > 0:
                health_summary["recommendations"].append("Immediate cleanup recommended for critical sessions")
            if health_summary["warning_sessions"] > health_summary["total_sessions"] * 0.3:
                health_summary["recommendations"].append("Consider reducing session timeout or increasing cleanup frequency")
            if status_counts.get("critical_pending_overflow", 0) > 0:
                health_summary["recommendations"].append("Check for message delivery issues")
            if status_counts.get("critical_uninitialized", 0) > 0:
                health_summary["recommendations"].append("Investigate initialization failures")

            return health_summary

    def get_rate_limit_violation_stats(self) -> Dict[str, Any]:
        """Get comprehensive rate limit violation statistics

        Returns:
            Violation statistics and analysis
        """
        current_time = time.time()
        cutoff_time = current_time - self._violation_window

        stats = {
            "total_clients_with_violations": len(self._rate_limit_violations),
            "total_violations_1h": 0,
            "violations_by_type": {},
            "violations_by_severity": {},
            "violations_by_client": {},
            "top_violating_clients": [],
            "violation_trends": {
                "last_5min": 0,
                "last_15min": 0,
                "last_30min": 0,
                "last_1h": 0
            },
            "recommendations": []
        }

        all_violations = []

        # Collect and analyze all violations
        for client_host, violations in self._rate_limit_violations.items():
            # Filter recent violations
            recent_violations = [v for v in violations if v["timestamp"] > cutoff_time]

            if not recent_violations:
                continue

            stats["violations_by_client"][client_host] = {
                "count": len(recent_violations),
                "latest_violation": recent_violations[-1]["timestamp"],
                "violation_types": {},
                "severity_breakdown": {}
            }

            for violation in recent_violations:
                all_violations.append(violation)

                # Count by type
                v_type = violation["violation_type"]
                stats["violations_by_type"][v_type] = stats["violations_by_type"].get(v_type, 0) + 1
                stats["violations_by_client"][client_host]["violation_types"][v_type] = \
                    stats["violations_by_client"][client_host]["violation_types"].get(v_type, 0) + 1

                # Count by severity
                severity = violation["severity"]
                stats["violations_by_severity"][severity] = stats["violations_by_severity"].get(severity, 0) + 1
                stats["violations_by_client"][client_host]["severity_breakdown"][severity] = \
                    stats["violations_by_client"][client_host]["severity_breakdown"].get(severity, 0) + 1

        stats["total_violations_1h"] = len(all_violations)

        # Calculate time-based trends
        time_windows = [
            ("last_5min", 300),
            ("last_15min", 900),
            ("last_30min", 1800),
            ("last_1h", 3600)
        ]

        for window_name, window_seconds in time_windows:
            window_cutoff = current_time - window_seconds
            stats["violation_trends"][window_name] = len([
                v for v in all_violations if v["timestamp"] > window_cutoff
            ])

        # Generate top violating clients
        client_violation_counts = [
            (client, data["count"])
            for client, data in stats["violations_by_client"].items()
        ]
        stats["top_violating_clients"] = sorted(
            client_violation_counts,
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10

        # Generate recommendations
        if stats["total_violations_1h"] > 50:
            stats["recommendations"].append("High violation rate detected - consider adjusting rate limits")

        if stats["violations_by_severity"].get("critical", 0) > 0:
            stats["recommendations"].append("Critical violations detected - immediate investigation recommended")

        if len(stats["top_violating_clients"]) > 0:
            top_client, top_count = stats["top_violating_clients"][0]
            if top_count > 10:
                stats["recommendations"].append(f"Client {top_client} has {top_count} violations - consider blocking or investigation")

        return stats

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limiting status for monitoring dashboard

        Returns:
            Current rate limiting status and metrics
        """
        current_time = time.time()

        with self.session_lock:
            # Basic session counts
            total_sessions = len(self.sessions)
            sessions_by_proxy = {}
            sessions_by_client = {}

            for session in self.sessions.values():
                # Count by proxy
                proxy = session.proxy_name
                sessions_by_proxy[proxy] = sessions_by_proxy.get(proxy, 0) + 1

                # Count by client
                client = session.client_host
                sessions_by_client[client] = sessions_by_client.get(client, 0) + 1

            # Rate limit utilization
            max_client_sessions = max(sessions_by_client.values()) if sessions_by_client else 0
            max_proxy_sessions = max(sessions_by_proxy.values()) if sessions_by_proxy else 0

            client_utilization = (max_client_sessions / self.rate_limit_config.max_sessions_per_client) * 100
            proxy_utilization = (max_proxy_sessions / self.rate_limit_config.max_sessions_per_proxy) * 100

            # Recent violations
            violation_stats = self.get_rate_limit_violation_stats()

            status = {
                "timestamp": current_time,
                "rate_limits": {
                    "max_sessions_per_client": self.rate_limit_config.max_sessions_per_client,
                    "max_sessions_per_proxy": self.rate_limit_config.max_sessions_per_proxy,
                    "session_creation_window": self.rate_limit_config.session_creation_window,
                    "adaptive_scaling": self.rate_limit_config.adaptive_scaling
                },
                "current_usage": {
                    "total_sessions": total_sessions,
                    "sessions_by_proxy": sessions_by_proxy,
                    "sessions_by_client": sessions_by_client,
                    "max_client_sessions": max_client_sessions,
                    "max_proxy_sessions": max_proxy_sessions,
                    "client_utilization_percent": round(client_utilization, 1),
                    "proxy_utilization_percent": round(proxy_utilization, 1)
                },
                "violations": {
                    "total_1h": violation_stats["total_violations_1h"],
                    "last_5min": violation_stats["violation_trends"]["last_5min"],
                    "clients_with_violations": violation_stats["total_clients_with_violations"],
                    "by_severity": violation_stats["violations_by_severity"]
                },
                "health_status": self._get_rate_limit_health_status(client_utilization, proxy_utilization, violation_stats),
                "cache_stats": {
                    "cache_size": len(self._rate_limit_cache),
                    "cache_ttl": self._cache_ttl
                }
            }

            return status

    def _get_rate_limit_health_status(self, client_utilization: float, proxy_utilization: float, violation_stats: Dict[str, Any]) -> str:
        """Determine overall rate limiting health status

        Args:
            client_utilization: Client utilization percentage
            proxy_utilization: Proxy utilization percentage
            violation_stats: Violation statistics

        Returns:
            Health status (healthy, warning, critical)
        """
        # Check for critical conditions
        if (client_utilization > 90 or proxy_utilization > 90 or
            violation_stats["violations_by_severity"].get("critical", 0) > 0 or
            violation_stats["violation_trends"]["last_5min"] > 10):
            return "critical"

        # Check for warning conditions
        if (client_utilization > 70 or proxy_utilization > 70 or
            violation_stats["total_violations_1h"] > 20 or
            violation_stats["violation_trends"]["last_5min"] > 5):
            return "warning"

        return "healthy"

    def clear_rate_limit_history(self, client_host: str = None) -> int:
        """Clear rate limiting history for a specific client or all clients

        Args:
            client_host: Specific client to clear, or None to clear all

        Returns:
            Number of client histories cleared
        """
        with self.session_lock:
            if client_host:
                if client_host in self._client_session_history:
                    del self._client_session_history[client_host]
                    logger.info(f"🧹 Cleared rate limit history for client: {client_host}")
                    return 1
                return 0
            else:
                cleared_count = len(self._client_session_history)
                self._client_session_history.clear()
                logger.info(f"🧹 Cleared rate limit history for all clients: {cleared_count} entries")
                return cleared_count

    def get_sessions_by_proxy(self, proxy_name: str) -> List[str]:
        """Get all session IDs for a specific proxy"""
        with self.session_lock:
            return [
                session_id for session_id, session in self.sessions.items()
                if session.proxy_name == proxy_name
            ]

    def broadcast_to_proxy(self, proxy_name: str, message: Dict[str, Any]) -> int:
        """Broadcast a message to all sessions of a specific proxy

        Returns:
            int: Number of sessions the message was sent to
        """
        session_ids = self.get_sessions_by_proxy(proxy_name)
        sent_count = 0

        for session_id in session_ids:
            if self.add_message(session_id, message):
                sent_count += 1

        logger.info(f"Broadcasted message to {sent_count} sessions for proxy {proxy_name}")
        return sent_count

    async def handle_mcp_message(self, session_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP message and return response"""
        session = self.get_session(session_id)
        if not session:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32001,
                    "message": "Session not found"
                }
            }

        try:
            # Handle different MCP methods
            method = message.get("method")
            message_id = message.get("id")

            if method == "initialize":
                return self._handle_initialize(session, message)
            elif method == "tools/list":
                return self._handle_tools_list(session, message)
            elif method == "tools/call":
                return await self._handle_tool_call(session, message)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

        except Exception as e:
            logger.error(f"Error handling MCP message in session {session_id}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    def _handle_initialize(self, session: SSESession, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        session.is_initialized = True

        # Get proxy instructions using the same logic as dynamic_proxy.py
        proxy_instructions = self._get_proxy_instructions(session.proxy_name)

        # Build serverInfo (per MCP v2025-03-26 spec: only name and version)
        server_info = {
            "name": f"MCP-Dock-{session.proxy_name}",
            "version": "1.0.0"
        }

        # Build result object
        result = {
            "protocolVersion": "2025-03-26",  # Updated to latest MCP version
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": False},
                "logging": {}  # Required by MCP Inspector
            },
            "serverInfo": server_info
        }

        # Add instructions as top-level field (per MCP v2025-03-26 spec)
        if proxy_instructions and proxy_instructions.strip():
            result["instructions"] = proxy_instructions.strip()

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": result
        }

    def _get_proxy_instructions(self, proxy_name: str) -> str:
        """Get proxy instructions using the same logic as dynamic_proxy.py

        Args:
            proxy_name: Proxy name

        Returns:
            str: Proxy instructions or empty string if none found
        """
        try:
            # Get proxy manager
            from mcp_dock.core.mcp_proxy import McpProxyManager
            proxy_manager = McpProxyManager.get_instance()

            # Get proxy instance directly to access config
            proxy_instance = proxy_manager.proxies.get(proxy_name)
            if not proxy_instance:
                logger.warning(f"Proxy instance {proxy_name} not found")
                return ""

            # Check if proxy has custom instructions configured
            if proxy_instance.config.instructions and proxy_instance.config.instructions.strip():
                logger.debug(f"Using custom instructions for proxy {proxy_name}")
                return proxy_instance.config.instructions.strip()

            # If no custom instructions, try to inherit from target service
            server_name = proxy_instance.config.server_name
            if not proxy_manager.mcp_manager or server_name not in proxy_manager.mcp_manager.servers:
                logger.debug(f"Target service {server_name} not found for proxy {proxy_name}")
                return ""

            target_server = proxy_manager.mcp_manager.servers[server_name]

            # First priority: server_info instructions from MCP server
            if hasattr(target_server, 'server_info') and target_server.server_info:
                server_instructions = target_server.server_info.get('instructions', '') or ''
                if server_instructions and server_instructions.strip():
                    logger.debug(f"Using server_info instructions for proxy {proxy_name}")
                    return server_instructions.strip()

            # Second priority: config instructions from service configuration
            if target_server.config.instructions:
                config_instructions = target_server.config.instructions.strip()
                if config_instructions:
                    logger.debug(f"Using config instructions for proxy {proxy_name}")
                    return config_instructions

            logger.debug(f"No instructions found for proxy {proxy_name}")
            return ""

        except Exception as e:
            logger.error(f"Error getting instructions for proxy {proxy_name}: {e}")
            return ""

    def _handle_tools_list(self, session: SSESession, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/list request"""
        # Get tools from proxy manager
        from mcp_dock.core.mcp_proxy import McpProxyManager
        proxy_manager = McpProxyManager.get_instance()
        
        proxy_instance = proxy_manager.proxies.get(session.proxy_name)
        tools_list = proxy_instance.tools if proxy_instance else []
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": tools_list
            }
        }
    
    async def _handle_tool_call(self, session: SSESession, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/call request"""
        try:
            # Get proxy and service managers
            from mcp_dock.core.mcp_proxy import McpProxyManager
            proxy_manager = McpProxyManager.get_instance()

            # Use proxy manager to call the tool
            response = await proxy_manager.proxy_request(session.proxy_name, message)
            return response

        except Exception as e:
            logger.error(f"Error handling tool call in session {session.session_id}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> None:
        """Clean up old sessions"""
        current_time = time.time()
        with self.session_lock:
            expired_sessions = [
                session_id for session_id, session in self.sessions.items()
                if current_time - session.created_at > max_age_seconds
            ]
            
            for session_id in expired_sessions:
                self.unregister_session(session_id)
                logger.info(f"Cleaned up expired session {session_id}")
