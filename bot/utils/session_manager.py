"""
Session Manager for V4
Manages temporary user session data for multi-step flows
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages temporary session data for users"""

    def __init__(self):
        self._sessions: Dict[int, Dict[str, Any]] = {}
        self._session_timeout = timedelta(minutes=10)  # Auto-clear after 10 minutes

    def create_session(self, user_id: int, session_type: str = "exchange") -> Dict[str, Any]:
        """Create new session for user"""
        self._sessions[user_id] = {
            "type": session_type,
            "send_method": None,
            "receive_method": None,
            "amount_usd": None,
            "send_crypto": None,  # If send is crypto
            "receive_crypto": None,  # If receive is crypto
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        logger.info(f"Created {session_type} session for user {user_id}")
        return self._sessions[user_id]

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get existing session for user"""
        session = self._sessions.get(user_id)

        if session:
            # Check if session expired
            created = session.get("created_at")
            if created and datetime.now(timezone.utc) - created > self._session_timeout:
                logger.info(f"Session expired for user {user_id}, clearing")
                self.clear_session(user_id)
                return None

        return session

    def update_session(self, user_id: int, **kwargs):
        """Update session data"""
        if user_id in self._sessions:
            self._sessions[user_id].update(kwargs)
            self._sessions[user_id]["updated_at"] = datetime.now(timezone.utc)
            logger.debug(f"Updated session for user {user_id}: {kwargs}")
        else:
            logger.warning(f"Attempted to update non-existent session for user {user_id}")

    def clear_session(self, user_id: int):
        """Clear session data"""
        if user_id in self._sessions:
            del self._sessions[user_id]
            logger.info(f"Cleared session for user {user_id}")

    def has_session(self, user_id: int) -> bool:
        """Check if user has active session"""
        return user_id in self._sessions

    def cleanup_expired_sessions(self):
        """Cleanup all expired sessions"""
        now = datetime.now(timezone.utc)
        expired = [
            user_id
            for user_id, session in self._sessions.items()
            if now - session.get("created_at", now) > self._session_timeout
        ]

        for user_id in expired:
            self.clear_session(user_id)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global session manager instance
session_manager = SessionManager()
