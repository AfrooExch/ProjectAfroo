"""General helper functions"""

from datetime import datetime
from typing import Optional, Any
from bson import ObjectId


def format_currency(amount: float, currency: str) -> str:
    """Format currency amount"""
    return f"{amount:.8f} {currency.upper()}"


def calculate_fee(amount: float, fee_percent: float) -> float:
    """Calculate fee from amount and percentage"""
    return amount * (fee_percent / 100)


def generate_slug(text: str) -> str:
    """Generate URL-safe slug from text"""
    return text.lower().replace(" ", "-").replace("_", "-")


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO string"""
    return dt.isoformat() if dt else None


def serialize_objectids(data: Any) -> Any:
    """
    Recursively convert all BSON ObjectIds to strings for JSON serialization.

    Handles:
    - Single ObjectId values
    - Nested dictionaries
    - Lists of items
    - Mixed structures

    Args:
        data: Any data structure that may contain ObjectIds

    Returns:
        The same structure with all ObjectIds converted to strings

    Example:
        >>> doc = {"_id": ObjectId("..."), "user": {"id": ObjectId("...")}}
        >>> serialize_objectids(doc)
        {"_id": "...", "user": {"id": "..."}}
    """
    if isinstance(data, ObjectId):
        # Convert ObjectId to string
        return str(data)
    elif isinstance(data, dict):
        # Recursively process dictionary values
        return {key: serialize_objectids(value) for key, value in data.items()}
    elif isinstance(data, list):
        # Recursively process list items
        return [serialize_objectids(item) for item in data]
    elif isinstance(data, tuple):
        # Recursively process tuple items (return as tuple)
        return tuple(serialize_objectids(item) for item in data)
    else:
        # Return as-is for primitive types (str, int, float, bool, None, etc.)
        return data
