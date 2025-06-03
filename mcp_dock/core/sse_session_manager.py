"""
SSE Session Manager for MCP-Dock

Manages SSE sessions for MCP Inspector compatibility.
"""

import asyncio
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

        # Rate limiting for session creation
        self._max_sessions_per_client = 5  # Maximum sessions per client IP
        self._max_sessions_per_proxy = 20  # Maximum sessions per proxy
        self._session_creation_window = 60  # Time window for rate limiting (seconds)
        self._client_session_history: Dict[str, List[float]] = {}  # Track session creation times per client
    
    @classmethod
    def get_instance(cls) -> 'SSESessionManager':
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

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
        """Check if session creation should be rate limited

        Returns:
            tuple[bool, str]: (is_allowed, reason_if_denied)
        """
        current_time = time.time()

        # Clean up old entries in client session history
        cutoff_time = current_time - self._session_creation_window
        for client_ip in list(self._client_session_history.keys()):
            self._client_session_history[client_ip] = [
                timestamp for timestamp in self._client_session_history[client_ip]
                if timestamp > cutoff_time
            ]
            if not self._client_session_history[client_ip]:
                del self._client_session_history[client_ip]

        # Check sessions per client limit
        client_sessions = self._client_session_history.get(client_host, [])
        if len(client_sessions) >= self._max_sessions_per_client:
            return False, f"Client {client_host} exceeded rate limit ({len(client_sessions)}/{self._max_sessions_per_client} sessions in {self._session_creation_window}s)"

        # Check sessions per proxy limit
        proxy_session_count = sum(1 for session in self.sessions.values() if session.proxy_name == proxy_name)
        if proxy_session_count >= self._max_sessions_per_proxy:
            return False, f"Proxy {proxy_name} exceeded session limit ({proxy_session_count}/{self._max_sessions_per_proxy} active sessions)"

        return True, ""

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

            logger.info(f"🔗 SSE SESSION REGISTERED: {session_id}")
            logger.info(f"   📍 Proxy: {proxy_name} | Client: {client_host}")
            logger.info(f"   📊 Total Active Sessions: {total_sessions}")

            # Log session distribution by proxy
            proxy_counts = {}
            for sid, sess in self.sessions.items():
                proxy = sess.proxy_name
                proxy_counts[proxy] = proxy_counts.get(proxy, 0) + 1

            logger.debug(f"   📈 Session Distribution: {proxy_counts}")

            # Warn if approaching limits
            client_session_count = len(self._client_session_history.get(client_host, []))
            proxy_session_count = proxy_counts.get(proxy_name, 0)

            if client_session_count >= self._max_sessions_per_client * 0.8:
                logger.warning(f"   ⚠️ Client {client_host} approaching session limit: {client_session_count}/{self._max_sessions_per_client}")

            if proxy_session_count >= self._max_sessions_per_proxy * 0.8:
                logger.warning(f"   ⚠️ Proxy {proxy_name} approaching session limit: {proxy_session_count}/{self._max_sessions_per_proxy}")

            return True

    def has_session(self, session_id: str) -> bool:
        """Check if a session exists"""
        with self.session_lock:
            return session_id in self.sessions

    def unregister_session(self, session_id: str) -> None:
        """Unregister an SSE session with enhanced logging"""
        with self.session_lock:
            if session_id in self.sessions:
                session = self.sessions.pop(session_id)
                session_age = time.time() - session.created_at
                remaining_sessions = len(self.sessions)
                pending_messages = len(session.pending_messages)

                logger.info(f"🔌 SSE SESSION UNREGISTERED: {session_id}")
                logger.info(f"   📍 Proxy: {session.proxy_name} | Client: {session.client_host}")
                logger.info(f"   ⏱️ Session Age: {session_age:.2f}s | Pending Messages: {pending_messages}")
                logger.info(f"   📊 Remaining Active Sessions: {remaining_sessions}")

                # Warn about potential issues
                if pending_messages > 0:
                    logger.warning(f"   ⚠️ Session had {pending_messages} undelivered messages")
                if session_age < 1.0:
                    logger.warning(f"   ⚠️ Very short session duration: {session_age:.3f}s - possible connection issue")
            else:
                logger.warning(f"🔍 Attempted to unregister non-existent session: {session_id}")

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
        """Clean up expired sessions and return count of cleaned sessions

        Args:
            session_timeout: Session timeout in seconds (default: 300 = 5 minutes)
        """
        expired_sessions = []
        current_time = time.time()

        # Also clean up sessions with too many pending messages (potential memory leak)
        max_pending_messages = 100

        with self.session_lock:
            for session_id, session in self.sessions.items():
                should_expire = False

                # Check timeout
                if current_time - session.last_activity > session_timeout:
                    logger.info(f"Session {session_id} expired due to inactivity ({current_time - session.last_activity:.1f}s)")
                    should_expire = True

                # Check pending message overflow
                if len(session.pending_messages) > max_pending_messages:
                    logger.warning(f"Session {session_id} has too many pending messages ({len(session.pending_messages)}), cleaning up")
                    should_expire = True

                if should_expire:
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                session = self.sessions.pop(session_id)
                logger.info(f"Cleaned up expired session {session_id} for proxy {session.proxy_name}")

        return len(expired_sessions)

    def get_session_count(self) -> int:
        """Get total number of active sessions"""
        with self.session_lock:
            return len(self.sessions)

    def get_session_stats(self) -> Dict[str, Any]:
        """Get detailed session statistics for monitoring"""
        with self.session_lock:
            current_time = time.time()
            stats = {
                "total_sessions": len(self.sessions),
                "sessions_by_proxy": {},
                "sessions_by_client": {},
                "sessions_by_age": {"<1min": 0, "1-5min": 0, "5-30min": 0, ">30min": 0},
                "sessions_by_activity": {"<1min": 0, "1-5min": 0, "5-30min": 0, ">30min": 0},
                "sessions_with_pending_messages": 0,
                "total_pending_messages": 0,
                "oldest_session_age": 0,
                "newest_session_age": 0,
                "sessions_detail": [],
                "rate_limiting": {
                    "max_sessions_per_client": self._max_sessions_per_client,
                    "max_sessions_per_proxy": self._max_sessions_per_proxy,
                    "session_creation_window": self._session_creation_window,
                    "active_client_histories": len(self._client_session_history),
                    "clients_near_limit": []
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

                # Count pending messages
                if pending_count > 0:
                    stats["sessions_with_pending_messages"] += 1
                    stats["total_pending_messages"] += pending_count

                # Session detail
                stats["sessions_detail"].append({
                    "session_id": session_id,  # Full session ID for debugging
                    "session_id_short": session_id[:8] + "...",  # Truncated for display
                    "proxy_name": session.proxy_name,
                    "client_host": session.client_host,
                    "age_seconds": round(session_age, 1),
                    "last_activity_seconds": round(activity_age, 1),
                    "pending_messages": pending_count,
                    "is_initialized": session.is_initialized
                })

            stats["oldest_session_age"] = round(max(session_ages), 1) if session_ages else 0
            stats["newest_session_age"] = round(min(session_ages), 1) if session_ages else 0

            # Add rate limiting statistics
            cutoff_time = current_time - self._session_creation_window
            for client_ip, timestamps in self._client_session_history.items():
                recent_sessions = [t for t in timestamps if t > cutoff_time]
                if len(recent_sessions) >= self._max_sessions_per_client * 0.8:
                    stats["rate_limiting"]["clients_near_limit"].append({
                        "client": client_ip,
                        "recent_sessions": len(recent_sessions),
                        "limit": self._max_sessions_per_client
                    })

            return stats



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
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": False, "listChanged": False},
                    "logging": {}  # Required by MCP Inspector
                },
                "serverInfo": {
                    "name": f"MCP-Dock-{session.proxy_name}",
                    "version": "1.0.0",
                    "instructions": f"MCP-Dock proxy server for {session.proxy_name}. This server provides access to tools from the underlying MCP service through a unified interface."  # Required by MCP Inspector
                }
            }
        }
    
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
