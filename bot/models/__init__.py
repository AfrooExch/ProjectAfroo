"""
Data Models - Pydantic models matching API responses
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from models.enums import TicketStatus, PayoutMethod, UserStatus, SwapStatus, TransactionType


# =======================
# User Models
# =======================

class User(BaseModel):
    """User data model"""
    id: str = Field(alias="_id")
    discord_id: str
    username: str
    discriminator: str
    avatar: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    status: UserStatus = UserStatus.ACTIVE
    total_volume: float = 0.0
    total_trades: int = 0
    created_at: datetime
    last_seen: Optional[datetime] = None

    class Config:
        populate_by_name = True


class CustomerStats(BaseModel):
    """Customer statistics"""
    total_volume: float
    total_trades: int
    average_trade: float
    highest_trade: float
    monthly_volume: float
    monthly_trades: int
    current_milestone: Optional[str] = None
    first_trade: Optional[datetime] = None
    last_trade: Optional[datetime] = None


class ExchangerStats(BaseModel):
    """Exchanger statistics"""
    total_fees_earned: float
    pending_fees: float
    total_trades: int
    total_volume: float
    average_trade: float
    highest_trade: float
    monthly_trades: int
    monthly_volume: float
    total_claimed_tickets: int
    last_exchange: Optional[datetime] = None


# =======================
# Ticket Models
# =======================

class Ticket(BaseModel):
    """Exchange ticket model"""
    id: str = Field(alias="_id")
    ticket_id: str
    user_id: str
    username: str
    input_currency: str
    output_currency: str
    amount: float
    status: TicketStatus
    tos_agreed: bool = False
    tos_version: Optional[str] = None
    exchanger_id: Optional[str] = None
    exchanger_username: Optional[str] = None
    channel_id: Optional[str] = None
    payout_method: Optional[PayoutMethod] = None
    server_fee: float = 0.0
    exchanger_fee: float = 0.0
    created_at: datetime
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class TicketCreateRequest(BaseModel):
    """Request to create a ticket"""
    input_currency: str
    output_currency: str
    amount: float


class TicketUpdateRequest(BaseModel):
    """Request to update ticket"""
    status: Optional[TicketStatus] = None
    exchanger_id: Optional[str] = None
    payout_method: Optional[PayoutMethod] = None
    tos_agreed: Optional[bool] = None


# =======================
# Wallet Models
# =======================

class Wallet(BaseModel):
    """Wallet model"""
    id: str = Field(alias="_id")
    user_id: str
    asset: str
    address: str
    balance_units: float
    held_units: float
    fee_reserved_units: float
    balance_usd: float
    network: Optional[str] = None
    is_active: bool = True
    is_frozen: bool = False
    created_at: datetime
    last_sync: Optional[datetime] = None

    class Config:
        populate_by_name = True

    @property
    def available_balance(self) -> float:
        """Calculate available balance"""
        return self.balance_units - self.held_units - self.fee_reserved_units


class WalletGenerateRequest(BaseModel):
    """Request to generate wallet"""
    asset: str
    network: Optional[str] = None


class WithdrawRequest(BaseModel):
    """Request to withdraw funds"""
    asset: str
    amount: float
    destination_address: str


# =======================
# Swap Models
# =======================

class Swap(BaseModel):
    """Swap model"""
    id: str = Field(alias="_id")
    user_id: str
    from_asset: str
    to_asset: str
    from_amount: float
    expected_amount: float
    actual_amount: Optional[float] = None
    status: SwapStatus
    provider_id: Optional[str] = None
    deposit_address: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class SwapCreateRequest(BaseModel):
    """Request to create swap"""
    from_asset: str
    to_asset: str
    amount: float


# =======================
# Support Models
# =======================

class SupportTicket(BaseModel):
    """Support ticket model"""
    id: str = Field(alias="_id")
    ticket_id: str
    user_id: str
    ticket_type: str
    subject: str
    description: str
    status: str
    channel_id: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


# =======================
# Transaction Models
# =======================

class Transaction(BaseModel):
    """Transaction model"""
    id: str = Field(alias="_id")
    user_id: str
    asset: str
    amount: float
    transaction_type: TransactionType
    tx_hash: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        populate_by_name = True


# =======================
# API Response Models
# =======================

class APIResponse(BaseModel):
    """Generic API response"""
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None


class PaginatedResponse(BaseModel):
    """Paginated API response"""
    items: List[dict]
    total: int
    page: int
    per_page: int
    pages: int
