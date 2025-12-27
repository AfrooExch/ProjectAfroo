"""Ticket model"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

from app.models.user import PyObjectId


class TicketMessage(BaseModel):
    """Ticket message subdocument"""

    id: str = Field(default_factory=lambda: str(ObjectId()))
    user_id: PyObjectId
    message: str
    is_internal: bool = False
    attachments: List[dict] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Ticket(BaseModel):
    """Ticket model"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    ticket_number: int

    # Ownership
    user_id: PyObjectId
    partner_id: Optional[PyObjectId] = None
    assigned_to: Optional[PyObjectId] = None

    # Ticket details
    type: str  # 'support', 'dispute', 'kyc', 'report', 'exchange', 'application'
    subject: str
    description: str
    status: str = "open"  # open, awaiting_tos, in_progress, claimed, waiting, resolved, completed, canceled, closed
    priority: str = "medium"  # low, medium, high, critical

    # Related entities
    exchange_id: Optional[PyObjectId] = None
    hold_id: Optional[PyObjectId] = None

    # Discord Thread IDs (new thread-based system)
    client_thread_id: Optional[str] = None      # Discord thread ID for client
    exchanger_thread_id: Optional[str] = None   # Discord thread ID for exchanger
    client_forum_id: Optional[str] = None       # Forum channel ID for client
    exchanger_forum_id: Optional[str] = None    # Forum channel ID for exchanger
    channel_id: Optional[str] = None            # Legacy channel-based system (deprecated)

    # Exchange ticket fields
    send_method: Optional[str] = None  # Payment method for sending (e.g., "paypal", "cashapp")
    send_crypto: Optional[str] = None  # Crypto asset if send_method is crypto (e.g., "BTC", "ETH")
    receive_method: Optional[str] = None  # Payment method for receiving (e.g., "crypto", "zelle")
    receive_crypto: Optional[str] = None  # Crypto asset if receive_method is crypto
    amount_usd: Optional[float] = None  # Exchange amount in USD
    fee_amount: Optional[float] = None  # Fee amount in USD
    fee_percentage: Optional[float] = None  # Fee percentage
    receiving_amount: Optional[float] = None  # Amount user will receive after fee

    # TOS workflow fields (for exchange tickets)
    tos_required: bool = False  # Whether TOS agreement is required
    tos_deadline: Optional[datetime] = None  # Deadline to accept TOS (10 minutes)
    tos_accepted_at: Optional[datetime] = None  # When user agreed to TOS
    tos_ping_count: int = 0  # Number of reminder pings sent
    required_tos_ids: List[str] = []  # List of TOS IDs that need to be agreed to

    # Hold management (new thread-based system)
    hold_created_at: Optional[datetime] = None  # When hold was first created (on TOS accept)
    hold_status: str = "none"  # none, pending, created, released, refunded

    # Payment completion tracking (new thread-based system)
    client_sent_at: Optional[datetime] = None  # When client marked payment as sent
    exchanger_confirmed_receipt_at: Optional[datetime] = None  # When exchanger confirmed receipt
    payout_sent_at: Optional[datetime] = None  # When payout was sent
    payout_method: Optional[str] = None  # "internal", "external"
    payout_txid: Optional[str] = None  # Transaction ID for external payouts
    payout_verified: bool = False  # Blockchain verification status

    # Client risk assessment (new thread-based system)
    client_account_age_days: Optional[int] = None  # Discord account age in days
    client_exchange_count: int = 0  # Number of past exchanges
    client_completion_rate: Optional[float] = None  # Completion rate (0.0 - 1.0)
    client_risk_level: str = "unknown"  # low, medium, high, unknown

    # Messages (embedded subdocuments)
    messages: List[TicketMessage] = []

    # Metadata
    tags: List[str] = []
    satisfaction_rating: Optional[int] = None
    satisfaction_feedback: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True


class TicketCreate(BaseModel):
    """Ticket creation model"""

    type: str
    subject: str
    description: str
    exchange_id: Optional[str] = None

    # Exchange ticket fields (required if type='exchange')
    send_method: Optional[str] = None  # Payment method for sending
    receive_method: Optional[str] = None  # Payment method for receiving
    amount: Optional[float] = None  # Exchange amount


class ExchangeTicketCreate(BaseModel):
    """Exchange ticket creation model"""

    user_id: str
    username: str
    send_method: str
    send_crypto: Optional[str] = None
    receive_method: str
    receive_crypto: Optional[str] = None
    amount_usd: float
    fee_amount: float
    fee_percentage: float
    receiving_amount: float


class TicketMessageCreate(BaseModel):
    """Ticket message creation model"""

    message: str
    is_internal: bool = False


class TicketResponse(BaseModel):
    """Ticket response model"""

    id: str
    ticket_number: int
    type: str
    subject: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
