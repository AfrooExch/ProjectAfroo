"""
Exchanger Deposit Models - V3 deposit system for exchangers
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ExchangerDepositCreate(BaseModel):
    """Create exchanger deposit wallet"""
    asset: str = Field(..., description="Asset code (BTC, ETH, LTC, etc.)")


class ExchangerDepositBalance(BaseModel):
    """Exchanger deposit balance info"""
    asset: str
    balance_units: float
    held_units: float
    fee_reserved_units: float
    available_units: float
    balance_usd: float
    compensation_balance_usd: float = 0.0  # Permanent compensation balance (not affected by blockchain sync)
    total_committed_usd: float
    claim_limit_usd: float
    address: str


class ExchangerDepositWithdraw(BaseModel):
    """Withdraw from exchanger deposit"""
    asset: str
    amount_units: float
    to_address: str
