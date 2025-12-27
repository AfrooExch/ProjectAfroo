"""
Transcript Model - Metadata for stored ticket transcripts
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.with_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            )
        )

    @classmethod
    def validate(cls, v, info):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class TranscriptMetadata(BaseModel):
    """Metadata for stored transcripts"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Ticket reference
    ticket_id: str  # Original ticket/swap/escrow ID
    ticket_type: str  # 'ticket', 'swap', 'automm', 'application', 'support'
    ticket_number: Optional[int] = None  # Human-readable number if applicable

    # Ownership
    user_id: str  # Primary owner (Discord ID)
    participants: List[str] = []  # Other users who can access (Discord IDs)

    # File info
    file_path: str  # Server filesystem path
    file_size: int  # Bytes

    # Transcript details
    message_count: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Access tracking
    view_count: int = 0
    last_viewed_at: Optional[datetime] = None

    # Status
    status: str = "active"  # 'active', 'archived', 'deleted'

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class TranscriptUploadRequest(BaseModel):
    """Request to upload a new transcript"""

    ticket_id: str
    ticket_type: str  # 'ticket', 'swap', 'automm', 'application', 'support'
    ticket_number: Optional[int] = None
    user_id: str  # Discord ID of primary owner
    participants: List[str] = []  # Other Discord IDs
    html_content: str  # The full HTML transcript
    message_count: int = 0


class TranscriptUploadResponse(BaseModel):
    """Response after successful upload"""

    success: bool
    transcript_id: str
    public_url: str  # Full URL to view transcript
    file_path: str
    file_size: int
