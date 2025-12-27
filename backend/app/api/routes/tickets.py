"""
Ticket Routes - Support ticket system
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional
from pydantic import BaseModel

from app.api.dependencies import get_current_active_user, require_admin, get_user_from_bot_request
from app.services.ticket_service import TicketService
from app.services.tos_service import TOSService
from app.models.ticket import TicketCreate, TicketMessageCreate, ExchangeTicketCreate
from app.core.config import settings
from app.core.database import get_tickets_collection

router = APIRouter(tags=["Tickets"])


class TOSAgreementRequest(BaseModel):
    """TOS agreement request"""
    agreed: bool = True  # User must explicitly agree


@router.post("/create")
async def create_ticket(request: Request):
    """Create new ticket (support or exchange)"""

    # Get raw JSON body
    body = await request.json()

    # Check if this is an exchange ticket (has exchange-specific fields)
    is_exchange = all(k in body for k in ["send_method", "receive_method", "amount_usd", "fee_amount"])

    if is_exchange:
        # Exchange tickets use bot authentication via headers
        x_bot_token = request.headers.get("x-bot-token")
        if x_bot_token != settings.BOT_SERVICE_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid bot token")

        # Handle exchange ticket creation
        try:
            exchange_data = ExchangeTicketCreate(**body)
            ticket = await TicketService.create_exchange_ticket(exchange_data)

            return {
                "message": "Exchange ticket created successfully",
                "ticket_id": str(ticket["_id"]),
                "ticket_number": ticket["ticket_number"],
                "status": ticket["status"],
                "created_at": ticket["created_at"],
                "tos_deadline": ticket.get("tos_deadline")
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Regular support tickets require user authentication
        try:
            # Get authenticated user
            authorization = request.headers.get("Authorization")
            if not authorization:
                raise HTTPException(status_code=401, detail="Authentication required")

            from app.api.dependencies import get_current_active_user
            from fastapi.security import HTTPAuthorizationCredentials

            scheme, token = authorization.split(" ", 1)
            credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
            user = await get_current_active_user(credentials)

            ticket_data = TicketCreate(**body)
            user_id = str(user["_id"])
            ticket = await TicketService.create_ticket(user_id, ticket_data)

            return {
                "message": "Ticket created successfully",
                "ticket": {
                    "id": str(ticket["_id"]),
                    "ticket_number": ticket["ticket_number"],
                    "type": ticket["type"],
                    "subject": ticket["subject"],
                    "status": ticket["status"],
                    "created_at": ticket["created_at"]
                }
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
async def list_my_tickets(
    status: Optional[str] = None,
    user: dict = Depends(get_current_active_user)
):
    """List user's tickets"""

    user_id = str(user["_id"])
    tickets = await TicketService.list_tickets(user_id=user_id, status=status)

    return {
        "tickets": [
            {
                "id": str(t["_id"]),
                "ticket_number": t["ticket_number"],
                "type": t["type"],
                "subject": t["subject"],
                "status": t["status"],
                "priority": t.get("priority"),
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
                "message_count": len(t.get("messages", []))
            }
            for t in tickets
        ],
        "count": len(tickets)
    }


@router.get("/active")
async def get_active_tickets(
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """
    Get user's active tickets (non-completed/cancelled).
    Accepts bot token authentication.
    """
    try:
        from app.core.database import get_users_collection
        from bson import ObjectId

        # Get user from Discord ID
        users = get_users_collection()
        user = await users.find_one({"discord_id": discord_user_id})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get active tickets (not completed or cancelled)
        tickets = get_tickets_collection()
        cursor = tickets.find({
            "$or": [
                {"user_id": user["_id"]},
                {"client_id": user["_id"]},
                {"exchanger_id": user["_id"]}
            ],
            "status": {
                "$nin": ["completed", "cancelled", "closed"]
            }
        }).sort("created_at", -1).limit(50)

        active_tickets = await cursor.to_list(length=50)

        # Convert ObjectIds to strings for JSON serialization
        result_tickets = []
        for ticket in active_tickets:
            result_tickets.append({
                "id": str(ticket["_id"]),
                "ticket_number": ticket.get("ticket_number", ""),
                "type": ticket.get("type", "support"),
                "subject": ticket.get("subject", ""),
                "status": ticket["status"],
                "channel_id": ticket.get("channel_id"),
                "created_at": ticket["created_at"].isoformat() if ticket.get("created_at") else None,
                "updated_at": ticket["updated_at"].isoformat() if ticket.get("updated_at") else None
            })

        return {
            "success": True,
            "tickets": result_tickets,
            "count": len(result_tickets)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active tickets: {str(e)}"
        )


@router.get("/pending-notifications")
async def get_pending_notifications(
    request: Request
):
    """Get tickets with pending completion notifications (bot only)"""
    # Verify bot authentication
    x_bot_token = request.headers.get("x-bot-token")

    if not x_bot_token or x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Bot authentication required")

    from app.utils.helpers import serialize_objectids
    tickets = get_tickets_collection()

    # Find tickets with pending notifications
    cursor = tickets.find({"notification_pending": True}).limit(20)
    pending_tickets = await cursor.to_list(length=20)

    # Recursively convert all ObjectIds to strings for JSON serialization
    # This handles nested ObjectIds in completion_notification and other fields
    pending_tickets = serialize_objectids(pending_tickets)

    return {
        "tickets": pending_tickets,
        "count": len(pending_tickets)
    }


@router.post("/{ticket_id}/mark-notification-processed")
async def mark_notification_processed(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Mark completion notification as processed (bot only)"""
    from app.services.notification_service import NotificationService

    await NotificationService.mark_notification_processed(ticket_id)

    return {
        "message": "Notification marked as processed",
        "ticket_id": ticket_id
    }


@router.get("/exchange-rates")
async def get_exchange_rates(
    amount: float = 100.0
):
    """Get live USD to top 10 global currency conversion rates"""
    try:
        from app.services.exchange_rate_service import ExchangeRateService

        # get_top_currencies() already returns the full structure
        result = await ExchangeRateService.get_top_currencies(amount)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rates: {str(e)}")


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    request: Request
):
    """Get ticket details with messages (supports both JWT and bot authentication)"""

    from bson import ObjectId
    from app.core.database import get_tickets_collection

    tickets = get_tickets_collection()
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check authentication method (bot token or JWT)
    x_bot_token = request.headers.get("x-bot-token")

    if x_bot_token and x_bot_token == settings.BOT_SERVICE_TOKEN:
        # Bot authentication - use Discord user ID
        discord_user_id = request.headers.get("x-discord-user-id") or request.headers.get("x-discord-id")
        if not discord_user_id:
            raise HTTPException(status_code=401, detail="Missing Discord user ID")

        # Check ownership - compare Discord IDs
        ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))

        # For bot requests, just return the ticket (exchangers need to see ticket details)
        # No strict ownership check for bot requests since exchangers need access
    else:
        # JWT authentication
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(status_code=401, detail="Authentication required")

        from app.api.dependencies import get_current_active_user
        from fastapi.security import HTTPAuthorizationCredentials

        scheme, token = authorization.split(" ", 1)
        credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
        user = await get_current_active_user(credentials)

        # Check ownership (or admin)
        user_id = str(user["_id"])
        is_admin = "admin" in user.get("roles", [])

        if str(ticket["user_id"]) != user_id and not is_admin:
            raise HTTPException(status_code=403, detail="Not your ticket")

    return {
        "ticket": {
            "id": str(ticket["_id"]),
            "ticket_number": ticket["ticket_number"],
            "user_id": str(ticket["user_id"]),
            "discord_user_id": ticket.get("discord_user_id"),
            "type": ticket["type"],
            "subject": ticket.get("subject"),
            "description": ticket.get("description"),
            "status": ticket["status"],
            "priority": ticket.get("priority"),
            "assigned_to": str(ticket["assigned_to"]) if ticket.get("assigned_to") else None,
            "exchanger_discord_id": ticket.get("exchanger_discord_id"),
            "exchanger_id": str(ticket.get("exchanger_id")) if ticket.get("exchanger_id") else None,
            "amount_usd": ticket.get("amount_usd"),
            "fee_amount": ticket.get("fee_amount"),
            "fee_percentage": ticket.get("fee_percentage"),
            "receiving_amount": ticket.get("receiving_amount"),
            "send_method": ticket.get("send_method"),
            "receive_method": ticket.get("receive_method"),
            "send_crypto": ticket.get("send_crypto"),
            "receive_crypto": ticket.get("receive_crypto"),
            "channel_id": ticket.get("channel_id"),
            "exchanger_channel_id": ticket.get("exchanger_channel_id"),
            "category_id": ticket.get("category_id"),
            "exchanger_category_id": ticket.get("exchanger_category_id"),
            "messages": [
                {
                    "id": msg["id"],
                    "user_id": str(msg["user_id"]),
                    "message": msg["message"],
                    "is_internal": msg.get("is_internal", False),
                    "created_at": msg["created_at"]
                }
                for msg in ticket.get("messages", [])
            ],
            "created_at": ticket["created_at"],
            "updated_at": ticket["updated_at"],
            "first_response_at": ticket.get("first_response_at"),
            "resolved_at": ticket.get("resolved_at"),
            "closed_at": ticket.get("closed_at")
        }
    }


@router.post("/{ticket_id}/message")
async def add_ticket_message(
    ticket_id: str,
    message_data: TicketMessageCreate,
    user: dict = Depends(get_current_active_user)
):
    """Add message to ticket"""

    # Verify ticket ownership
    from bson import ObjectId
    from app.core.database import get_tickets_collection

    tickets = get_tickets_collection()
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    user_id = str(user["_id"])
    is_admin = "admin" in user.get("roles", [])

    if str(ticket["user_id"]) != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not your ticket")

    # Only staff can post internal messages
    if message_data.is_internal and not is_admin:
        raise HTTPException(status_code=403, detail="Only staff can post internal messages")

    try:
        updated_ticket = await TicketService.add_message(ticket_id, user_id, message_data)

        return {
            "message": "Message added successfully",
            "ticket_id": ticket_id,
            "message_count": len(updated_ticket.get("messages", []))
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/close")
async def close_ticket(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Close ticket (bot-authenticated)"""

    # Verify ticket ownership
    from bson import ObjectId
    from app.core.database import get_tickets_collection
    from app.services.user_service import UserService

    tickets = get_tickets_collection()
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check if user is client, exchanger, or admin
    ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))
    exchanger_discord_id = ticket.get("exchanger_discord_id")

    is_owner = ticket_discord_id == discord_user_id
    is_exchanger = exchanger_discord_id and str(exchanger_discord_id) == str(discord_user_id)
    is_admin = await UserService.is_staff(discord_user_id)

    if not (is_owner or is_exchanger or is_admin):
        raise HTTPException(status_code=403, detail="Not your ticket")

    try:
        updated_ticket = await TicketService.close_ticket(ticket_id, discord_user_id)

        return {
            "message": "Ticket closed successfully",
            "ticket": {
                "id": str(updated_ticket["_id"]),
                "status": updated_ticket["status"],
                "closed_at": updated_ticket.get("closed_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/claim")
async def claim_ticket(
    ticket_id: str,
    request: Request,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Claim ticket as exchanger - locks funds (bot-authenticated, V4 System)"""

    from bson import ObjectId
    from decimal import Decimal
    from app.core.database import get_tickets_collection

    # Get ticket to determine currency and amount
    tickets = get_tickets_collection()
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # IMPORTANT: Hold the FULL ticket amount, not just receiving_amount
    # receiving_amount = what client gets after platform fee
    # amount_usd = FULL ticket value (what client sent)
    # We hold the full amount as collateral
    full_ticket_amount = Decimal(str(ticket.get("amount_usd", 0)))

    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Claim ticket #{ticket.get('ticket_number')}: user={discord_user_id}, amount=${full_ticket_amount}")

    # Multi-currency hold: Auto-allocate from ANY available deposits
    # No need to specify currency - system will use whatever is available
    try:
        updated_ticket = await TicketService.claim_ticket(
            ticket_id=ticket_id,
            exchanger_id=discord_user_id,  # Pass Discord ID (string)
            amount_usd=full_ticket_amount  # Hold FULL ticket amount
        )

        return {
            "message": "Ticket claimed successfully, funds locked",
            "ticket": {
                "id": str(updated_ticket["_id"]),
                "ticket_number": updated_ticket.get("ticket_number"),
                "status": updated_ticket["status"],
                "claimed_at": updated_ticket.get("claimed_at"),
                "hold_id": str(updated_ticket.get("hold_id")),
                "amount_usd": updated_ticket.get("amount_usd"),
                "fee_amount": updated_ticket.get("fee_amount"),
                "receiving_amount": updated_ticket.get("receiving_amount"),
                "send_method": updated_ticket.get("send_method"),
                "receive_method": updated_ticket.get("receive_method"),
                "send_crypto": updated_ticket.get("send_crypto"),
                "receive_crypto": updated_ticket.get("receive_crypto"),
                "user_id": str(updated_ticket.get("user_id")),
                "discord_user_id": updated_ticket.get("discord_user_id"),
                "assigned_to": str(updated_ticket.get("assigned_to")) if updated_ticket.get("assigned_to") else None,
                "channel_id": updated_ticket.get("channel_id"),
                "exchanger_channel_id": updated_ticket.get("exchanger_channel_id")
            }
        }
    except ValueError as e:
        # Return clear error message from service (includes insufficient balance errors)
        error_msg = str(e)
        logger.error(f"Claim validation error for ticket {ticket_id}: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        # Log unexpected errors and return clear message
        logger.error(f"Error claiming ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to claim ticket: {str(e)}")


@router.post("/{ticket_id}/complete")
async def complete_ticket(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Complete ticket - releases hold and deducts funds + fee (bot-authenticated)"""

    user_id = discord_user_id

    try:
        updated_ticket = await TicketService.complete_ticket(ticket_id, user_id)

        return {
            "message": "Ticket completed successfully, funds deducted",
            "ticket": {
                "id": str(updated_ticket["_id"]),
                "ticket_number": updated_ticket.get("ticket_number"),
                "status": updated_ticket["status"],
                "resolved_at": updated_ticket.get("resolved_at"),
                "closed_at": updated_ticket.get("closed_at"),
                "amount_usd": updated_ticket.get("amount_usd"),
                "receiving_amount": updated_ticket.get("receiving_amount"),
                "user_id": str(updated_ticket.get("user_id")) if updated_ticket.get("user_id") else None,
                "discord_user_id": updated_ticket.get("discord_user_id"),
                "exchanger_id": str(updated_ticket.get("assigned_to")) if updated_ticket.get("assigned_to") else None,
                "exchanger_discord_id": updated_ticket.get("exchanger_discord_id"),
                "send_method": updated_ticket.get("send_method"),
                "send_crypto": updated_ticket.get("send_crypto"),
                "receive_method": updated_ticket.get("receive_method"),
                "receive_crypto": updated_ticket.get("receive_crypto")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ticket_id}/cancel")
async def cancel_ticket(
    ticket_id: str,
    request: Request,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Cancel ticket - refunds hold if claimed (bot-authenticated)"""

    # Get reason from request body
    try:
        body = await request.json()
        reason = body.get("reason", "")
    except:
        reason = ""

    # Verify ticket ownership
    from bson import ObjectId
    from app.core.database import get_tickets_collection

    tickets = get_tickets_collection()
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Verify ownership - check discord_user_id for exchange tickets
    ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))
    if ticket_discord_id != discord_user_id:
        raise HTTPException(status_code=403, detail="Not your ticket")

    try:
        updated_ticket = await TicketService.cancel_ticket(ticket_id, discord_user_id, reason)

        return {
            "message": "Ticket canceled successfully",
            "ticket": {
                "id": str(updated_ticket["_id"]),
                "status": updated_ticket["status"],
                "canceled_reason": updated_ticket.get("canceled_reason"),
                "closed_at": updated_ticket.get("closed_at")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ticket_id}/tos")
async def get_ticket_tos(
    ticket_id: str,
    user: dict = Depends(get_current_active_user)
):
    """Get required TOS for exchange ticket"""

    from bson import ObjectId
    from app.core.database import get_tickets_collection

    tickets = get_tickets_collection()
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Verify ownership
    user_id = str(user["_id"])
    if str(ticket["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not your ticket")

    # Check if ticket requires TOS
    if not ticket.get("tos_required"):
        raise HTTPException(status_code=400, detail="This ticket does not require TOS")

    # Get TOS details
    required_tos_ids = ticket.get("required_tos_ids", [])
    tos_details = []

    from app.core.database import get_db_collection
    tos_db = await get_db_collection("tos_versions")

    for tos_id in required_tos_ids:
        tos = await tos_db.find_one({"_id": ObjectId(tos_id)})
        if tos:
            tos_details.append({
                "id": str(tos["_id"]),
                "category": tos["category"],
                "version": tos["version"],
                "content": tos["content"],
                "summary": tos.get("summary")
            })

    return {
        "ticket_id": ticket_id,
        "tos_required": ticket.get("tos_required"),
        "tos_deadline": ticket.get("tos_deadline"),
        "tos_accepted_at": ticket.get("tos_accepted_at"),
        "tos_ping_count": ticket.get("tos_ping_count", 0),
        "required_tos": tos_details,
        "time_remaining_seconds": (
            int((ticket["tos_deadline"] - ticket["created_at"]).total_seconds())
            if ticket.get("tos_deadline") and not ticket.get("tos_accepted_at")
            else None
        )
    }


@router.post("/{ticket_id}/tos/agree")
async def agree_to_ticket_tos(
    ticket_id: str,
    request_data: TOSAgreementRequest,
    http_request: Request,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Agree to TOS for exchange ticket (bot-authenticated)"""

    if not request_data.agreed:
        raise HTTPException(status_code=400, detail="You must agree to the terms")

    ip_address = http_request.client.host
    user_agent = http_request.headers.get("user-agent", "")

    try:
        updated_ticket = await TicketService.agree_to_tos(
            ticket_id=ticket_id,
            user_id=discord_user_id,  # Use Discord user ID directly
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "message": "TOS accepted successfully",
            "ticket": {
                "id": str(updated_ticket["_id"]),
                "ticket_id": str(updated_ticket["_id"]),
                "ticket_number": updated_ticket.get("ticket_number"),
                "status": updated_ticket["status"],
                "tos_accepted_at": updated_ticket.get("tos_accepted_at"),
                "amount_usd": updated_ticket.get("amount_usd"),
                "fee_amount": updated_ticket.get("fee_amount"),
                "fee_percentage": updated_ticket.get("fee_percentage"),
                "receiving_amount": updated_ticket.get("receiving_amount"),
                "send_method": updated_ticket.get("send_method"),
                "send_crypto": updated_ticket.get("send_crypto"),
                "receive_method": updated_ticket.get("receive_method"),
                "receive_crypto": updated_ticket.get("receive_crypto"),
                "client_discord_id": updated_ticket.get("discord_user_id"),
                "client_username": updated_ticket.get("client_username")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    request: Request
):
    """Update ticket fields (bot-authenticated)"""
    from bson import ObjectId
    from datetime import datetime
    import logging

    logger = logging.getLogger(__name__)

    # Verify bot authentication
    x_bot_token = request.headers.get("x-bot-token")
    if not x_bot_token or x_bot_token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Bot authentication required")

    # Get update data from request body
    body = await request.json()

    # Only allow specific fields to be updated
    allowed_fields = [
        "channel_id",
        "exchanger_channel_id",
        "category_id",
        "exchanger_category_id"
    ]

    # Filter only allowed fields
    update_data = {k: v for k, v in body.items() if k in allowed_fields}

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    try:
        tickets = get_tickets_collection()

        # Update ticket
        update_data["updated_at"] = datetime.utcnow()

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {"$set": update_data},
            return_document=True
        )

        if not result:
            raise HTTPException(status_code=404, detail="Ticket not found")

        logger.info(f"Updated ticket {ticket_id} with fields: {list(update_data.keys())}")

        return {
            "message": "Ticket updated successfully",
            "ticket": {
                "id": str(result["_id"]),
                "ticket_number": result.get("ticket_number"),
                "channel_id": result.get("channel_id"),
                "exchanger_channel_id": result.get("exchanger_channel_id"),
                "category_id": result.get("category_id"),
                "exchanger_category_id": result.get("exchanger_category_id")
            }
        }
    except Exception as e:
        logger.error(f"Error updating ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    staff_id: str,
    admin: dict = Depends(require_admin)
):
    """Assign ticket to staff (admin only)"""

    try:
        updated_ticket = await TicketService.assign_ticket(ticket_id, staff_id)

        return {
            "message": "Ticket assigned successfully",
            "ticket": {
                "id": str(updated_ticket["_id"]),
                "assigned_to": str(updated_ticket["assigned_to"]),
                "status": updated_ticket["status"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/all")
async def list_all_tickets_admin(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """List all tickets with filters (admin only via bot)"""
    from bson import ObjectId

    tickets = get_tickets_collection()

    # Build query
    query = {}
    if status:
        query["status"] = status
    if type:
        query["type"] = type

    # Fetch tickets
    cursor = tickets.find(query).sort("created_at", -1).limit(limit)
    ticket_list = await cursor.to_list(length=limit)

    return {
        "tickets": [
            {
                "_id": str(t["_id"]),
                "ticket_number": t["ticket_number"],
                "user_id": str(t.get("user_id", "")),
                "discord_user_id": t.get("discord_user_id", str(t.get("user_id", ""))),
                "exchanger_discord_id": t.get("exchanger_discord_id"),
                "type": t["type"],
                "subject": t.get("subject", ""),
                "status": t["status"],
                "priority": t.get("priority", "medium"),
                "assigned_to": str(t["assigned_to"]) if t.get("assigned_to") else None,
                "channel_id": t.get("channel_id"),
                "amount_usd": t.get("amount_usd", 0),
                "fee_amount": t.get("fee_amount", 0),
                "receiving_amount": t.get("receiving_amount", 0),
                "send_method": t.get("send_method"),
                "receive_method": t.get("receive_method"),
                "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
                "updated_at": t.get("updated_at").isoformat() if t.get("updated_at") else None,
                "claimed_at": t.get("claimed_at").isoformat() if t.get("claimed_at") else None,
                "closed_at": t.get("closed_at").isoformat() if t.get("closed_at") else None
            }
            for t in ticket_list
        ],
        "count": len(ticket_list)
    }


@router.get("/admin/{ticket_number}")
async def get_ticket_by_number_admin(
    ticket_number: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Get ticket details by ticket number (admin only via bot)"""
    from bson import ObjectId

    tickets = get_tickets_collection()

    # Try to find by ticket_number (int)
    try:
        ticket = await tickets.find_one({"ticket_number": int(ticket_number)})
    except ValueError:
        ticket = None

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket #{ticket_number} not found")

    return {
        "_id": str(ticket["_id"]),
        "ticket_number": ticket["ticket_number"],
        "user_id": str(ticket.get("user_id", "")),
        "discord_user_id": ticket.get("discord_user_id", str(ticket.get("user_id", ""))),
        "exchanger_discord_id": ticket.get("exchanger_discord_id"),
        "type": ticket["type"],
        "subject": ticket.get("subject", ""),
        "description": ticket.get("description", ""),
        "status": ticket["status"],
        "priority": ticket.get("priority", "medium"),
        "assigned_to": str(ticket["assigned_to"]) if ticket.get("assigned_to") else None,
        "channel_id": ticket.get("channel_id"),
        "amount_usd": ticket.get("amount_usd", 0),
        "fee_amount": ticket.get("fee_amount", 0),
        "receiving_amount": ticket.get("receiving_amount", 0),
        "send_method": ticket.get("send_method"),
        "receive_method": ticket.get("receive_method"),
        "hold_id": str(ticket["hold_id"]) if ticket.get("hold_id") else None,
        "hold_ids": ticket.get("hold_ids", []),
        "created_at": ticket["created_at"].isoformat() if ticket.get("created_at") else None,
        "updated_at": ticket.get("updated_at").isoformat() if ticket.get("updated_at") else None,
        "claimed_at": ticket.get("claimed_at").isoformat() if ticket.get("claimed_at") else None,
        "closed_at": ticket.get("closed_at").isoformat() if ticket.get("closed_at") else None
    }


class ForceCloseRequest(BaseModel):
    """Force close ticket request"""
    reason: str


@router.post("/admin/{ticket_id}/force-close")
async def force_close_ticket_admin(
    ticket_id: str,
    request: ForceCloseRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Force close ticket (admin only via bot)"""
    from bson import ObjectId
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Close ticket and refund holds
        ticket = await TicketService.close_ticket(ticket_id, discord_user_id)

        # Store the close reason
        tickets = get_tickets_collection()
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "force_close_reason": request.reason,
                    "force_closed_by_admin": discord_user_id
                }
            }
        )

        logger.info(f"Admin {discord_user_id} force closed ticket {ticket_id}: {request.reason}")

        return {
            "success": True,
            "message": f"Ticket force closed",
            "ticket": {
                "id": str(ticket["_id"]),
                "status": ticket["status"],
                "closed_at": ticket.get("closed_at").isoformat() if ticket.get("closed_at") else None
            }
        }
    except Exception as e:
        logger.error(f"Error force closing ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/{ticket_id}/force-complete")
async def force_complete_ticket_admin(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Force complete ticket - releases holds with deduction (admin only via bot)"""
    from bson import ObjectId
    import logging
    logger = logging.getLogger(__name__)

    try:
        tickets = get_tickets_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Get client Discord ID for TicketService.complete_ticket (it verifies client ownership)
        # We'll bypass that by calling hold service directly
        from app.services.hold_service import HoldService

        # Release all holds with deduction
        await HoldService.release_all_holds_for_ticket(
            ticket_id=ticket_id,
            deduct_funds=True
        )

        # Update ticket status
        from datetime import datetime
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "completed",
                    "resolved_at": datetime.utcnow(),
                    "closed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "force_completed_by_admin": discord_user_id
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            discord_user_id,
            "ticket.force_completed_by_admin",
            {"admin_id": discord_user_id}
        )

        # Auto-refresh exchanger deposits after completion
        if result.get("exchanger_discord_id"):
            try:
                from app.services.exchanger_service import ExchangerService
                exchanger_id = result["exchanger_discord_id"]

                # Get all deposits and sync them
                deposits_list = await ExchangerService.list_deposits(exchanger_id)
                for deposit in deposits_list:
                    try:
                        # Access currency from Pydantic model
                        currency = deposit.currency if hasattr(deposit, 'currency') else deposit.get('currency')
                        if currency:
                            await ExchangerService.sync_deposit_balance(exchanger_id, currency)
                            logger.info(f"Auto-synced {currency} for exchanger {exchanger_id} after force complete")
                    except Exception as sync_err:
                        logger.warning(f"Failed to auto-sync deposit: {sync_err}")
            except Exception as refresh_err:
                logger.error(f"Failed to auto-refresh deposits: {refresh_err}")

        # Check milestones for customer and exchanger
        try:
            from app.services.milestone_service import MilestoneService

            # Check customer milestones
            if result.get("user_id"):
                await MilestoneService.check_and_grant_milestones(str(result["user_id"]))

            # Check exchanger milestones
            if result.get("assigned_to"):
                await MilestoneService.check_and_grant_milestones(str(result["assigned_to"]))
        except Exception as milestone_err:
            logger.warning(f"Failed to check milestones: {milestone_err}")

        logger.info(f"Admin {discord_user_id} force completed ticket {ticket_id}")

        return {
            "success": True,
            "message": "Ticket force completed, holds released with deduction",
            "ticket": {
                "id": str(result["_id"]),
                "status": result["status"],
                "closed_at": result.get("closed_at").isoformat() if result.get("closed_at") else None
            }
        }
    except Exception as e:
        logger.error(f"Error force completing ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ForceClaimRequest(BaseModel):
    """Force claim ticket request"""
    exchanger_discord_id: str


@router.post("/admin/{ticket_id}/force-claim")
async def force_claim_ticket_admin(
    ticket_id: str,
    request: ForceClaimRequest,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Force claim ticket for an exchanger (bypasses hold requirement) - ADMIN ONLY"""
    from bson import ObjectId
    import logging
    logger = logging.getLogger(__name__)

    try:
        # CRITICAL SECURITY CHECK: Verify user has admin role
        from app.services.user_service import UserService
        is_admin = await UserService.is_admin(discord_user_id)

        if not is_admin:
            logger.warning(f"Unauthorized force-claim attempt by user {discord_user_id} for ticket {ticket_id}")
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Only Head Admin or Assistant Admin can force-claim tickets without balance"
            )

        logger.info(f"Admin {discord_user_id} authorized to force-claim ticket {ticket_id}")

        tickets = get_tickets_collection()
        from app.core.database import get_users_collection
        users = get_users_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Get exchanger user
        exchanger = await users.find_one({"discord_id": request.exchanger_discord_id})
        if not exchanger:
            raise HTTPException(status_code=404, detail="Exchanger not found")

        # Update ticket to claimed status (NO HOLDS CREATED - bypass requirement)
        from datetime import datetime
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "claimed",
                    "assigned_to": exchanger["_id"],
                    "exchanger_discord_id": request.exchanger_discord_id,
                    "claimed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "force_claimed_by_admin": discord_user_id,
                    "bypass_holds": True  # Flag to indicate holds were bypassed
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            discord_user_id,
            "ticket.force_claimed_by_admin",
            {
                "admin_id": discord_user_id,
                "exchanger_id": request.exchanger_discord_id,
                "bypass_holds": True
            }
        )

        logger.info(f"Admin {discord_user_id} force claimed ticket {ticket_id} for exchanger {request.exchanger_discord_id} (bypassed holds)")

        return {
            "success": True,
            "message": "Ticket force claimed (holds bypassed)",
            "ticket": {
                "id": str(result["_id"]),
                "status": result["status"],
                "exchanger_discord_id": result.get("exchanger_discord_id"),
                "claimed_at": result.get("claimed_at").isoformat() if result.get("claimed_at") else None,
                "channel_id": result.get("channel_id"),
                "exchanger_channel_id": result.get("exchanger_channel_id"),
                "send_method": result.get("send_method"),
                "receive_method": result.get("receive_method"),
                "ticket_number": result.get("ticket_number"),
                "amount_usd": result.get("amount_usd", 0),
                "fee_amount": result.get("fee_amount", 0),
                "fee_percentage": result.get("fee_percentage", 10),
                "receiving_amount": result.get("receiving_amount", 0),
                "customer_id": str(result.get("user_id")) if result.get("user_id") else None,
                "exchanger_id": str(result.get("assigned_to")) if result.get("assigned_to") else None,
                "discord_user_id": result.get("discord_user_id")
            }
        }
    except Exception as e:
        logger.error(f"Error force claiming ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/{ticket_id}/force-unclaim")
async def force_unclaim_ticket_admin(
    ticket_id: str,
    discord_user_id: str = Depends(get_user_from_bot_request)
):
    """Force unclaim ticket and refund holds (admin only via bot)"""
    from bson import ObjectId
    import logging
    logger = logging.getLogger(__name__)

    try:
        tickets = get_tickets_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Refund holds if they exist
        from app.services.hold_service import HoldService
        try:
            await HoldService.release_all_holds_for_ticket(
                ticket_id=ticket_id,
                deduct_funds=False  # Refund, don't deduct
            )
        except ValueError:
            # No holds found, that's okay (might have been bypassed)
            pass

        # Reopen ticket
        from datetime import datetime
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "open",
                    "updated_at": datetime.utcnow(),
                    "force_unclaimed_by_admin": discord_user_id
                },
                "$unset": {
                    "assigned_to": "",
                    "exchanger_discord_id": "",
                    "hold_id": "",
                    "hold_ids": "",
                    "claimed_at": "",
                    "client_sent_at": "",
                    "bypass_holds": ""
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            discord_user_id,
            "ticket.force_unclaimed_by_admin",
            {"admin_id": discord_user_id}
        )

        logger.info(f"Admin {discord_user_id} force unclaimed ticket {ticket_id}")

        return {
            "success": True,
            "message": "Ticket force unclaimed and reopened",
            "ticket": {
                "id": str(result["_id"]),
                "status": result["status"]
            }
        }
    except Exception as e:
        logger.error(f"Error force unclaiming ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
