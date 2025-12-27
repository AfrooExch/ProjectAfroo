"""Partner model"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

from app.models.user import PyObjectId


class PartnerBranding(BaseModel):
    """Partner branding configuration"""

    logo_url: Optional[str] = None
    primary_color: str = "#000000"
    secondary_color: str = "#ffffff"
    custom_domain: Optional[str] = None


class PartnerFeeStructure(BaseModel):
    """Partner fee configuration"""

    platform_fee_percent: float = 1.0
    partner_fee_percent: float = 0.5
    exchanger_fee_percent: float = 1.0
    revenue_share_percent: float = 20.0


class Partner(BaseModel):
    """Partner model"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Identity
    name: str
    slug: str  # Unique, URL-safe

    # Discord integration
    discord_guild_id: str  # Unique
    discord_owner_id: str

    # Branding
    branding: PartnerBranding = PartnerBranding()

    # Configuration
    config: dict = {}
    fee_structure: PartnerFeeStructure = PartnerFeeStructure()

    # Limits & quotas
    max_exchangers: int = 10
    max_monthly_volume: Optional[float] = None

    # Status
    status: str = "active"  # active, suspended, trial
    tier: str = "basic"  # basic, pro, enterprise

    # Analytics
    total_exchanges: int = 0
    total_volume: float = 0.0
    total_revenue: float = 0.0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True


class PartnerCreate(BaseModel):
    """Partner creation model"""

    name: str
    slug: str
    discord_guild_id: str
    discord_owner_id: str


class PartnerResponse(BaseModel):
    """Partner response model"""

    id: str
    name: str
    slug: str
    status: str
    tier: str
    created_at: datetime
