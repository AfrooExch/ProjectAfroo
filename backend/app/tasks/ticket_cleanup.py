"""
Ticket Cleanup Background Task
Automatically closes tickets that have been unclaimed for more than 12 hours
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict

from app.core.database import get_tickets_collection
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


async def close_old_unclaimed_tickets():
    """
    Find and close tickets that have been open/unclaimed for more than 12 hours.

    Runs periodically (every hour) to check for stale tickets.
    Only closes tickets that are still in 'open', 'pending', or 'awaiting_claim' status.
    Does NOT close claimed tickets.
    """
    try:
        tickets = get_tickets_collection()

        # Calculate cutoff time (12 hours ago)
        cutoff_time = datetime.utcnow() - timedelta(hours=12)

        # Find unclaimed tickets older than 12 hours
        # Status must be one of: open, pending, awaiting_claim
        # Must NOT have assigned_to or exchanger_discord_id (not claimed)
        query = {
            "status": {"$in": ["open", "pending", "awaiting_claim"]},
            "created_at": {"$lt": cutoff_time},
            "$or": [
                {"assigned_to": None},
                {"assigned_to": {"$exists": False}},
                {"exchanger_discord_id": None},
                {"exchanger_discord_id": {"$exists": False}}
            ]
        }

        old_tickets = await tickets.find(query).to_list(length=None)

        if not old_tickets:
            logger.debug("No unclaimed tickets older than 12 hours found")
            return {
                "success": True,
                "closed_count": 0,
                "tickets_closed": []
            }

        logger.info(f"Found {len(old_tickets)} unclaimed tickets older than 12 hours - closing them")

        closed_tickets = []

        for ticket in old_tickets:
            ticket_id = str(ticket["_id"])
            ticket_number = ticket.get("ticket_number", "Unknown")
            created_at = ticket.get("created_at")

            try:
                # Close the ticket with auto-close reason
                from bson.objectid import ObjectId

                result = await tickets.find_one_and_update(
                    {"_id": ObjectId(ticket_id)},
                    {
                        "$set": {
                            "status": "closed",
                            "closed_at": datetime.utcnow(),
                            "close_reason": "Auto-closed: No exchanger claimed within 12 hours",
                            "auto_closed": True,
                            "updated_at": datetime.utcnow()
                        }
                    },
                    return_document=True
                )

                if result:
                    closed_tickets.append({
                        "ticket_id": ticket_id,
                        "ticket_number": ticket_number,
                        "created_at": created_at.isoformat() if created_at else None,
                        "age_hours": (datetime.utcnow() - created_at).total_seconds() / 3600 if created_at else None
                    })

                    logger.info(f"Auto-closed ticket #{ticket_number} (ID: {ticket_id}) - unclaimed for {closed_tickets[-1]['age_hours']:.1f} hours")

            except Exception as e:
                logger.error(f"Failed to auto-close ticket #{ticket_number} (ID: {ticket_id}): {e}", exc_info=True)
                continue

        logger.info(f"Auto-close task completed: {len(closed_tickets)}/{len(old_tickets)} tickets closed successfully")

        return {
            "success": True,
            "closed_count": len(closed_tickets),
            "tickets_closed": closed_tickets
        }

    except Exception as e:
        logger.error(f"Error in auto-close task: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "closed_count": 0
        }


async def run_cleanup_task():
    """
    Wrapper function to run the cleanup task.
    This is called by the scheduler.
    """
    logger.info("Starting ticket auto-close cleanup task...")
    result = await close_old_unclaimed_tickets()

    if result["success"]:
        if result["closed_count"] > 0:
            logger.info(f"Cleanup task completed: {result['closed_count']} tickets auto-closed")
        else:
            logger.debug("Cleanup task completed: No tickets needed closing")
    else:
        logger.error(f"Cleanup task failed: {result.get('error', 'Unknown error')}")

    return result
