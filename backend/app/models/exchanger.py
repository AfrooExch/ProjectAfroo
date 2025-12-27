"""
Exchanger Models - V4 Exchanger System
Supports all 14 cryptocurrencies with hold/fee/claim limit logic
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId
from decimal import Decimal


class PyObjectId(str):
    """Custom ObjectId type for Pydantic v2"""
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


# ====================
# Exchanger Deposit Models
# ====================

class ExchangerDeposit(BaseModel):
    """
    Exchanger liquidity deposit wallet
    SEPARATE from regular wallets - different address and private key
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="Discord user ID (exchanger)")
    currency: str = Field(..., description="Currency code (BTC, ETH, SOL, etc.)")

    # Wallet data (SEPARATE from regular V4 wallet)
    wallet_address: str = Field(..., description="Deposit address (unique to exchanger)")
    encrypted_private_key: str = Field(..., description="AES encrypted private key")

    # Balance tracking (all in crypto units)
    balance: str = Field(default="0", description="Confirmed balance (Decimal as string)")
    unconfirmed_balance: str = Field(default="0", description="Unconfirmed balance")
    held: str = Field(default="0", description="Locked for active tickets")
    fee_reserved: str = Field(default="0", description="Reserved for platform fees")

    # Calculated: available = balance - held - fee_reserved

    # Statistics
    total_deposited: str = Field(default="0", description="Lifetime deposits")
    total_withdrawn: str = Field(default="0", description="Lifetime withdrawals")

    # Status
    is_active: bool = Field(default=True, description="Deposit wallet active")
    is_frozen: bool = Field(default=False, description="Frozen by admin")
    frozen_at: Optional[datetime] = None
    frozen_by: Optional[str] = Field(None, description="Admin user ID who froze")
    frozen_reason: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    def get_balance_decimal(self) -> Decimal:
        """Get balance as Decimal"""
        return Decimal(self.balance)

    def get_held_decimal(self) -> Decimal:
        """Get held as Decimal"""
        return Decimal(self.held)

    def get_fee_reserved_decimal(self) -> Decimal:
        """Get fee_reserved as Decimal"""
        return Decimal(self.fee_reserved)

    def get_available_decimal(self) -> Decimal:
        """Calculate available balance"""
        return self.get_balance_decimal() - self.get_held_decimal() - self.get_fee_reserved_decimal()


# ====================
# Hold Models
# ====================

class TicketHold(BaseModel):
    """
    Holds for active tickets
    Locks exchanger funds until ticket is completed/cancelled
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    ticket_id: str = Field(..., description="Ticket ID")
    exchanger_id: str = Field(..., description="Exchanger Discord ID")

    # Hold amounts
    hold_usd: str = Field(..., description="Total USD value held (Decimal as string)")

    # Status
    status: Literal["active", "released", "consumed"] = Field(default="active")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class HoldAllocation(BaseModel):
    """
    Asset allocation for a hold
    Tracks which assets/amounts are locked for a hold
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    hold_id: PyObjectId = Field(..., description="Parent hold ID")

    # Asset details
    currency: str = Field(..., description="Currency code")
    amount: str = Field(..., description="Amount locked (Decimal as string)")

    # USD tracking (at time of hold)
    usd_at_allocation: str = Field(..., description="USD value when locked")
    rate_usd_per_unit: str = Field(..., description="Exchange rate when locked")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# Fee Reservation Models
# ====================

class FeeReservation(BaseModel):
    """
    Platform fee reservations from exchanger deposits
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    ticket_id: str = Field(..., description="Ticket ID")
    exchanger_id: str = Field(..., description="Exchanger Discord ID")

    # Fee amounts
    fee_usd: str = Field(..., description="Total USD fee reserved")

    # Status
    status: Literal["reserved", "collected", "released"] = Field(default="reserved")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    collected_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class FeeAllocation(BaseModel):
    """
    Asset allocation for fee reservation
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    fee_reservation_id: PyObjectId = Field(..., description="Parent fee reservation ID")

    # Asset details
    currency: str = Field(..., description="Currency code")
    amount: str = Field(..., description="Amount reserved (Decimal as string)")

    # USD tracking
    usd_at_reservation: str = Field(..., description="USD value when reserved")
    rate_usd_per_unit: str = Field(..., description="Exchange rate when reserved")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# Exchanger Profile Models
# ====================

class PremadeMessage(BaseModel):
    """Premade message stored by exchanger"""
    name: str = Field(..., description="Name/title of the premade message")
    content: str = Field(..., description="Content of the premade message")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True


class ExchangerProfile(BaseModel):
    """
    Exchanger profile with stats and performance tracking
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="Discord user ID")
    username: str = Field(..., description="Discord username")

    # Statistics
    total_volume_usd: str = Field(default="0", description="Lifetime volume in USD")
    total_trades: int = Field(default=0, description="Total completed trades")

    # Performance
    rating: float = Field(default=0.0, description="Performance rating (0-5)")
    avg_response_time_seconds: Optional[float] = None
    completion_rate: float = Field(default=0.0, description="Percentage of completed vs claimed")

    # Status
    is_active: bool = Field(default=True, description="Exchanger is active")
    is_verified: bool = Field(default=False, description="Verified exchanger")

    # Premade messages for quick responses
    premades: list[PremadeMessage] = Field(default_factory=list, description="Saved premade messages")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_trade_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# Transaction History Model
# ====================

class ExchangerTransaction(BaseModel):
    """
    Exchanger deposit/withdrawal transaction
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="Exchanger Discord ID")
    currency: str = Field(..., description="Currency code")

    # Transaction details
    type: Literal["deposit", "withdrawal"] = Field(..., description="Transaction type")
    amount: str = Field(..., description="Amount (Decimal as string)")

    # Status
    status: Literal["pending", "confirming", "confirmed", "failed"] = Field(default="pending")
    confirmations: int = Field(default=0)

    # Blockchain
    tx_hash: Optional[str] = Field(None, description="Blockchain transaction hash")
    to_address: Optional[str] = Field(None, description="Destination address (for withdrawals)")
    from_address: Optional[str] = Field(None, description="Source address (for deposits)")

    # Fees (for withdrawals)
    network_fee: str = Field(default="0", description="Network fee")
    exchanger_fee: str = Field(default="0", description="Exchanger fee (2%)")

    # Error tracking
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# API Request/Response Models
# ====================

class CreateDepositRequest(BaseModel):
    """Request to create deposit wallet"""
    currency: str = Field(..., description="Currency code (BTC, ETH, etc.)")


class DepositBalanceResponse(BaseModel):
    """Response with deposit balance details"""
    currency: str
    balance: str
    unconfirmed_balance: str
    held: str
    fee_reserved: str
    available: str
    balance_usd: Optional[str] = None
    held_usd: Optional[str] = None
    available_usd: Optional[str] = None
    wallet_address: str


class ClaimLimitResponse(BaseModel):
    """Response with claim limit information"""
    total_deposit_usd: str
    total_held_usd: str
    claim_limit_usd: str
    available_to_claim_usd: str
    claim_limit_multiplier: float


class HoldFundsRequest(BaseModel):
    """Request to hold funds for ticket"""
    ticket_id: str
    ticket_amount_usd: str
    hold_multiplier: float = Field(default=1.0, description="Multiplier for hold amount")


class ReleaseFundsRequest(BaseModel):
    """Request to release held funds"""
    ticket_id: str


class WithdrawRequest(BaseModel):
    """Request to withdraw exchanger funds"""
    currency: str
    amount: str  # "max" or Decimal string
    to_address: str


# ====================
# Exchanger Preference Models
# ====================

class ExchangerPreference(BaseModel):
    """
    Exchanger role preferences for ticket notifications
    Allows exchangers to filter which tickets they get pinged for
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="Exchanger Discord ID")

    # Payment method preferences
    preferred_payment_methods: list[str] = Field(default_factory=list, description="List of payment method values")

    # Currency preferences
    preferred_currencies: list[str] = Field(default_factory=list, description="List of currency codes")

    # Amount range preferences
    min_ticket_amount: Optional[str] = Field(None, description="Minimum ticket amount USD")
    max_ticket_amount: Optional[str] = Field(None, description="Maximum ticket amount USD")

    # Notification settings
    notifications_enabled: bool = Field(default=True, description="Enable ticket notifications")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# Exchanger Question Models
# ====================

class ExchangerQuestion(BaseModel):
    """
    Anonymous question from exchanger to ticket
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    ticket_id: str = Field(..., description="Target ticket ID")
    exchanger_id: str = Field(..., description="Exchanger Discord ID (anonymous to customer)")

    # Question content
    question_text: str = Field(..., description="Question text")
    question_type: str = Field(default="preset", description="preset, custom, alt_payment, alt_amount")

    # For alt_payment questions
    alt_payment_method: Optional[str] = Field(None, description="Alternative payment method offered")

    # For alt_amount questions
    alt_amount_usd: Optional[str] = Field(None, description="Alternative amount offered")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    posted_to_channel: bool = Field(default=False, description="Whether posted to ticket channel")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# API Request/Response Models (Preferences & Questions)
# ====================

class UpdatePreferencesRequest(BaseModel):
    """Request to update exchanger preferences"""
    preferred_payment_methods: Optional[list[str]] = None
    preferred_currencies: Optional[list[str]] = None
    min_ticket_amount: Optional[str] = None
    max_ticket_amount: Optional[str] = None
    notifications_enabled: Optional[bool] = None


class AskQuestionRequest(BaseModel):
    """Request to ask question on ticket"""
    ticket_id: str
    question_text: str
    question_type: str = "preset"  # preset, custom, alt_payment, alt_amount
    alt_payment_method: Optional[str] = None  # For alt_payment
    alt_amount_usd: Optional[str] = None  # For alt_amount
