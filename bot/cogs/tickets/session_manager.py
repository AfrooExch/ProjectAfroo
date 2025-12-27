"""
Session Manager for Exchange Ticket Creation
Manages multi-step ticket creation flow with in-memory storage
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ExchangeSession:
    """
    Exchange session data structure
    Represents a user's progress through the ticket creation flow
    """

    def __init__(self, user_id: str):
        self.user_id: str = user_id
        self.send_method: Optional[str] = None
        self.send_crypto: Optional[str] = None
        self.receive_method: Optional[str] = None
        self.receive_crypto: Optional[str] = None
        self.amount_usd: Optional[float] = None
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "user_id": self.user_id,
            "send_method": self.send_method,
            "send_crypto": self.send_crypto,
            "receive_method": self.receive_method,
            "receive_crypto": self.receive_crypto,
            "amount_usd": self.amount_usd,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def is_complete(self) -> bool:
        """Check if all required fields are filled"""
        return all([
            self.send_method,
            self.receive_method,
            self.amount_usd is not None
        ])


class ExchangeSessionManager:
    """
    Manager for exchange ticket creation sessions
    Stores sessions in memory for temporary state during creation flow
    """

    def __init__(self):
        """Initialize session manager with in-memory storage"""
        self.sessions: Dict[str, ExchangeSession] = {}

    def create_session(self, user_id: str) -> ExchangeSession:
        """
        Create new exchange session

        Args:
            user_id: Discord user ID

        Returns:
            New ExchangeSession object
        """
        session = ExchangeSession(user_id)
        self.sessions[user_id] = session
        logger.info(f"Created exchange session for user {user_id}")
        return session

    def get_session(self, user_id: str) -> Optional[ExchangeSession]:
        """
        Get existing exchange session

        Args:
            user_id: Discord user ID

        Returns:
            ExchangeSession if exists, None otherwise
        """
        return self.sessions.get(user_id)

    def update_session(self, user_id: str, **updates) -> ExchangeSession:
        """
        Update exchange session

        Args:
            user_id: Discord user ID
            **updates: Fields to update

        Returns:
            Updated ExchangeSession object
        """
        session = self.sessions.get(user_id)
        if not session:
            session = self.create_session(user_id)

        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.updated_at = datetime.now(timezone.utc)
        logger.info(f"Updated exchange session for user {user_id}: {list(updates.keys())}")
        return session

    def delete_session(self, user_id: str) -> bool:
        """
        Delete exchange session

        Args:
            user_id: Discord user ID

        Returns:
            True if deleted successfully
        """
        if user_id in self.sessions:
            del self.sessions[user_id]
            logger.info(f"Deleted exchange session for user {user_id}")
            return True
        return False

    def get_or_create_session(self, user_id: str) -> ExchangeSession:
        """
        Get existing session or create new one

        Args:
            user_id: Discord user ID

        Returns:
            ExchangeSession object
        """
        session = self.get_session(user_id)
        if session is None:
            session = self.create_session(user_id)
        return session

    def set_send_method(
        self,
        user_id: str,
        send_method: str,
        send_crypto: Optional[str] = None
    ) -> ExchangeSession:
        """
        Set sending payment method

        Args:
            user_id: Discord user ID
            send_method: Payment method ID
            send_crypto: Crypto asset symbol (if crypto)

        Returns:
            Updated ExchangeSession
        """
        return self.update_session(
            user_id,
            send_method=send_method,
            send_crypto=send_crypto
        )

    def set_receive_method(
        self,
        user_id: str,
        receive_method: str,
        receive_crypto: Optional[str] = None
    ) -> ExchangeSession:
        """
        Set receiving payment method

        Args:
            user_id: Discord user ID
            receive_method: Payment method ID
            receive_crypto: Crypto asset symbol (if crypto)

        Returns:
            Updated ExchangeSession
        """
        return self.update_session(
            user_id,
            receive_method=receive_method,
            receive_crypto=receive_crypto
        )

    def set_amount(
        self,
        user_id: str,
        amount_usd: float
    ) -> ExchangeSession:
        """
        Set exchange amount

        Args:
            user_id: Discord user ID
            amount_usd: Amount in USD

        Returns:
            Updated ExchangeSession
        """
        return self.update_session(
            user_id,
            amount_usd=amount_usd
        )

    def clear_session(self, user_id: str) -> bool:
        """
        Clear exchange session (alias for delete)

        Args:
            user_id: Discord user ID

        Returns:
            True if cleared successfully
        """
        return self.delete_session(user_id)
