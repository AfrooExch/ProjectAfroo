"""
Notification Service - Handles completion notifications, DMs, and vouch posting
Triggered when tickets are completed
"""

from typing import Dict, Optional
from bson import ObjectId
import logging
from datetime import datetime

from app.core.database import get_tickets_collection, get_users_collection

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling ticket completion notifications"""

    @staticmethod
    async def trigger_completion_notifications(ticket_id: str) -> Dict:
        """
        Trigger all completion notifications for a ticket
        This creates a notification record that the bot will pick up

        Args:
            ticket_id: Ticket ID that was completed

        Returns:
            Notification details
        """
        tickets = get_tickets_collection()
        users = get_users_collection()

        # Get ticket details
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Get client and exchanger IDs
        client_discord_id = ticket.get("discord_user_id", str(ticket.get("user_id")))
        exchanger_id = ticket.get("assigned_to")

        # Get exchanger's Discord ID
        exchanger_discord_id = None
        if exchanger_id:
            exchanger_user = await users.find_one({"_id": ObjectId(exchanger_id)})
            if exchanger_user:
                exchanger_discord_id = exchanger_user.get("discord_id")

        # Create notification record for bot to pick up
        notification = {
            "type": "ticket_completed",
            "ticket_id": ObjectId(ticket_id),
            "ticket_number": ticket.get("ticket_number"),
            "client_discord_id": client_discord_id,
            "exchanger_discord_id": exchanger_discord_id,
            "transcript_html": ticket.get("transcript_html"),
            "transcript_text": ticket.get("transcript_text"),
            "client_vouch_template": ticket.get("client_vouch_template"),
            "exchanger_vouch_template": ticket.get("exchanger_vouch_template"),
            "amount_usd": ticket.get("amount_usd", 0),
            "receiving_amount": ticket.get("receiving_amount", 0),
            "server_fee_collected": ticket.get("server_fee_collected", 0),
            "created_at": datetime.utcnow(),
            "processed": False
        }

        # Store notification in ticket document for bot to pick up
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "completion_notification": notification,
                    "notification_pending": True
                }
            }
        )

        logger.info(
            f"Ticket {ticket_id}: Completion notifications queued for bot processing"
        )

        return {
            "status": "queued",
            "notification": {
                "client_discord_id": client_discord_id,
                "exchanger_discord_id": exchanger_discord_id,
                "has_transcript": bool(ticket.get("transcript_html")),
                "has_vouches": bool(ticket.get("client_vouch_template"))
            }
        }

    @staticmethod
    async def mark_notification_processed(ticket_id: str) -> None:
        """
        Mark completion notification as processed by bot

        Args:
            ticket_id: Ticket ID
        """
        tickets = get_tickets_collection()

        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "notification_pending": False,
                    "notification_processed_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"Ticket {ticket_id}: Completion notifications marked as processed")
