"""
Support Tickets API Routes
Bug reports, feature requests, general support
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime

from app.api.deps import get_current_user_bot, AuthContext
from app.core.database import get_database

router = APIRouter()


@router.post("/support/tickets")
async def create_support_ticket(
    ticket_type: str,
    subject: str,
    description: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Create support ticket"""
    ticket_data = {
        "user_id": auth.user["discord_id"],
        "username": auth.user.get("username", "Unknown"),
        "ticket_type": ticket_type,  # bug_report, feature_request, general_support
        "subject": subject,
        "description": description,
        "status": "open",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "messages": []
    }

    result = await db.support_tickets.insert_one(ticket_data)
    ticket_data["_id"] = str(result.inserted_id)
    ticket_data["ticket_id"] = str(result.inserted_id)

    return {"success": True, "ticket": ticket_data}


@router.get("/support/tickets/{ticket_id}")
async def get_support_ticket(
    ticket_id: str,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Get support ticket by ID"""
    from bson import ObjectId

    ticket = await db.support_tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    # Check ownership or admin
    if ticket["user_id"] != auth.user["discord_id"] and not auth.is_admin:
        raise HTTPException(403, "Not authorized")

    ticket["_id"] = str(ticket["_id"])
    return ticket


@router.post("/support/tickets/{ticket_id}/close")
async def close_support_ticket(
    ticket_id: str,
    reason: Optional[str] = None,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Close support ticket"""
    from bson import ObjectId

    result = await db.support_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "status": "closed",
                "closed_at": datetime.utcnow(),
                "closed_by": auth.user["discord_id"],
                "close_reason": reason
            }
        }
    )

    return {"success": True, "modified": result.modified_count}


@router.post("/support/tickets/{ticket_id}/messages")
async def add_support_message(
    ticket_id: str,
    message: str,
    attachments: Optional[List[str]] = None,
    auth: AuthContext = Depends(get_current_user_bot),
    db = Depends(get_database)
):
    """Add message to support ticket"""
    from bson import ObjectId

    message_data = {
        "author_id": auth.user["discord_id"],
        "author_name": auth.user.get("username", "Unknown"),
        "message": message,
        "attachments": attachments or [],
        "timestamp": datetime.utcnow()
    }

    result = await db.support_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$push": {"messages": message_data}}
    )

    return {"success": True, "modified": result.modified_count}
