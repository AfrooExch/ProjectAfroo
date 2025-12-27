"""User model"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema):
        schema.update(type="string")
        return schema


class User(BaseModel):
    """User model"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Discord identity (immutable)
    discord_id: str
    username: str
    discriminator: Optional[str] = None
    global_name: Optional[str] = None
    avatar_hash: Optional[str] = None
    # Email from Discord OAuth (stored but NOT used for notifications)
    # Notifications are sent via Discord DM only
    email: Optional[str] = None

    # Profile
    bio: Optional[str] = None
    language: str = "en"
    timezone: str = "UTC"

    # Platform metadata
    partner_id: Optional[PyObjectId] = None
    referred_by: Optional[PyObjectId] = None

    # Status
    status: str = "active"  # active, suspended, banned, archived
    kyc_level: int = 0  # 0: none, 1: basic, 2: advanced
    reputation_score: int = 100

    # Security
    two_factor_enabled: bool = False
    two_factor_secret: Optional[str] = None

    # Login tracking
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    login_history: List[dict] = []

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True


class UserCreate(BaseModel):
    """User creation model"""

    discord_id: str
    username: str
    discriminator: Optional[str] = None
    global_name: Optional[str] = None
    avatar_hash: Optional[str] = None
    # Email from Discord OAuth (stored but NOT used for email notifications)
    email: Optional[str] = None


class UserUpdate(BaseModel):
    """User update model"""

    username: Optional[str] = None
    bio: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


class UserResponse(BaseModel):
    """User response model (public-facing)"""

    discord_id: str
    username: str
    global_name: Optional[str] = None
    avatar_hash: Optional[str] = None
    status: str
    kyc_level: int
    reputation_score: int
    created_at: datetime
