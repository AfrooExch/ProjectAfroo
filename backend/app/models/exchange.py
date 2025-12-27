"""Exchange model"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

from app.models.user import PyObjectId


class Exchange(BaseModel):
    """Exchange model"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Participants
    creator_id: PyObjectId
    exchanger_id: Optional[PyObjectId] = None
    partner_id: Optional[PyObjectId] = None

    # Exchange details
    type: str  # 'crypto_to_crypto', 'crypto_to_fiat'
    status: str = "pending"  # pending, active, escrow, completed, disputed, cancelled

    # Sender side
    send_currency: str
    send_amount: float
    send_wallet_id: Optional[PyObjectId] = None
    send_tx_hash: Optional[str] = None

    # Receiver side
    receive_currency: str
    receive_amount: float
    receive_wallet_id: Optional[PyObjectId] = None
    receive_tx_hash: Optional[str] = None

    # Rates & fees
    exchange_rate: float
    platform_fee_percent: float
    platform_fee_amount: float
    exchanger_fee_percent: Optional[float] = None
    exchanger_fee_amount: Optional[float] = None
    partner_fee_percent: Optional[float] = None
    partner_fee_amount: Optional[float] = None

    # Escrow
    escrow_address: Optional[str] = None
    escrow_locked_at: Optional[datetime] = None
    escrow_released_at: Optional[datetime] = None

    # Metadata
    notes: Optional[str] = None
    risk_score: int = 0
    requires_kyc: bool = False
    auto_accept: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True


class ExchangeCreate(BaseModel):
    """Exchange creation model"""

    send_currency: str
    send_amount: float
    receive_currency: str
    receive_amount: float
    notes: Optional[str] = None


class ExchangeResponse(BaseModel):
    """Exchange response model"""

    id: str
    status: str
    type: str
    send_currency: str
    send_amount: float
    receive_currency: str
    receive_amount: float
    exchange_rate: float
    platform_fee_amount: float
    created_at: datetime
    expires_at: Optional[datetime] = None
