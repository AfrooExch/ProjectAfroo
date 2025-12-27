"""
Wallet System Database Models
Defines MongoDB schemas for wallets, balances, transactions, and profit holds
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from decimal import Decimal
from bson import ObjectId


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
# Supported Currencies
# ====================

SUPPORTED_CURRENCIES = [
    "BTC", "LTC", "ETH", "SOL",
    "USDC-SOL", "USDC-ETH",
    "USDT-SOL", "USDT-ETH",
    "XRP", "BNB", "TRX",
    "MATIC", "AVAX", "DOGE"
]

# Currency display names
CURRENCY_NAMES = {
    "BTC": "Bitcoin",
    "LTC": "Litecoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "USDC-SOL": "USD Coin (Solana)",
    "USDC-ETH": "USD Coin (Ethereum)",
    "USDT-SOL": "Tether (Solana)",
    "USDT-ETH": "Tether (Ethereum)",
    "XRP": "Ripple",
    "BNB": "Binance Coin",
    "TRX": "Tron",
    "MATIC": "Polygon",
    "AVAX": "Avalanche",
    "DOGE": "Dogecoin"
}

# Currency symbols/emojis
CURRENCY_SYMBOLS = {
    "BTC": "🔶",
    "LTC": "⚪",
    "ETH": "🔷",
    "SOL": "🟣",
    "USDC-SOL": "🔵",
    "USDC-ETH": "🔵",
    "USDT-SOL": "🟢",
    "USDT-ETH": "🟢",
    "XRP": "💙",
    "BNB": "💛",
    "TRX": "🔴",
    "MATIC": "🟣",
    "AVAX": "🔴",
    "DOGE": "🐶"
}


# ====================
# Wallet Model
# ====================

class Wallet(BaseModel):
    """
    User's cryptocurrency wallet
    One wallet per currency per user
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="Discord user ID")
    currency: str = Field(..., description="Currency code (BTC, ETH, USDC-SOL, etc.)")
    address: str = Field(..., description="Wallet address for deposits")
    encrypted_private_key: str = Field(..., description="AES encrypted private key")
    tatum_account_id: Optional[str] = Field(None, description="Tatum account ID")
    derivation_index: int = Field(default=0, description="HD wallet derivation index")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = Field(None, description="Last transaction timestamp")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# ====================
# Balance Model
# ====================

class Balance(BaseModel):
    """
    User's balance for a specific currency
    Tracks available, locked, pending, and fee_reserved amounts
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="Discord user ID")
    currency: str = Field(..., description="Currency code")
    available: str = Field(default="0", description="Available for use (Decimal as string)")
    locked: str = Field(default="0", description="Locked in exchanges/swaps (Decimal as string)")
    pending: str = Field(default="0", description="Pending confirmation (Decimal as string)")
    fee_reserved: str = Field(default="0", description="Reserved for admin fees (Decimal as string)")
    last_synced: datetime = Field(default_factory=datetime.utcnow)
    sync_status: Literal["synced", "syncing", "error"] = Field(default="synced")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    def get_total(self) -> Decimal:
        """Calculate total balance (includes fee_reserved)"""
        return Decimal(self.available) + Decimal(self.locked) + Decimal(self.pending) + Decimal(self.fee_reserved)

    def get_withdrawable(self) -> Decimal:
        """Calculate withdrawable balance (available only, excludes locked/pending/fee_reserved)"""
        return Decimal(self.available)


# ====================
# Transaction Model
# ====================

class Transaction(BaseModel):
    """
    Cryptocurrency transaction (deposit or withdrawal)
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    tx_id: str = Field(..., description="Unique transaction ID")
    user_id: str = Field(..., description="Discord user ID")
    currency: str = Field(..., description="Currency code")
    type: Literal["deposit", "withdrawal"] = Field(..., description="Transaction type")

    # Amounts (stored as strings to preserve precision)
    amount: str = Field(..., description="Transaction amount (Decimal as string)")
    network_fee: str = Field(default="0", description="Blockchain network fee")
    server_fee: str = Field(default="0", description="Server profit fee (0.5%)")
    total_deducted: str = Field(default="0", description="Total amount deducted from user")

    # Addresses
    from_address: Optional[str] = Field(None, description="Source address")
    to_address: str = Field(..., description="Destination address")

    # Status tracking
    status: Literal["pending", "confirming", "confirmed", "failed", "cancelled"] = Field(default="pending")
    confirmations: int = Field(default=0, description="Current confirmations")
    required_confirmations: int = Field(default=1, description="Required confirmations")

    # Blockchain data
    blockchain_tx_hash: Optional[str] = Field(None, description="On-chain transaction hash")
    tatum_reference: Optional[str] = Field(None, description="Tatum transaction reference")

    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Profit tracking
    profit_sent: bool = Field(default=False, description="Whether server fee was sent to admin")
    profit_hold_id: Optional[str] = Field(None, description="Profit hold ID if fee too small")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = Field(None, description="Confirmation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda dt: dt.isoformat()}

    def get_amount_decimal(self) -> Decimal:
        """Get amount as Decimal"""
        return Decimal(self.amount)

    def get_total_deducted_decimal(self) -> Decimal:
        """Get total deducted as Decimal"""
        return Decimal(self.total_deducted)


# ====================
# Profit Hold Model
# ====================

class ProfitHold(BaseModel):
    """
    Holds server profit fees that are too small to send immediately
    Batched and sent when threshold is reached
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    transaction_id: str = Field(..., description="Related transaction ID")
    user_id: str = Field(..., description="User who generated the fee")
    currency: str = Field(..., description="Currency code")

    # Amounts
    amount: str = Field(..., description="Profit amount (Decimal as string)")
    usd_value: Optional[str] = Field(None, description="USD value at time of hold")

    # Status
    reason: Literal["below_minimum", "processing_error", "manual_hold"] = Field(..., description="Why it's held")
    status: Literal["held", "processing", "released", "failed"] = Field(default="held")

    # Batch processing
    batch_id: Optional[str] = Field(None, description="Batch ID when processed")
    blockchain_tx_hash: Optional[str] = Field(None, description="Transaction hash when released")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = Field(None, description="Release timestamp")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda dt: dt.isoformat()}

    def get_amount_decimal(self) -> Decimal:
        """Get amount as Decimal"""
        return Decimal(self.amount)


# ====================
# Profit Batch Model
# ====================

class ProfitBatch(BaseModel):
    """
    Batch of profit holds processed together
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    batch_id: str = Field(..., description="Unique batch ID")
    currency: str = Field(..., description="Currency code")

    # Batch details
    total_amount: str = Field(..., description="Total amount in batch")
    transaction_count: int = Field(..., description="Number of transactions")
    hold_ids: list[str] = Field(default_factory=list, description="List of profit hold IDs")

    # Destination
    admin_wallet: str = Field(..., description="Admin wallet address")

    # Status
    status: Literal["processing", "completed", "failed"] = Field(default="processing")
    blockchain_tx_hash: Optional[str] = Field(None, description="On-chain transaction hash")
    error_message: Optional[str] = Field(None, description="Error if failed")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda dt: dt.isoformat()}


# ====================
# Webhook Log Model
# ====================

class WebhookLog(BaseModel):
    """
    Log of Tatum webhook calls for deposits
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    webhook_id: str = Field(..., description="Webhook ID from Tatum")
    user_id: Optional[str] = Field(None, description="User ID if matched")
    currency: str = Field(..., description="Currency code")
    address: str = Field(..., description="Wallet address")
    amount: str = Field(..., description="Deposit amount")
    tx_hash: str = Field(..., description="Blockchain transaction hash")
    confirmations: int = Field(default=0, description="Confirmations at time of webhook")
    processed: bool = Field(default=False, description="Whether deposit was processed")
    error_message: Optional[str] = Field(None, description="Error if processing failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda dt: dt.isoformat()}


# ====================
# Helper Functions
# ====================

def is_valid_currency(currency: str) -> bool:
    """Check if currency is supported"""
    return currency.upper() in SUPPORTED_CURRENCIES


def get_currency_name(currency: str) -> str:
    """Get display name for currency"""
    return CURRENCY_NAMES.get(currency.upper(), currency.upper())


def get_currency_symbol(currency: str) -> str:
    """Get emoji symbol for currency"""
    return CURRENCY_SYMBOLS.get(currency.upper(), "💰")
