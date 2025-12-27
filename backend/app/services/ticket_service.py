"""
Ticket Service - Business logic for support ticket operations
Integrates with hold system for exchanger fund locking
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from bson import ObjectId

logger = logging.getLogger(__name__)

from app.core.database import (
    get_tickets_collection,
    get_audit_logs_collection,
    get_next_sequence
)
from app.models.ticket import Ticket, TicketCreate, TicketMessageCreate, ExchangeTicketCreate
from app.services.hold_service import HoldService
from app.services.tos_service import TOSService
from app.services.milestone_service import MilestoneService


class TicketService:
    """Service for ticket operations"""

    @staticmethod
    async def create_ticket(user_id: str, ticket_data: TicketCreate) -> dict:
        """Create new support ticket"""
        tickets = get_tickets_collection()

        # Get next ticket number
        ticket_number = await get_next_sequence("ticket_number")

        # Check if this is an exchange ticket requiring TOS
        is_exchange_ticket = ticket_data.type == "exchange"
        requires_tos = is_exchange_ticket and ticket_data.send_method and ticket_data.receive_method

        # Set initial status
        initial_status = "awaiting_tos" if requires_tos else "open"

        ticket_dict = {
            "ticket_number": ticket_number,
            "user_id": ObjectId(user_id),
            "partner_id": None,
            "assigned_to": None,
            "type": ticket_data.type,
            "subject": ticket_data.subject,
            "description": ticket_data.description,
            "status": initial_status,
            "priority": "medium",
            "exchange_id": ObjectId(ticket_data.exchange_id) if ticket_data.exchange_id else None,
            "hold_id": None,
            "messages": [
                {
                    "id": str(ObjectId()),
                    "user_id": ObjectId(user_id),
                    "message": ticket_data.description,
                    "is_internal": False,
                    "attachments": [],
                    "created_at": datetime.utcnow()
                }
            ],
            "tags": [],
            "satisfaction_rating": None,
            "satisfaction_feedback": None,
            "created_at": datetime.utcnow(),
            "first_response_at": None,
            "resolved_at": None,
            "closed_at": None,
            "claimed_at": None,
            "updated_at": datetime.utcnow()
        }

        # Add exchange ticket fields
        if is_exchange_ticket:
            ticket_dict.update({
                "send_method": ticket_data.send_method,
                "receive_method": ticket_data.receive_method,
                "amount": ticket_data.amount
            })

        # Add TOS workflow fields if required
        if requires_tos:
            # Get required TOS for this ticket
            required_tos = await TOSService.get_tos_for_ticket(
                send_method=ticket_data.send_method,
                receive_method=ticket_data.receive_method
            )

            # Extract TOS IDs
            tos_ids = [tos["_id"] for tos in required_tos.values()]

            ticket_dict.update({
                "tos_required": True,
                "tos_deadline": datetime.utcnow() + timedelta(minutes=10),  # 10 minute deadline
                "tos_accepted_at": None,
                "tos_ping_count": 0,
                "required_tos_ids": tos_ids
            })

        result = await tickets.insert_one(ticket_dict)
        ticket_dict["_id"] = result.inserted_id

        # Log ticket creation
        await TicketService.log_action(
            str(result.inserted_id),
            user_id,
            "ticket.created",
            {
                "ticket_number": ticket_number,
                "type": ticket_data.type,
                "requires_tos": requires_tos
            }
        )

        return ticket_dict

    @staticmethod
    async def create_exchange_ticket(exchange_data: ExchangeTicketCreate) -> dict:
        """Create new exchange ticket with TOS workflow"""
        from app.core.database import get_users_collection

        tickets = get_tickets_collection()
        users = get_users_collection()

        # Get next ticket number
        ticket_number = await get_next_sequence("ticket_number")

        # Look up user by Discord ID to get their MongoDB ObjectId
        user = await users.find_one({"discord_id": exchange_data.user_id})
        if not user:
            # User doesn't exist yet - create a basic user record
            user_dict = {
                "discord_id": exchange_data.user_id,
                "username": exchange_data.username,
                "roles": [],
                "status": "active",
                "created_at": datetime.utcnow()
            }
            result = await users.insert_one(user_dict)
            user_mongo_id = result.inserted_id
        else:
            user_mongo_id = user["_id"]

        # Get required TOS for this exchange
        required_tos = await TOSService.get_tos_for_ticket(
            send_method=exchange_data.send_method,
            receive_method=exchange_data.receive_method
        )

        # Extract TOS IDs
        tos_ids = [str(tos["_id"]) for tos in required_tos.values()]

        # Build ticket document
        ticket_dict = {
            "ticket_number": ticket_number,
            "user_id": user_mongo_id,  # Use MongoDB ObjectId
            "discord_user_id": exchange_data.user_id,  # Store Discord ID separately
            "partner_id": None,
            "assigned_to": None,
            "type": "exchange",
            "subject": f"Exchange Ticket #{ticket_number} - {exchange_data.username}",
            "description": f"Exchange: {exchange_data.send_method} → {exchange_data.receive_method} | Amount: ${exchange_data.amount_usd:.2f}",
            "status": "awaiting_tos",
            "priority": "medium",
            "exchange_id": None,
            "hold_id": None,
            # Exchange specific fields
            "send_method": exchange_data.send_method,
            "send_crypto": exchange_data.send_crypto,
            "receive_method": exchange_data.receive_method,
            "receive_crypto": exchange_data.receive_crypto,
            "amount_usd": exchange_data.amount_usd,
            "fee_amount": exchange_data.fee_amount,
            "fee_percentage": exchange_data.fee_percentage,
            "receiving_amount": exchange_data.receiving_amount,
            # TOS workflow
            "tos_required": True,
            "tos_deadline": datetime.utcnow() + timedelta(minutes=10),
            "tos_accepted_at": None,
            "tos_ping_count": 0,
            "required_tos_ids": tos_ids,
            # Messages
            "messages": [],
            "tags": ["v4", "exchange"],
            "satisfaction_rating": None,
            "satisfaction_feedback": None,
            # Timestamps
            "created_at": datetime.utcnow(),
            "first_response_at": None,
            "resolved_at": None,
            "closed_at": None,
            "claimed_at": None,
            "updated_at": datetime.utcnow()
        }

        # Insert ticket
        result = await tickets.insert_one(ticket_dict)
        ticket_dict["_id"] = result.inserted_id

        # Log ticket creation
        await TicketService.log_action(
            str(result.inserted_id),
            str(user_mongo_id),  # Use MongoDB user ID, not Discord ID
            "exchange_ticket.created",
            {
                "ticket_number": ticket_number,
                "send_method": exchange_data.send_method,
                "receive_method": exchange_data.receive_method,
                "amount_usd": exchange_data.amount_usd
            }
        )

        return ticket_dict

    @staticmethod
    async def add_message(
        ticket_id: str,
        user_id: str,
        message_data: TicketMessageCreate
    ) -> dict:
        """Add message to ticket"""
        tickets = get_tickets_collection()

        message = {
            "id": str(ObjectId()),
            "user_id": ObjectId(user_id),
            "message": message_data.message,
            "is_internal": message_data.is_internal,
            "attachments": [],
            "created_at": datetime.utcnow()
        }

        # Update ticket
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.utcnow()}
            },
            return_document=True
        )

        # If this is first staff response, update first_response_at
        if message_data.is_internal and not result.get("first_response_at"):
            await tickets.update_one(
                {"_id": ObjectId(ticket_id)},
                {"$set": {"first_response_at": datetime.utcnow()}}
            )

        await TicketService.log_action(
            ticket_id,
            user_id,
            "ticket.message_added",
            {"is_internal": message_data.is_internal}
        )

        return result

    @staticmethod
    async def close_ticket(ticket_id: str, user_id: str) -> dict:
        """Close a ticket - releases any active holds (refund, no deduction)"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # If ticket was claimed, refund ALL holds
        hold_refunded = False
        if ticket.get("status") in ["claimed", "client_sent", "payout_pending"]:
            try:
                from app.services.hold_service import HoldService
                await HoldService.release_all_holds_for_ticket(
                    ticket_id=ticket_id,
                    deduct_funds=False  # Close without completion: refund, don't deduct
                )
                hold_refunded = True
                logger.info(f"Ticket {ticket_id}: Released holds on close")
            except Exception as e:
                logger.error(f"Ticket {ticket_id}: Error releasing holds on close: {e}")

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            user_id,
            "ticket.closed",
            {"hold_refunded": hold_refunded}
        )

        return result

    @staticmethod
    async def assign_ticket(ticket_id: str, staff_id: str) -> dict:
        """Assign ticket to staff member"""
        tickets = get_tickets_collection()

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "assigned_to": ObjectId(staff_id),
                    "status": "in_progress",
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            staff_id,
            "ticket.assigned",
            {"staff_id": staff_id}
        )

        return result

    @staticmethod
    async def list_tickets(
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """List tickets with filters"""
        tickets = get_tickets_collection()

        query = {}
        if user_id:
            query["user_id"] = ObjectId(user_id)
        if status:
            query["status"] = status
        if assigned_to:
            query["assigned_to"] = ObjectId(assigned_to)

        cursor = tickets.find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    async def claim_ticket(
        ticket_id: str,
        exchanger_id: str,
        amount_usd: Decimal
    ) -> dict:
        """
        Claim ticket as exchanger - creates multi-currency hold to lock funds (V4 System).
        Automatically uses available funds from ANY deposits to reach required amount.

        Args:
            ticket_id: Ticket MongoDB _id
            exchanger_id: Discord user ID (string)
            amount_usd: Ticket amount in USD (Decimal)
        """
        tickets = get_tickets_collection()

        # Look up exchanger's MongoDB ObjectId from Discord ID
        from app.core.database import get_users_collection
        users = get_users_collection()
        exchanger_user = await users.find_one({"discord_id": exchanger_id})
        exchanger_object_id = exchanger_user["_id"] if exchanger_user else None

        # ATOMIC CLAIM: Check status AND update in one operation (prevents race condition)
        # This ensures only ONE exchanger can claim the ticket, even if clicked simultaneously
        pre_claim_result = await tickets.find_one_and_update(
            {
                "_id": ObjectId(ticket_id),
                "status": {"$in": ["open", "pending", "awaiting_claim"]},  # Only claim if available
                "assigned_to": None  # And not already assigned
            },
            {
                "$set": {
                    "status": "claiming",  # Temporary status to prevent double-claim
                    "assigned_to": exchanger_object_id,
                    "exchanger_discord_id": exchanger_id,
                    "claim_started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=False  # Return old document to verify it was available
        )

        if not pre_claim_result:
            # Ticket was already claimed or doesn't exist
            ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            else:
                raise ValueError(f"Ticket {ticket_id} is no longer available (status: {ticket['status']})")

        # Now create holds (safe because we atomically claimed above)
        try:
            # CRITICAL: Sync on-chain balances BEFORE creating holds to prevent ghost funds
            from app.services.exchanger_service import ExchangerService
            logger.info(f"Ticket {ticket_id}: Syncing all deposit balances for exchanger {exchanger_id}")

            try:
                # Get all exchanger deposits
                from app.core.database import get_db_collection
                deposits_db = await get_db_collection("exchanger_deposits")
                deposits = await deposits_db.find({"user_id": exchanger_id}).to_list(length=None)

                # Sync each deposit's balance with blockchain
                for deposit in deposits:
                    try:
                        currency = deposit.get("currency")
                        await ExchangerService.sync_deposit_balance(exchanger_id, currency)
                        logger.info(f"Synced {currency} balance for {exchanger_id}")
                    except Exception as sync_err:
                        logger.warning(f"Failed to sync {deposit.get('currency')}: {sync_err}")

                logger.info(f"Completed balance sync for exchanger {exchanger_id}")
            except Exception as sync_err:
                logger.error(f"Error during balance sync: {sync_err}")
                # Continue anyway - use cached balances

            from app.services.hold_service import HoldService
            holds = await HoldService.create_multi_currency_hold(
                ticket_id=ticket_id,
                user_id=exchanger_id,
                amount_usd=amount_usd
            )

            # Store first hold ID for legacy compatibility
            first_hold_id = holds[0]["_id"] if holds else None

            # Finalize claim with hold information
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "status": "claimed",
                        "hold_id": first_hold_id,  # Legacy field
                        "hold_ids": [str(h["_id"]) for h in holds],  # New field for multi-currency
                        "claimed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {"claim_started_at": ""}
                },
                return_document=True
            )

        except Exception as e:
            # Rollback: Release the claim if hold creation fails
            logger.error(f"Failed to create holds for ticket {ticket_id}: {e}")
            await tickets.update_one(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "status": pre_claim_result["status"],  # Restore original status
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {
                        "assigned_to": "",
                        "exchanger_discord_id": "",
                        "claim_started_at": ""
                    }
                }
            )
            raise ValueError(f"Failed to claim ticket: {str(e)}")

        # Calculate total server fee across all holds
        total_server_fee = sum(Decimal(h["server_fee_usd"]) for h in holds)
        currencies_used = [h["currency"] for h in holds]

        await TicketService.log_action(
            ticket_id,
            exchanger_id,
            "ticket.claimed",
            {
                "amount_usd": str(amount_usd),
                "server_fee_usd": str(total_server_fee),
                "currencies_used": currencies_used,
                "hold_count": len(holds)
            }
        )

        return result

    @staticmethod
    async def complete_ticket(ticket_id: str, user_id: str) -> dict:
        """
        Complete ticket - releases hold and deducts funds + fee (V4 System).
        Called when exchange is successfully completed.
        """
        tickets = get_tickets_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify that only the CLIENT can complete the ticket
        ticket_discord_id = ticket.get("discord_user_id", str(ticket.get("user_id", "")))
        if ticket_discord_id != user_id:
            raise ValueError("Only the client can confirm receipt and complete the ticket")

        # Check if ticket is already completed
        if ticket["status"] == "completed":
            raise ValueError("This ticket has already been completed. Thank you!")

        # Allow completion from claimed, client_sent, or payout_pending statuses
        if ticket["status"] not in ["claimed", "client_sent", "payout_pending"]:
            raise ValueError(f"Ticket {ticket_id} cannot be completed (status: {ticket['status']})")

        # Release ALL holds for ticket (multi-currency support)
        from app.services.hold_service import HoldService
        try:
            await HoldService.release_all_holds_for_ticket(
                ticket_id=ticket_id,
                deduct_funds=True  # Complete ticket: deduct balance + collect fee
            )
        except ValueError as e:
            # Fallback for legacy single-hold tickets
            # Release hold if one exists
            if ticket.get("hold_id"):
                await HoldService.release_hold(
                    hold_id=str(ticket["hold_id"]),
                    deduct_funds=True
                )
            elif not ticket.get("bypass_holds") and not ticket.get("force_claimed"):
                # Only require hold if ticket wasn't force-claimed by admin
                raise ValueError(f"Ticket {ticket_id} has no associated holds")

        # Update ticket status
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "completed",
                    "resolved_at": datetime.utcnow(),
                    "closed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            user_id,
            "ticket.completed",
            {"hold_released": True}
        )

        # Track exchange completion stats
        try:
            from app.services.stats_tracking_service import StatsTrackingService
            from app.services.hold_service import HoldService
            from decimal import Decimal

            # Get all holds to calculate total server fee
            holds = await HoldService.get_holds_by_ticket(ticket_id)
            total_server_fee_usd = sum(Decimal(str(h.get("server_fee_usd", 0))) for h in holds)

            # Track completion with proper user IDs and amounts
            await StatsTrackingService.track_exchange_completion(
                client_id=str(ticket["user_id"]),
                exchanger_id=str(ticket["assigned_to"]) if ticket.get("assigned_to") else None,
                amount_usd=float(ticket.get("amount_usd", 0)),
                fee_amount_usd=float(total_server_fee_usd),
                ticket_id=ticket_id
            )
            logger.info(f"Tracked exchange completion stats for ticket {ticket_id}: client={ticket['user_id']}, exchanger={ticket.get('assigned_to')}, amount=${ticket.get('amount_usd', 0)}, fee=${total_server_fee_usd}")
        except Exception as stats_err:
            logger.error(f"Failed to track exchange completion stats: {stats_err}", exc_info=True)
            # Don't fail ticket completion if stats tracking fails

        # Auto-refresh exchanger deposits after completion (so UI updates immediately)
        if ticket.get("exchanger_discord_id"):
            try:
                from app.services.exchanger_service import ExchangerService
                exchanger_id = ticket["exchanger_discord_id"]

                # Get all currencies that were involved in this ticket
                deposits = await ExchangerService.list_deposits(exchanger_id)

                # Sync all deposits to update UI immediately
                for deposit in deposits:
                    try:
                        await ExchangerService.sync_deposit_balance(exchanger_id, deposit.currency)
                        logger.info(f"Auto-synced {deposit.currency} deposit for exchanger {exchanger_id} after ticket completion")
                    except Exception as sync_err:
                        logger.warning(f"Failed to auto-sync {deposit.currency} for exchanger {exchanger_id}: {sync_err}")
            except Exception as refresh_err:
                logger.error(f"Failed to auto-refresh exchanger deposits after ticket completion: {refresh_err}")
                # Don't fail ticket completion if refresh fails

        # Check and grant milestones for both users
        try:
            # Check for customer (client)
            client_milestones = await MilestoneService.check_and_grant_milestones(
                str(ticket["user_id"])
            )
            if client_milestones:
                logger.info(
                    f"Client earned {len(client_milestones)} milestone(s): "
                    f"{[m['name'] for m in client_milestones]}"
                )

            # Check for exchanger
            if ticket.get("assigned_to"):
                exchanger_milestones = await MilestoneService.check_and_grant_milestones(
                    str(ticket["assigned_to"])
                )
                if exchanger_milestones:
                    logger.info(
                        f"Exchanger earned {len(exchanger_milestones)} milestone(s): "
                        f"{[m['name'] for m in exchanger_milestones]}"
                    )

        except Exception as e:
            # Don't fail ticket completion if milestone check fails
            logger.error(f"Error checking milestones: {e}", exc_info=True)

        return result

    @staticmethod
    async def cancel_ticket(ticket_id: str, user_id: str, reason: str = "") -> dict:
        """
        Cancel ticket - refunds hold if claimed.
        Called when ticket is canceled before completion.
        """
        tickets = get_tickets_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # If ticket was claimed, refund ALL holds
        hold_refunded = False
        try:
            from app.services.hold_service import HoldService
            await HoldService.release_all_holds_for_ticket(
                ticket_id=ticket_id,
                deduct_funds=False  # Cancel: refund, don't deduct
            )
            hold_refunded = True
        except ValueError:
            # Fallback for legacy single-hold tickets
            if ticket.get("hold_id"):
                await HoldService.refund_hold(hold_id=str(ticket["hold_id"]))
                hold_refunded = True

        # Update ticket status
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "canceled",
                    "canceled_reason": reason,
                    "closed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            user_id,
            "ticket.canceled",
            {"reason": reason, "hold_refunded": hold_refunded}
        )

        return result

    @staticmethod
    async def agree_to_tos(
        ticket_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> dict:
        """
        Record user agreement to TOS for exchange ticket.
        Changes ticket status from 'awaiting_tos' to 'open'.
        """
        tickets = get_tickets_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify ownership - check discord_user_id for exchange tickets
        ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))
        if ticket_discord_id != user_id:
            raise ValueError("Not your ticket")

        # Check if ticket requires TOS
        if not ticket.get("tos_required"):
            raise ValueError("This ticket does not require TOS agreement")

        # Check if already agreed
        if ticket.get("tos_accepted_at"):
            raise ValueError("TOS already accepted for this ticket")

        # Check if deadline passed
        if ticket.get("tos_deadline") and datetime.utcnow() > ticket["tos_deadline"]:
            # Auto-close the ticket
            await TicketService.cancel_ticket(
                ticket_id=ticket_id,
                user_id=user_id,
                reason="TOS agreement deadline expired"
            )
            raise ValueError("TOS agreement deadline has expired, ticket closed")

        # Record agreement to all required TOS
        required_tos_ids = ticket.get("required_tos_ids", [])
        for tos_id in required_tos_ids:
            success, message = await TOSService.record_agreement(
                user_id=user_id,
                tos_id=tos_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            if not success and "Already agreed" not in message:
                raise ValueError(f"Failed to record TOS agreement: {message}")

        # Update ticket status
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "open",  # Change from awaiting_tos to open
                    "tos_accepted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await TicketService.log_action(
            ticket_id,
            user_id,
            "ticket.tos_accepted",
            {
                "tos_count": len(required_tos_ids),
                "ip_address": ip_address
            }
        )

        return result

    @staticmethod
    async def monitor_tos_deadlines():
        """
        Monitor tickets awaiting TOS agreement.
        Sends pings at 3, 6, 9 minutes and auto-closes at 10 minutes.
        Called by background task every minute.
        """
        import logging
        logger = logging.getLogger(__name__)

        tickets = get_tickets_collection()

        # Find tickets awaiting TOS
        awaiting_tickets = await tickets.find({
            "status": "awaiting_tos",
            "tos_required": True,
            "tos_accepted_at": None
        }).to_list(length=1000)

        logger.info(f"Checking {len(awaiting_tickets)} tickets awaiting TOS")

        for ticket in awaiting_tickets:
            try:
                created_at = ticket["created_at"]
                tos_deadline = ticket.get("tos_deadline")
                ping_count = ticket.get("tos_ping_count", 0)
                ticket_id = str(ticket["_id"])
                user_id = str(ticket["user_id"])

                # SAFETY CHECK: Skip if ticket was claimed or TOS was accepted
                if ticket.get("assigned_to") or ticket.get("exchanger_discord_id"):
                    logger.info(f"Skipping ticket {ticket_id} - already claimed")
                    continue

                if ticket.get("tos_accepted_at"):
                    logger.info(f"Skipping ticket {ticket_id} - TOS already accepted")
                    continue

                # Calculate time elapsed since creation
                time_elapsed = datetime.utcnow() - created_at
                minutes_elapsed = time_elapsed.total_seconds() / 60

                # Auto-close if past deadline (10 minutes)
                if tos_deadline and datetime.utcnow() >= tos_deadline:
                    logger.info(f"Auto-closing ticket {ticket_id} - TOS deadline expired")
                    await TicketService.cancel_ticket(
                        ticket_id=ticket_id,
                        user_id=user_id,
                        reason="TOS agreement deadline expired (10 minutes)"
                    )
                    # TODO: Send DM to user via Discord bot
                    continue

                # Send pings at 3, 6, 9 minutes
                should_ping = False
                ping_message = ""

                if minutes_elapsed >= 3 and ping_count == 0:
                    should_ping = True
                    ping_message = "⏰ Reminder: 7 minutes left to accept TOS"
                elif minutes_elapsed >= 6 and ping_count == 1:
                    should_ping = True
                    ping_message = "⏰ Reminder: 4 minutes left to accept TOS"
                elif minutes_elapsed >= 9 and ping_count == 2:
                    should_ping = True
                    ping_message = "URGENT: 1 minute left to accept TOS or ticket will be closed!"

                if should_ping:
                    # Increment ping count
                    await tickets.update_one(
                        {"_id": ticket["_id"]},
                        {
                            "$inc": {"tos_ping_count": 1},
                            "$set": {"updated_at": datetime.utcnow()}
                        }
                    )

                    # Add system message to ticket
                    await tickets.update_one(
                        {"_id": ticket["_id"]},
                        {
                            "$push": {
                                "messages": {
                                    "id": str(ObjectId()),
                                    "user_id": ticket["user_id"],  # System message
                                    "message": ping_message,
                                    "is_internal": False,
                                    "attachments": [],
                                    "created_at": datetime.utcnow()
                                }
                            }
                        }
                    )

                    logger.info(f"Sent ping {ping_count + 1} to ticket {ticket_id}")

                    # TODO: Send Discord ping to user
                    # await discord_bot.send_tos_reminder(ticket_id, user_id, ping_message)

            except Exception as e:
                logger.error(f"Error monitoring ticket {ticket_id}: {e}", exc_info=True)

        return len(awaiting_tickets)

    @staticmethod
    async def log_action(ticket_id: str, user_id: str, action: str, details: dict):
        """Log ticket action"""
        audit_logs = get_audit_logs_collection()

        # Handle both MongoDB ObjectId and Discord ID formats
        try:
            # Try to convert to ObjectId if it's a valid MongoDB ID
            user_id_field = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        except:
            # If conversion fails, use as string (Discord ID)
            user_id_field = user_id

        await audit_logs.insert_one({
            "user_id": user_id_field,
            "actor_type": "user",
            "action": action,
            "resource_type": "ticket",
            "resource_id": ObjectId(ticket_id),
            "details": details,
            "created_at": datetime.utcnow()
        })

    # =====================================================================
    # Thread-Based Ticket System Methods (V4)
    # =====================================================================

    @staticmethod
    async def create_exchanger_thread(ticket_id: str, payment_method: str) -> dict:
        """
        Create exchanger thread after TOS acceptance
        Creates hold FIRST, then returns thread info

        Args:
            ticket_id: Ticket ID
            payment_method: Payment method for role-specific visibility

        Returns:
            dict with exchanger_thread_id, hold_ids, hold_status, available_exchangers, estimated_profit
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        if ticket["status"] != "awaiting_tos":
            raise ValueError(f"Ticket must be awaiting TOS (current status: {ticket['status']})")

        if not ticket.get("tos_accepted_at"):
            raise ValueError("TOS must be accepted before creating exchanger thread")

        # Calculate amount to hold (full ticket amount)
        amount_usd = Decimal(str(ticket.get("amount_usd", 0)))

        # Create multi-currency hold (locks funds from ALL exchangers)
        try:
            hold_result = await HoldService.create_hold(
                amount_usd=amount_usd,
                ticket_id=str(ticket["_id"]),
                reason="ticket_hold",
                ticket_number=ticket.get("ticket_number")
            )

            # Update ticket with hold info
            await tickets.update_one(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "hold_created_at": datetime.utcnow(),
                        "hold_status": "created",
                        "hold_id": hold_result.get("hold_id"),
                        "status": "open",  # Change from awaiting_tos to open
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Calculate estimated profit
            profit_info = await TicketService.calculate_estimated_profit(ticket_id)

            return {
                "exchanger_thread_id": None,  # Bot will create and update
                "hold_ids": hold_result.get("hold_ids", []),
                "hold_status": "created",
                "available_exchangers": hold_result.get("available_exchangers", 0),
                "estimated_profit": profit_info["estimated_profit"]
            }

        except Exception as e:
            logger.error(f"Failed to create hold for ticket {ticket_id}: {e}", exc_info=True)
            raise ValueError(f"Insufficient exchanger funds available: {str(e)}")

    @staticmethod
    async def get_client_risk_info(ticket_id: str) -> dict:
        """
        Get anonymous client risk information

        Returns client stats without revealing identity:
        - Account age in days
        - Past exchange count
        - Completion rate (0.0 - 1.0)
        - Risk level (low, medium, high, unknown)
        """
        from app.core.database import get_users_collection

        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        # Get user info
        user_id = ticket.get("user_id")
        discord_user_id = ticket.get("discord_user_id")

        if not user_id and not discord_user_id:
            return {
                "account_age_days": None,
                "exchange_count": 0,
                "completion_rate": None,
                "risk_level": "unknown"
            }

        # Get user document
        users = get_users_collection()
        user = await users.find_one({"_id": user_id}) if user_id else None

        if not user:
            return {
                "account_age_days": None,
                "exchange_count": 0,
                "completion_rate": None,
                "risk_level": "unknown"
            }

        # Calculate account age (from created_at or Discord join date)
        account_age_days = None
        if user.get("created_at"):
            account_age_days = (datetime.utcnow() - user["created_at"]).days

        # Get exchange history
        completed_tickets = await tickets.count_documents({
            "user_id": user_id,
            "type": "exchange",
            "status": "completed"
        })

        total_tickets = await tickets.count_documents({
            "user_id": user_id,
            "type": "exchange",
            "status": {"$in": ["completed", "closed", "cancelled"]}
        })

        # Calculate completion rate
        completion_rate = None
        if total_tickets > 0:
            completion_rate = float(completed_tickets) / float(total_tickets)

        # Calculate risk level using weighted scoring
        risk_level = TicketService._calculate_risk_level(
            account_age_days=account_age_days,
            exchange_count=completed_tickets,
            completion_rate=completion_rate
        )

        return {
            "account_age_days": account_age_days,
            "exchange_count": completed_tickets,
            "completion_rate": completion_rate,
            "risk_level": risk_level
        }

    @staticmethod
    def _calculate_risk_level(account_age_days: Optional[int], exchange_count: int, completion_rate: Optional[float]) -> str:
        """
        Calculate risk level using weighted scoring

        Weights:
        - Account age: 40%
        - Exchange count: 30%
        - Completion rate: 30%
        """
        score = 0

        # Account age scoring (40% weight)
        if account_age_days is not None:
            if account_age_days >= 180:
                score += 40
            elif account_age_days >= 90:
                score += 25
            elif account_age_days >= 30:
                score += 10

        # Exchange history scoring (30% weight)
        if exchange_count >= 20:
            score += 30
        elif exchange_count >= 10:
            score += 20
        elif exchange_count >= 5:
            score += 10

        # Completion rate scoring (30% weight)
        if completion_rate is not None:
            if completion_rate >= 0.95:
                score += 30
            elif completion_rate >= 0.85:
                score += 20
            elif completion_rate >= 0.70:
                score += 10

        # Determine risk level
        if score >= 75:
            return "low"
        elif score >= 50:
            return "medium"
        else:
            return "high"

    @staticmethod
    async def calculate_estimated_profit(ticket_id: str) -> dict:
        """
        Calculate estimated profit for exchanger

        Formula:
        - Platform fee (< $40: flat $4, >= $40: 10%, crypto-to-crypto: 5%)
        - Server fee (max($0.50, 2% of amount))
        - Profit = Platform fee - Server fee
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        amount_usd = float(ticket.get("amount_usd", 0))
        send_method = ticket.get("send_method", "").lower()
        receive_method = ticket.get("receive_method", "").lower()

        # Calculate platform fee
        is_crypto_to_crypto = send_method == "crypto" and receive_method == "crypto"

        if is_crypto_to_crypto:
            # 5% for crypto-to-crypto
            platform_fee = amount_usd * 0.05
        elif amount_usd < 40:
            # Flat $4 for amounts under $40
            platform_fee = 4.0
        else:
            # 10% for amounts $40 and above
            platform_fee = amount_usd * 0.10

        # Calculate server fee (max of $0.50 or 2%)
        server_fee = max(0.50, amount_usd * 0.02)

        # Calculate profit
        estimated_profit = platform_fee - server_fee
        profit_percentage = (estimated_profit / amount_usd) * 100 if amount_usd > 0 else 0

        return {
            "amount_usd": amount_usd,
            "platform_fee": round(platform_fee, 2),
            "server_fee": round(server_fee, 2),
            "estimated_profit": round(estimated_profit, 2),
            "profit_percentage": round(profit_percentage, 2)
        }

    @staticmethod
    async def mark_client_sent_payment(ticket_id: str, client_discord_id: str) -> dict:
        """
        Client marks payment as sent

        Returns next step: "confirm_receipt" (FIAT) or "select_payout" (CRYPTO)
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        if ticket["status"] != "claimed":
            raise ValueError(f"Ticket must be claimed (current status: {ticket['status']})")

        # Verify this is the client
        ticket_discord_id = ticket.get("discord_user_id")
        if str(ticket_discord_id) != str(client_discord_id):
            raise ValueError("Only the ticket client can mark payment as sent")

        # Update ticket
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "client_sent_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Determine next step based on receive method
        receive_method = ticket.get("receive_method", "").lower()
        is_fiat = receive_method not in ["crypto", "bitcoin", "ethereum", "litecoin"]

        return {
            "client_sent_at": datetime.utcnow(),
            "next_step": "confirm_receipt" if is_fiat else "select_payout",
            "receive_method": receive_method
        }

    @staticmethod
    async def confirm_receipt(ticket_id: str, exchanger_discord_id: str) -> dict:
        """
        Exchanger confirms receipt of client payment (FIAT only)
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        # Verify this is the assigned exchanger
        assigned_to = ticket.get("assigned_to")
        if not assigned_to:
            raise ValueError("Ticket is not assigned to an exchanger")

        # Get exchanger's Discord ID
        from app.core.database import get_users_collection
        users = get_users_collection()
        exchanger = await users.find_one({"_id": assigned_to})

        if not exchanger or str(exchanger.get("discord_id")) != str(exchanger_discord_id):
            raise ValueError("Only the assigned exchanger can confirm receipt")

        # Update ticket
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "exchanger_confirmed_receipt_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "exchanger_confirmed_receipt_at": datetime.utcnow()
        }

    @staticmethod
    async def select_payout_method(ticket_id: str, exchanger_discord_id: str, method: str) -> dict:
        """
        Exchanger selects payout method (internal or external)

        Returns:
        - internal: List of available cryptos from held wallets
        - external: Empty dict (will show TXID form)
        """
        if method not in ["internal", "external"]:
            raise ValueError("Method must be 'internal' or 'external'")

        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        # Verify this is the assigned exchanger
        assigned_to = ticket.get("assigned_to")
        if not assigned_to:
            raise ValueError("Ticket is not assigned to an exchanger")

        from app.core.database import get_users_collection
        users = get_users_collection()
        exchanger = await users.find_one({"_id": assigned_to})

        if not exchanger or str(exchanger.get("discord_id")) != str(exchanger_discord_id):
            raise ValueError("Only the assigned exchanger can select payout method")

        # Update ticket with selected method
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "payout_method": method,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # If internal, return available cryptos from held deposits
        if method == "internal":
            from app.services.exchanger_deposit_service import ExchangerDepositService
            deposits = await ExchangerDepositService.get_deposits_by_discord_id(exchanger_discord_id)

            # Filter to only show cryptos with held balance > 0
            available_cryptos = []
            for deposit in deposits:
                held = float(deposit.get("held", 0))
                if held > 0:
                    available_cryptos.append({
                        "currency": deposit.get("currency"),
                        "held_amount": held
                    })

            return {"available_cryptos": available_cryptos}

        return {}

    @staticmethod
    async def execute_internal_payout(
        ticket_id: str,
        exchanger_discord_id: str,
        currency: str,
        client_wallet: str
    ) -> dict:
        """
        Execute internal wallet payout
        Sends crypto from exchanger's held wallet to client

        Returns TXID and verification status
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        # Verify payout method is internal
        if ticket.get("payout_method") != "internal":
            raise ValueError("Payout method must be 'internal'")

        # TODO: Implement actual payout logic via wallet service
        # For now, return placeholder
        logger.info(f"Internal payout: {currency} to {client_wallet} for ticket {ticket_id}")

        # Update ticket
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "payout_sent_at": datetime.utcnow(),
                    "payout_txid": "PLACEHOLDER_TXID",  # TODO: Real TXID from wallet service
                    "payout_verified": False,  # Will be verified by blockchain
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "txid": "PLACEHOLDER_TXID",
            "amount": ticket.get("receiving_amount", 0),
            "verification_status": "pending",
            "payout_sent_at": datetime.utcnow()
        }

    @staticmethod
    async def record_external_payout(
        ticket_id: str,
        exchanger_discord_id: str,
        txid: str,
        client_wallet: str,
        currency: str
    ) -> dict:
        """
        Record external wallet payout
        Verifies TXID on blockchain
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        # Verify payout method is external
        if ticket.get("payout_method") != "external":
            raise ValueError("Payout method must be 'external'")

        # TODO: Implement blockchain verification
        verification_status = "unverified"  # or "verified" or "pending"

        # Update ticket
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "payout_sent_at": datetime.utcnow(),
                    "payout_txid": txid,
                    "payout_verified": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return {
            "verification_status": verification_status,
            "payout_sent_at": datetime.utcnow()
        }

    @staticmethod
    async def confirm_complete(ticket_id: str, client_discord_id: str) -> dict:
        """
        Client confirms receipt of payout

        Triggers completion workflow:
        1. Releases holds with deduction
        2. Updates stats
        3. Returns completion info for bot to handle transcripts/DMs
        """
        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        # Verify this is the client
        ticket_discord_id = ticket.get("discord_user_id")
        if str(ticket_discord_id) != str(client_discord_id):
            raise ValueError("Only the ticket client can confirm completion")

        # Verify payout was sent
        if not ticket.get("payout_sent_at"):
            raise ValueError("Payout must be sent before completing ticket")

        # Complete ticket (releases holds with deduction)
        completed_ticket = await TicketService.complete_ticket(
            ticket_id=ticket_id,
            user_id=str(ticket.get("assigned_to"))  # Exchanger user ID
        )

        # Calculate profit for transcript
        profit_info = await TicketService.calculate_estimated_profit(ticket_id)

        return {
            "completed_at": completed_ticket.get("closed_at"),
            "profit": profit_info["estimated_profit"],
            "server_fee": profit_info["server_fee"],
            "transcript_url": f"https://afrooexchange.com/transcripts/{ticket_id}"
        }

    @staticmethod
    async def claim_ticket_thread(ticket_id: str, exchanger_discord_id: str) -> dict:
        """
        Claim ticket in thread system

        NEW BEHAVIOR:
        - Hold already created on TOS accept
        - Verifies exchanger has sufficient unheld balance
        - Assigns ticket to exchanger
        - Returns thread info for DM
        """
        from app.core.database import get_users_collection

        tickets = get_tickets_collection()
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})

        if not ticket:
            raise ValueError("Ticket not found")

        if ticket["status"] != "open":
            raise ValueError(f"Ticket is not available for claiming (status: {ticket['status']})")

        if ticket.get("assigned_to"):
            raise ValueError("Ticket is already claimed")

        # Verify hold was created
        if ticket.get("hold_status") != "created":
            raise ValueError("Hold must be created before claiming ticket")

        # Get exchanger user
        users = get_users_collection()
        exchanger = await users.find_one({"discord_id": exchanger_discord_id})

        if not exchanger:
            raise ValueError("Exchanger user not found")

        # Verify exchanger has sufficient unheld balance
        from app.services.exchanger_deposit_service import ExchangerDepositService
        amount_usd = Decimal(str(ticket.get("amount_usd", 0)))

        # This will raise ValueError if insufficient balance
        await ExchangerDepositService.verify_sufficient_balance(exchanger_discord_id, amount_usd)

        # Assign ticket to exchanger
        await tickets.update_one(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "assigned_to": exchanger["_id"],
                    "status": "claimed",
                    "claimed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # Update hold with exchanger assignment
        if ticket.get("hold_id"):
            await HoldService.assign_hold_to_exchanger(
                hold_id=str(ticket["hold_id"]),
                exchanger_id=str(exchanger["_id"])
            )

        # Check milestones
        await MilestoneService.check_milestones(str(exchanger["_id"]))

        return {
            "ticket_number": ticket.get("ticket_number"),
            "client_thread_id": ticket.get("client_thread_id"),
            "exchanger_thread_id": ticket.get("exchanger_thread_id"),
            "amount_held": float(amount_usd),
            "claimed_at": datetime.utcnow()
        }
