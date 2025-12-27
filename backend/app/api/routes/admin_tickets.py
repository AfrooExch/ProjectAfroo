"""
Admin Ticket Management Routes - Force actions for tickets
HEAD ADMIN & ASSISTANT ADMIN
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel

from app.api.dependencies import require_assistant_admin_or_higher, require_head_admin, require_assistant_admin_or_higher_bot
from app.core.database import get_tickets_collection, get_users_collection, get_db_collection, get_audit_logs_collection

router = APIRouter(tags=["Admin - Tickets"])
logger = logging.getLogger(__name__)


class AddUserToTicketRequest(BaseModel):
    """Add user as participant to ticket"""
    ticket_id: str
    discord_id: str


class ForceClaimRequest(BaseModel):
    """Force claim ticket for exchanger"""
    ticket_id: str
    exchanger_discord_id: str


class ForceCloseRequest(BaseModel):
    """Force close ticket"""
    ticket_id: str
    reason: str
    release_holds: bool = True


class ForceChangeAmountRequest(BaseModel):
    """Force change amount"""
    new_amount: float
    reason: str


class ForceChangeFeeRequest(BaseModel):
    """Force change fee"""
    new_fee_percentage: float
    reason: str


@router.get("/tickets/all")
async def get_all_tickets(
    status: Optional[str] = None,
    ticket_type: Optional[str] = None,
    limit: int = 100,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Get all tickets with filters (ADMIN)"""
    tickets = get_tickets_collection()

    query = {}
    if status:
        query["status"] = status
    if ticket_type:
        query["type"] = ticket_type

    cursor = tickets.find(query).sort("created_at", -1).limit(limit)
    ticket_list = await cursor.to_list(length=limit)

    return {
        "tickets": [
            {
                "id": str(t["_id"]),
                "ticket_number": t.get("ticket_number"),
                "type": t.get("type"),
                "status": t["status"],
                "user_id": str(t.get("user_id")) if t.get("user_id") else None,
                "exchanger_id": str(t["exchanger_id"]) if t.get("exchanger_id") else None,
                "amount_usd": float(t.get("amount_usd", 0)),
                "send_method": t.get("send_method"),
                "receive_method": t.get("receive_method"),
                "channel_id": str(t.get("channel_id")) if t.get("channel_id") else None,
                "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
                "updated_at": t["updated_at"].isoformat() if t.get("updated_at") else None
            }
            for t in ticket_list
        ],
        "count": len(ticket_list)
    }


@router.post("/tickets/add-user")
async def add_user_to_ticket(
    request: AddUserToTicketRequest,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Add user as participant to ticket (ADMIN)"""
    tickets = get_tickets_collection()
    users = get_users_collection()
    audit_logs = get_audit_logs_collection()

    # Get ticket
    ticket = await tickets.find_one({"_id": ObjectId(request.ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get user
    user = await users.find_one({"discord_id": request.discord_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Add user to participants list
    participants = ticket.get("participants", [])
    if request.discord_id not in participants:
        participants.append(request.discord_id)

        await tickets.update_one(
            {"_id": ObjectId(request.ticket_id)},
            {
                "$set": {
                    "participants": participants,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Log action
        await audit_logs.insert_one({
            "actor_type": "admin",
            "actor_id": admin_id,
            "action": "ticket_add_user",
            "resource_type": "ticket",
            "resource_id": ObjectId(request.ticket_id),
            "details": {
                "user_discord_id": request.discord_id,
                "ticket_number": ticket.get("ticket_number")
            },
            "created_at": datetime.utcnow()
        })

    return {
        "success": True,
        "message": "User added to ticket",
        "ticket_id": request.ticket_id,
        "participants": participants
    }


@router.post("/tickets/remove-user")
async def remove_user_from_ticket(
    request: AddUserToTicketRequest,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Remove user from ticket participants (ADMIN)"""
    tickets = get_tickets_collection()
    audit_logs = get_audit_logs_collection()

    # Get ticket
    ticket = await tickets.find_one({"_id": ObjectId(request.ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Remove user from participants
    participants = ticket.get("participants", [])
    if request.discord_id in participants:
        participants.remove(request.discord_id)

        await tickets.update_one(
            {"_id": ObjectId(request.ticket_id)},
            {
                "$set": {
                    "participants": participants,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Log action
        await audit_logs.insert_one({
            "actor_type": "admin",
            "actor_id": admin_id,
            "action": "ticket_remove_user",
            "resource_type": "ticket",
            "resource_id": ObjectId(request.ticket_id),
            "details": {
                "user_discord_id": request.discord_id,
                "ticket_number": ticket.get("ticket_number")
            },
            "created_at": datetime.utcnow()
        })

    return {
        "success": True,
        "message": "User removed from ticket",
        "ticket_id": request.ticket_id,
        "participants": participants
    }


@router.post("/tickets/force-claim")
async def force_claim_ticket(
    request: ForceClaimRequest,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Force claim ticket for exchanger (bypasses balance checks) (ADMIN)"""
    tickets = get_tickets_collection()
    users = get_users_collection()
    audit_logs = get_audit_logs_collection()

    # Get ticket
    ticket = await tickets.find_one({"_id": ObjectId(request.ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Admin can force claim ticket in ANY state (no restrictions)
    # This includes: open, pending, waiting, claimed, pending_payout, etc.

    # Get exchanger
    exchanger = await users.find_one({"discord_id": request.exchanger_discord_id})
    if not exchanger:
        raise HTTPException(status_code=404, detail="Exchanger not found")

    # Get ticket amount
    amount_usd = ticket.get("amount_usd", 0)

    # Create holds but mark them as force-claimed (admin bypassed balance checks)
    # This ensures the workflow tracks the funds but doesn't require available balance
    from app.services.hold_service import HoldService
    from decimal import Decimal

    holds = []
    try:
        # Try to create holds normally first
        holds = await HoldService.create_multi_currency_hold(
            ticket_id=request.ticket_id,
            user_id=request.exchanger_discord_id,
            amount_usd=Decimal(str(amount_usd))
        )
    except Exception as e:
        # If holds fail due to insufficient balance, create a placeholder hold record
        # This allows the workflow to continue but marks it as admin-forced
        logger.warning(f"Force claim: Could not create holds for ticket {request.ticket_id}: {e}")
        # Create empty hold array - admin is bypassing the hold requirement
        holds = []

    # Store hold IDs if any were created
    first_hold_id = holds[0]["_id"] if holds else None
    hold_ids = [str(h["_id"]) for h in holds] if holds else []

    # Force claim with full workflow fields (skip balance checks)
    await tickets.update_one(
        {"_id": ObjectId(request.ticket_id)},
        {
            "$set": {
                "status": "claimed",
                "assigned_to": exchanger["_id"],  # Critical for bot permissions
                "exchanger_discord_id": request.exchanger_discord_id,  # Critical for Discord lookups
                "exchanger_id": exchanger["_id"],  # Legacy field
                "hold_id": first_hold_id,  # Legacy field
                "hold_ids": hold_ids,  # Multi-currency hold support
                "claimed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "force_claimed": True,
                "force_claimed_by": admin_id
            }
        }
    )

    # Log action with ticket service
    from app.services.ticket_service import TicketService
    await TicketService.log_action(
        request.ticket_id,
        request.exchanger_discord_id,
        "ticket.force_claimed",
        {
            "admin_id": admin_id,
            "amount_usd": str(amount_usd),
            "holds_created": len(holds),
            "bypassed_balance_checks": True
        }
    )

    # Log action in audit logs
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": admin_id,
        "action": "ticket_force_claim",
        "resource_type": "ticket",
        "resource_id": ObjectId(request.ticket_id),
        "details": {
            "exchanger_discord_id": request.exchanger_discord_id,
            "ticket_number": ticket.get("ticket_number"),
            "bypassed_checks": True,
            "holds_created": len(holds)
        },
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "message": "Ticket force claimed with full workflow",
        "ticket_id": request.ticket_id,
        "exchanger_discord_id": request.exchanger_discord_id,
        "holds_created": len(holds)
    }


@router.post("/tickets/force-unclaim")
async def force_unclaim_ticket(
    ticket_id: str,
    release_holds: bool = True,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Force unclaim ticket (releases holds and moves back to pending) (ADMIN)"""
    from app.services.hold_service import HoldService

    tickets = get_tickets_collection()
    audit_logs = get_audit_logs_collection()

    # Get ticket
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    exchanger_id = ticket.get("exchanger_id")

    # Release holds if requested
    if release_holds and exchanger_id:
        try:
            await HoldService.release_holds_for_ticket(ticket_id)
        except Exception as e:
            # Log error but continue
            pass

    # Unclaim ticket
    await tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "status": "pending",
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "exchanger_id": "",
                "claimed_at": ""
            }
        }
    )

    # Log action
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": admin_id,
        "action": "ticket_force_unclaim",
        "resource_type": "ticket",
        "resource_id": ObjectId(ticket_id),
        "details": {
            "previous_exchanger_id": str(exchanger_id) if exchanger_id else None,
            "ticket_number": ticket.get("ticket_number"),
            "holds_released": release_holds
        },
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "message": "Ticket unclaimed and moved to pending",
        "ticket_id": ticket_id,
        "holds_released": release_holds
    }


@router.post("/tickets/force-close")
async def force_close_ticket(
    request: ForceCloseRequest,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Force close ticket (completes workflow forcefully) (ADMIN)"""
    from app.services.hold_service import HoldService

    tickets = get_tickets_collection()
    audit_logs = get_audit_logs_collection()

    # Get ticket
    ticket = await tickets.find_one({"_id": ObjectId(request.ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Release holds if requested
    if request.release_holds:
        try:
            await HoldService.release_holds_for_ticket(request.ticket_id)
        except Exception as e:
            pass

    # Force close
    await tickets.update_one(
        {"_id": ObjectId(request.ticket_id)},
        {
            "$set": {
                "status": "cancelled",
                "closed_at": datetime.utcnow(),
                "closed_reason": request.reason,
                "force_closed": True,
                "force_closed_by": admin_id,
                "updated_at": datetime.utcnow()
            }
        }
    )

    # Log action
    await audit_logs.insert_one({
        "actor_type": "admin",
        "actor_id": admin_id,
        "action": "ticket_force_close",
        "resource_type": "ticket",
        "resource_id": ObjectId(request.ticket_id),
        "details": {
            "reason": request.reason,
            "ticket_number": ticket.get("ticket_number"),
            "previous_status": ticket["status"],
            "holds_released": request.release_holds
        },
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "message": "Ticket force closed",
        "ticket_id": request.ticket_id,
        "reason": request.reason
    }


@router.post("/tickets/force-complete")
async def force_complete_ticket(
    request: dict,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """
    Force complete ticket with full workflow (ADMIN)
    Generates transcript, collects server fee, releases holds
    Bypasses approval requirements
    """
    from app.services.hold_service import HoldService
    from app.services.transcript_service import TranscriptService
    from app.services.server_fee_service import ServerFeeService

    tickets = get_tickets_collection()
    audit_logs = get_audit_logs_collection()

    ticket_id = request.get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id required")

    # Get ticket
    ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    try:
        # Generate transcript
        transcript = await TranscriptService.generate_transcript(ticket_id)

        # Generate vouch templates for both parties
        client_vouch = TranscriptService.generate_vouch_template(ticket, "client")
        exchanger_vouch = TranscriptService.generate_vouch_template(ticket, "exchanger")

        # Get exchanger ID for fee collection and hold release
        exchanger_user_id = ticket.get("assigned_to")

        # Collect server fee from exchanger
        fee_result = None
        if exchanger_user_id:
            try:
                fee_result = await ServerFeeService.collect_server_fee(
                    ticket_id,
                    str(exchanger_user_id)
                )
                logger.info(f"Ticket {ticket_id}: Server fee collected - ${fee_result.get('amount_usd', 0):.2f}")
            except Exception as e:
                logger.error(f"Ticket {ticket_id}: Server fee collection failed: {e}")
                # Fee marked as pending - will be collected before next withdrawal

        # Release hold on exchanger's funds
        if ticket.get("hold_id"):
            try:
                await HoldService.release_hold(str(ticket["hold_id"]))
                logger.info(f"Ticket {ticket_id}: Hold released for exchanger")
            except Exception as e:
                logger.error(f"Ticket {ticket_id}: Hold release failed: {e}")

        # Close ticket with transcript data
        update_data = {
            "$set": {
                "status": "completed",
                "closed_at": datetime.utcnow(),
                "closed_reason": "Force completed by admin",
                "transcript_html": transcript["html"],
                "transcript_text": transcript["text"],
                "transcript_generated_at": transcript["generated_at"],
                "client_vouch_template": client_vouch,
                "exchanger_vouch_template": exchanger_vouch,
                "force_completed": True,
                "force_completed_by": admin_id,
                "updated_at": datetime.utcnow()
            }
        }

        # Add server fee info if collected
        if fee_result:
            update_data["$set"]["server_fee_collected"] = fee_result.get("amount_usd", 0)
            update_data["$set"]["server_fee_status"] = fee_result.get("status", "collected")

        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            update_data
        )

        logger.info(f"Ticket {ticket_id}: Force completed successfully with full workflow")

        # Trigger completion notifications for bot to process
        from app.services.notification_service import NotificationService

        try:
            await NotificationService.trigger_completion_notifications(ticket_id)
            logger.info(f"Ticket {ticket_id}: Completion notifications triggered")
        except Exception as e:
            logger.error(f"Ticket {ticket_id}: Failed to trigger notifications: {e}")
            # Don't fail the completion if notifications fail

        # Log action
        await audit_logs.insert_one({
            "actor_type": "admin",
            "actor_id": admin_id,
            "action": "ticket_force_complete",
            "resource_type": "ticket",
            "resource_id": ObjectId(ticket_id),
            "details": {
                "ticket_number": ticket.get("ticket_number"),
                "previous_status": ticket["status"],
                "transcript_generated": True,
                "fee_collected": fee_result is not None,
                "holds_released": ticket.get("hold_id") is not None
            },
            "created_at": datetime.utcnow()
        })

        return {
            "success": True,
            "message": "Ticket force completed with full workflow",
            "ticket_id": ticket_id,
            "transcript_generated": True,
            "server_fee_collected": fee_result is not None,
            "holds_released": ticket.get("hold_id") is not None
        }

    except Exception as e:
        logger.error(f"Failed to force complete ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to force complete ticket: {str(e)}")


@router.post("/tickets/admin/{ticket_id}/force-change-amount")
async def force_change_amount(
    ticket_id: str,
    request: ForceChangeAmountRequest,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Admin force-changes ticket amount without approval (ADMIN)"""
    from app.services.ticket_action_service import TicketActionService

    try:
        result = await TicketActionService.admin_force_change_amount(
            ticket_id=ticket_id,
            new_amount=request.new_amount,
            admin_id=admin_id,
            reason=request.reason
        )

        # Log action
        audit_logs = get_audit_logs_collection()
        await audit_logs.insert_one({
            "actor_type": "admin",
            "actor_id": admin_id,
            "action": "ticket_force_change_amount",
            "resource_type": "ticket",
            "resource_id": ObjectId(ticket_id),
            "details": {
                "new_amount": request.new_amount,
                "reason": request.reason,
                "ticket_number": result.get("ticket_number")
            },
            "created_at": datetime.utcnow()
        })

        return {
            "message": "Amount changed (admin bypass)",
            "ticket": {
                "id": str(result["_id"]),
                "amount_usd": result.get("amount_usd"),
                "fee_amount": result.get("fee_amount"),
                "receiving_amount": result.get("receiving_amount")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error forcing amount change: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tickets/admin/{ticket_id}/force-change-fee")
async def force_change_fee(
    ticket_id: str,
    request: ForceChangeFeeRequest,
    admin_id: str = Depends(require_assistant_admin_or_higher_bot)
):
    """Admin force-changes ticket fee without approval (ADMIN)"""
    from app.services.ticket_action_service import TicketActionService

    try:
        result = await TicketActionService.admin_force_change_fee(
            ticket_id=ticket_id,
            new_fee_percentage=request.new_fee_percentage,
            admin_id=admin_id,
            reason=request.reason
        )

        # Log action
        audit_logs = get_audit_logs_collection()
        await audit_logs.insert_one({
            "actor_type": "admin",
            "actor_id": admin_id,
            "action": "ticket_force_change_fee",
            "resource_type": "ticket",
            "resource_id": ObjectId(ticket_id),
            "details": {
                "new_fee_percentage": request.new_fee_percentage,
                "reason": request.reason,
                "ticket_number": result.get("ticket_number")
            },
            "created_at": datetime.utcnow()
        })

        return {
            "message": "Fee changed (admin bypass)",
            "ticket": {
                "id": str(result["_id"]),
                "fee_percentage": result.get("fee_percentage"),
                "fee_amount": result.get("fee_amount"),
                "receiving_amount": result.get("receiving_amount")
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error forcing fee change: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
