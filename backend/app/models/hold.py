"""
Hold Models - Fund locking for tickets
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class HoldCreate(BaseModel):
    """Create fund hold"""
    ticket_id: str
    user_id: str
    asset: str
    amount_units: float
    amount_usd: float


class HoldRelease(BaseModel):
    """Release hold"""
    hold_id: str
    deduct_fee: bool = True


class HoldRefund(BaseModel):
    """Refund hold"""
    hold_id: str
