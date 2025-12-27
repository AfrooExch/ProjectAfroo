"""
Ticket Action Service - Handles all dashboard actions for exchange tickets
Implements the full exchange flow: client-sent, amount/fee changes, unclaim, close, payouts
"""

from typing import Optional, Dict
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_tickets_collection, get_audit_logs_collection
from app.services.hold_service import HoldService
from app.services.exchanger_deposit_service import ExchangerDepositService

logger = logging.getLogger(__name__)


class TicketActionService:
    """Service for ticket dashboard actions"""

    @staticmethod
    async def exchanger_confirmed_receipt(ticket_id: str, discord_user_id: str) -> dict:
        """
        Exchanger confirms they received customer's fiat payment (fiat-to-fiat workflow)
        """
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify it's the exchanger
        exchanger_discord_id = ticket.get("exchanger_discord_id")
        if not exchanger_discord_id:
            raise ValueError("Ticket not claimed yet")

        if exchanger_discord_id != discord_user_id:
            raise ValueError("Only the exchanger can confirm receipt")

        # Update ticket
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "exchanger_confirmed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Exchanger confirmed receipt of customer payment")
        return result

    @staticmethod
    async def payment_sent(ticket_id: str, discord_user_id: str) -> dict:
        """
        Exchanger confirms they sent payment to customer (fiat-to-fiat workflow)
        """
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify it's the exchanger
        exchanger_discord_id = ticket.get("exchanger_discord_id")
        if not exchanger_discord_id:
            raise ValueError("Ticket not claimed yet")

        if exchanger_discord_id != discord_user_id:
            raise ValueError("Only the exchanger can confirm payment sent")

        # Update ticket
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "payment_sent_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Exchanger confirmed payment sent to customer")
        return result

    @staticmethod
    async def mark_client_sent(ticket_id: str, discord_user_id: str) -> dict:
        """
        Client marks that they've sent their funds.
        This triggers the exchanger payout flow.

        Admin bypass: Head Admin or Assistant Admin can mark on behalf of client.
        """
        tickets = get_tickets_collection()

        # Get ticket
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify it's the client OR admin
        ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))

        # Check if user is admin (staff includes both head admin and assistant admin)
        from app.services.user_service import UserService
        is_admin = await UserService.is_staff(discord_user_id)

        # Allow if either client or admin
        if ticket_discord_id != discord_user_id and not is_admin:
            raise ValueError("Only the client or admins can mark funds as sent")

        # Verify ticket is claimed
        if ticket["status"] != "claimed":
            raise ValueError(f"Ticket must be claimed first (current status: {ticket['status']})")

        # Update ticket
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "client_sent",
                    "client_sent_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        if is_admin and ticket_discord_id != discord_user_id:
            logger.info(f"Ticket {ticket_id}: Admin {discord_user_id} marked funds as sent on behalf of client")
        else:
            logger.info(f"Ticket {ticket_id}: Client marked funds as sent")

        return result

    @staticmethod
    async def request_amount_change(
        ticket_id: str,
        discord_user_id: str,
        new_amount: float,
        reason: str
    ) -> dict:
        """Request to change ticket amount - requires both parties to agree"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify requester is involved in ticket
        ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))
        exchanger_discord_id = ticket.get("exchanger_discord_id")

        is_client = ticket_discord_id == discord_user_id
        is_exchanger = exchanger_discord_id and exchanger_discord_id == discord_user_id

        if not (is_client or is_exchanger):
            raise ValueError("Only client or exchanger can request amount changes")

        # Calculate new amounts
        old_amount = ticket["amount_usd"]
        old_fee = ticket["fee_amount"]
        fee_percentage = ticket.get("fee_percentage", 10.0)

        # Recalculate fee
        if new_amount < 40.0:
            new_fee = 4.0  # Min fee
        else:
            new_fee = new_amount * (fee_percentage / 100)

        new_receiving = new_amount - new_fee

        # Create pending change request
        pending_change = {
            "requester_id": discord_user_id,
            "old_amount": old_amount,
            "new_amount": new_amount,
            "new_fee": new_fee,
            "new_receiving": new_receiving,
            "reason": reason,
            "requested_at": datetime.utcnow(),
            "approved_by": []
        }

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "pending_amount_change": pending_change,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Amount change requested from ${old_amount} to ${new_amount}")

        return result

    @staticmethod
    async def approve_amount_change(ticket_id: str, discord_user_id: str) -> dict:
        """Approve pending amount change - updates holds to reflect new amount"""
        from decimal import Decimal

        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        pending = ticket.get("pending_amount_change")
        if not pending:
            raise ValueError("No pending amount change to approve")

        # Can't approve your own request
        if pending["requester_id"] == discord_user_id:
            raise ValueError("You cannot approve your own request")

        # Add approval
        pending["approved_by"].append(discord_user_id)

        # If both parties approved, apply the change
        if len(pending["approved_by"]) >= 1:  # Other party approved
            new_amount_usd = Decimal(str(pending["new_amount"]))
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            # Update holds to new amount (if ticket is claimed)
            if ticket.get("status") == "claimed" and exchanger_discord_id:
                try:
                    # Step 1: Check if exchanger has enough funds for new amount BEFORE releasing anything
                    # Calculate what's currently held for this ticket
                    old_holds = await HoldService.get_holds_by_ticket(ticket_id)
                    old_total_held_usd = sum(
                        Decimal(h.get("amount_usd", "0")) + Decimal(h.get("server_fee_usd", "0"))
                        for h in old_holds if h.get("status") == "active"
                    )

                    # Calculate server fee for new amount
                    server_fee_usd = max(new_amount_usd * Decimal("0.02"), Decimal("0.50"))
                    new_total_needed_usd = new_amount_usd  # Fee comes FROM the amount

                    logger.info(
                        f"Ticket {ticket_id}: Amount change check - "
                        f"old=${old_total_held_usd} new=${new_total_needed_usd}"
                    )

                    # Check if exchanger has enough available funds (including currently held for this ticket)
                    from app.core.database import get_db_collection
                    from app.services.price_service import price_service

                    deposits_db = await get_db_collection("exchanger_deposits")
                    deposits = await deposits_db.find({"user_id": exchanger_discord_id}).to_list(length=100)

                    # Calculate total available (balance - held - fee_reserved + this ticket's holds)
                    total_available_usd = Decimal("0")
                    for deposit in deposits:
                        currency = deposit["currency"]
                        balance = Decimal(deposit.get("balance", "0"))
                        held = Decimal(deposit.get("held", "0"))
                        fee_reserved = Decimal(deposit.get("fee_reserved", "0"))

                        # Calculate crypto held for this specific ticket
                        ticket_held_crypto = sum(
                            Decimal(h.get("crypto_held", "0")) + Decimal(h.get("server_fee_crypto", "0"))
                            for h in old_holds
                            if h.get("status") == "active" and h.get("currency") == currency
                        )

                        available_crypto = balance - held - fee_reserved + ticket_held_crypto

                        if available_crypto > 0:
                            price_usd = await price_service.get_price_usd(currency)
                            if price_usd:
                                total_available_usd += available_crypto * price_usd

                    logger.info(
                        f"Ticket {ticket_id}: Exchanger has ${total_available_usd:.2f} available "
                        f"(needs ${new_total_needed_usd:.2f})"
                    )

                    if total_available_usd < new_total_needed_usd:
                        raise ValueError(
                            f"Insufficient balance. Need ${new_total_needed_usd:.2f} USD, "
                            f"but only ${total_available_usd:.2f} USD available"
                        )

                    # Step 2: Now it's safe to release old holds
                    logger.info(f"Ticket {ticket_id}: Releasing old holds for amount change")
                    await HoldService.release_all_holds_for_ticket(
                        ticket_id=ticket_id,
                        deduct_funds=False  # Refund, don't deduct
                    )

                    # Step 3: Create new holds with updated amount
                    logger.info(f"Ticket {ticket_id}: Creating new holds for ${new_amount_usd}")
                    new_holds = await HoldService.create_multi_currency_hold(
                        ticket_id=ticket_id,
                        user_id=exchanger_discord_id,
                        amount_usd=new_amount_usd
                    )

                    # Update ticket with new hold IDs
                    hold_ids = [str(h["_id"]) for h in new_holds]
                    first_hold_id = new_holds[0]["_id"] if new_holds else None

                    result = await tickets.find_one_and_update(
                        {"_id": ObjectId(ticket_id)},
                        {
                            "$set": {
                                "amount_usd": pending["new_amount"],
                                "fee_amount": pending["new_fee"],
                                "receiving_amount": pending["new_receiving"],
                                "hold_id": first_hold_id,  # Legacy field
                                "hold_ids": hold_ids,  # Multi-currency
                                "updated_at": datetime.utcnow()
                            },
                            "$unset": {"pending_amount_change": ""}
                        },
                        return_document=True
                    )

                    logger.info(f"Ticket {ticket_id}: Amount change approved, holds updated to ${new_amount_usd}")

                except ValueError as e:
                    # If insufficient funds or any check fails, DON'T touch the holds
                    logger.error(f"Ticket {ticket_id}: Cannot approve amount change - {e}")
                    raise ValueError(f"Cannot change amount: {str(e)}")

            else:
                # Ticket not claimed yet, just update amounts
                result = await tickets.find_one_and_update(
                    {"_id": ObjectId(ticket_id)},
                    {
                        "$set": {
                            "amount_usd": pending["new_amount"],
                            "fee_amount": pending["new_fee"],
                            "receiving_amount": pending["new_receiving"],
                            "updated_at": datetime.utcnow()
                        },
                        "$unset": {"pending_amount_change": ""}
                    },
                    return_document=True
                )

                logger.info(f"Ticket {ticket_id}: Amount change approved (no holds to update)")
        else:
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "pending_amount_change": pending,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

        return result

    @staticmethod
    async def admin_force_change_amount(
        ticket_id: str,
        new_amount: float,
        admin_id: str,
        reason: str
    ) -> dict:
        """
        Admin forces amount change (bypasses approval workflow).
        Updates holds correctly if ticket is claimed.
        """
        from decimal import Decimal

        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError("Ticket not found")

        # Calculate new amounts
        old_amount = ticket["amount_usd"]
        new_amount_decimal = Decimal(str(new_amount))

        # Recalculate fee based on ticket's fee structure
        send_method = ticket.get("send_method", "")
        receive_method = ticket.get("receive_method", "")

        # Check if crypto to crypto
        is_crypto_send = any(c in send_method.upper() for c in ["BTC", "ETH", "LTC", "SOL", "USDT", "CRYPTO"])
        is_crypto_receive = any(c in receive_method.upper() for c in ["BTC", "ETH", "LTC", "SOL", "USDT", "CRYPTO"])

        if is_crypto_send and is_crypto_receive:
            fee_percentage = 5.0
            new_fee = new_amount * 0.05
        elif new_amount >= 40.0:
            fee_percentage = 10.0
            new_fee = new_amount * 0.10
        else:
            fee_percentage = (4.0 / new_amount) * 100
            new_fee = 4.0

        new_receiving = new_amount - new_fee

        # If ticket is claimed, update holds
        if ticket.get("status") == "claimed" and ticket.get("exchanger_discord_id"):
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            try:
                logger.info(f"Ticket {ticket_id}: Admin forcing amount change with hold updates")

                # Release old holds (refund)
                await HoldService.release_all_holds_for_ticket(
                    ticket_id=ticket_id,
                    deduct_funds=False
                )

                # Create new holds with new amount
                new_holds = await HoldService.create_multi_currency_hold(
                    ticket_id=ticket_id,
                    user_id=exchanger_discord_id,
                    amount_usd=new_amount_decimal
                )

                # Update ticket with new amounts and hold IDs
                hold_ids = [str(h["_id"]) for h in new_holds]
                first_hold_id = new_holds[0]["_id"] if new_holds else None

                result = await tickets.find_one_and_update(
                    {"_id": ObjectId(ticket_id)},
                    {
                        "$set": {
                            "amount_usd": float(new_amount),
                            "fee_amount": float(new_fee),
                            "fee_percentage": float(fee_percentage),
                            "receiving_amount": float(new_receiving),
                            "hold_id": first_hold_id,
                            "hold_ids": hold_ids,
                            "admin_changed_amount_at": datetime.utcnow(),
                            "admin_changed_amount_by": admin_id,
                            "admin_change_reason": reason,
                            "updated_at": datetime.utcnow()
                        }
                    },
                    return_document=True
                )

                logger.info(
                    f"Ticket {ticket_id}: Admin changed amount from ${old_amount} to ${new_amount} "
                    f"(holds updated)"
                )

            except Exception as e:
                logger.error(f"Ticket {ticket_id}: Error updating holds during admin amount change: {e}")
                raise ValueError(f"Failed to update holds: {str(e)}")

        else:
            # Not claimed yet - just update amounts
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "amount_usd": float(new_amount),
                        "fee_amount": float(new_fee),
                        "fee_percentage": float(fee_percentage),
                        "receiving_amount": float(new_receiving),
                        "admin_changed_amount_at": datetime.utcnow(),
                        "admin_changed_amount_by": admin_id,
                        "admin_change_reason": reason,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

            logger.info(f"Ticket {ticket_id}: Admin changed amount from ${old_amount} to ${new_amount} (no holds)")

        # Log the action
        await TicketActionService.log_action(
            ticket_id, admin_id, "amount.force_changed_by_admin",
            {"old_amount": float(old_amount), "new_amount": float(new_amount), "reason": reason}
        )

        return result

    @staticmethod
    async def request_fee_change(
        ticket_id: str,
        discord_user_id: str,
        new_fee_percentage: float,
        reason: str
    ) -> dict:
        """Request to change ticket fee percentage"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Calculate new amounts
        amount_usd = ticket["amount_usd"]
        old_fee = ticket["fee_amount"]

        if amount_usd < 40.0:
            new_fee = 4.0  # Min fee always applies
        else:
            new_fee = amount_usd * (new_fee_percentage / 100)

        new_receiving = amount_usd - new_fee

        pending_change = {
            "requester_id": discord_user_id,
            "old_fee_percentage": ticket.get("fee_percentage", 10.0),
            "new_fee_percentage": new_fee_percentage,
            "new_fee": new_fee,
            "new_receiving": new_receiving,
            "reason": reason,
            "requested_at": datetime.utcnow(),
            "approved_by": []
        }

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "pending_fee_change": pending_change,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Fee change requested to {new_fee_percentage}%")

        return result

    @staticmethod
    async def approve_fee_change(ticket_id: str, discord_user_id: str) -> dict:
        """Approve pending fee change - updates holds to reflect new fee"""
        from decimal import Decimal

        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        pending = ticket.get("pending_fee_change")
        if not pending:
            raise ValueError("No pending fee change to approve")

        if pending["requester_id"] == discord_user_id:
            raise ValueError("You cannot approve your own request")

        pending["approved_by"].append(discord_user_id)

        if len(pending["approved_by"]) >= 1:
            # Get the ticket amount (doesn't change, only fee changes)
            amount_usd = Decimal(str(ticket["amount_usd"]))
            exchanger_discord_id = ticket.get("exchanger_discord_id")

            # Update holds with new fee (if ticket is claimed)
            if ticket.get("status") == "claimed" and exchanger_discord_id:
                try:
                    # Step 1: Check if exchanger has enough funds BEFORE releasing anything
                    # Get current holds for this ticket
                    old_holds = await HoldService.get_holds_by_ticket(ticket_id)

                    # Calculate server fee (stays the same, based on ticket amount)
                    server_fee_usd = max(amount_usd * Decimal("0.02"), Decimal("0.50"))
                    total_needed_usd = amount_usd  # Fee comes FROM the amount

                    logger.info(f"Ticket {ticket_id}: Fee change check - needs ${total_needed_usd}")

                    # Check if exchanger has enough available funds (including currently held for this ticket)
                    from app.core.database import get_db_collection
                    from app.services.price_service import price_service

                    deposits_db = await get_db_collection("exchanger_deposits")
                    deposits = await deposits_db.find({"user_id": exchanger_discord_id}).to_list(length=100)

                    # Calculate total available (balance - held - fee_reserved + this ticket's holds)
                    total_available_usd = Decimal("0")
                    for deposit in deposits:
                        currency = deposit["currency"]
                        balance = Decimal(deposit.get("balance", "0"))
                        held = Decimal(deposit.get("held", "0"))
                        fee_reserved = Decimal(deposit.get("fee_reserved", "0"))

                        # Calculate crypto held for this specific ticket
                        ticket_held_crypto = sum(
                            Decimal(h.get("crypto_held", "0")) + Decimal(h.get("server_fee_crypto", "0"))
                            for h in old_holds
                            if h.get("status") == "active" and h.get("currency") == currency
                        )

                        available_crypto = balance - held - fee_reserved + ticket_held_crypto

                        if available_crypto > 0:
                            price_usd = await price_service.get_price_usd(currency)
                            if price_usd:
                                total_available_usd += available_crypto * price_usd

                    logger.info(
                        f"Ticket {ticket_id}: Exchanger has ${total_available_usd:.2f} available "
                        f"(needs ${total_needed_usd:.2f})"
                    )

                    if total_available_usd < total_needed_usd:
                        raise ValueError(
                            f"Insufficient balance. Need ${total_needed_usd:.2f} USD, "
                            f"but only ${total_available_usd:.2f} USD available"
                        )

                    # Step 2: Now it's safe to release old holds
                    logger.info(f"Ticket {ticket_id}: Releasing old holds for fee change")
                    await HoldService.release_all_holds_for_ticket(
                        ticket_id=ticket_id,
                        deduct_funds=False  # Refund, don't deduct
                    )

                    # Step 3: Create new holds with same ticket amount
                    # Note: The hold system calculates server fee internally (2% min $0.50)
                    # The user-facing fee_percentage doesn't affect the server fee
                    logger.info(f"Ticket {ticket_id}: Creating new holds for ${amount_usd}")
                    new_holds = await HoldService.create_multi_currency_hold(
                        ticket_id=ticket_id,
                        user_id=exchanger_discord_id,
                        amount_usd=amount_usd
                    )

                    # Update ticket with new hold IDs
                    hold_ids = [str(h["_id"]) for h in new_holds]
                    first_hold_id = new_holds[0]["_id"] if new_holds else None

                    result = await tickets.find_one_and_update(
                        {"_id": ObjectId(ticket_id)},
                        {
                            "$set": {
                                "fee_percentage": pending["new_fee_percentage"],
                                "fee_amount": pending["new_fee"],
                                "receiving_amount": pending["new_receiving"],
                                "hold_id": first_hold_id,  # Legacy field
                                "hold_ids": hold_ids,  # Multi-currency
                                "updated_at": datetime.utcnow()
                            },
                            "$unset": {"pending_fee_change": ""}
                        },
                        return_document=True
                    )

                    logger.info(f"Ticket {ticket_id}: Fee change approved, holds updated")

                except ValueError as e:
                    # If insufficient funds or any check fails, DON'T touch the holds
                    logger.error(f"Ticket {ticket_id}: Cannot approve fee change - {e}")
                    raise ValueError(f"Cannot change fee: {str(e)}")

            else:
                # Ticket not claimed yet, just update amounts
                result = await tickets.find_one_and_update(
                    {"_id": ObjectId(ticket_id)},
                    {
                        "$set": {
                            "fee_percentage": pending["new_fee_percentage"],
                            "fee_amount": pending["new_fee"],
                            "receiving_amount": pending["new_receiving"],
                            "updated_at": datetime.utcnow()
                        },
                        "$unset": {"pending_fee_change": ""}
                    },
                    return_document=True
                )

                logger.info(f"Ticket {ticket_id}: Fee change approved (no holds to update)")
        else:
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "pending_fee_change": pending,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

        return result

    @staticmethod
    async def admin_force_change_fee(
        ticket_id: str,
        new_fee_percentage: float,
        admin_id: str,
        reason: str
    ) -> dict:
        """
        Admin forces fee change (bypasses approval workflow).
        Updates holds correctly if ticket is claimed.
        """
        from decimal import Decimal

        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError("Ticket not found")

        # Get current values
        amount_usd = ticket["amount_usd"]
        old_fee_percentage = ticket.get("fee_percentage", 10.0)
        old_fee = ticket["fee_amount"]

        # Calculate new amounts
        if amount_usd < 40.0:
            new_fee = 4.0  # Min fee always applies
        else:
            new_fee = amount_usd * (new_fee_percentage / 100)

        new_receiving = amount_usd - new_fee

        # If ticket is claimed, update holds
        if ticket.get("status") == "claimed" and ticket.get("exchanger_discord_id"):
            exchanger_discord_id = ticket.get("exchanger_discord_id")
            amount_decimal = Decimal(str(amount_usd))

            try:
                logger.info(f"Ticket {ticket_id}: Admin forcing fee change with hold updates")

                # Release old holds (refund)
                await HoldService.release_all_holds_for_ticket(
                    ticket_id=ticket_id,
                    deduct_funds=False
                )

                # Create new holds with same amount (hold system handles server fee internally)
                new_holds = await HoldService.create_multi_currency_hold(
                    ticket_id=ticket_id,
                    user_id=exchanger_discord_id,
                    amount_usd=amount_decimal
                )

                # Update ticket with new fee and hold IDs
                hold_ids = [str(h["_id"]) for h in new_holds]
                first_hold_id = new_holds[0]["_id"] if new_holds else None

                result = await tickets.find_one_and_update(
                    {"_id": ObjectId(ticket_id)},
                    {
                        "$set": {
                            "fee_percentage": float(new_fee_percentage),
                            "fee_amount": float(new_fee),
                            "receiving_amount": float(new_receiving),
                            "hold_id": first_hold_id,
                            "hold_ids": hold_ids,
                            "admin_changed_fee_at": datetime.utcnow(),
                            "admin_changed_fee_by": admin_id,
                            "admin_change_fee_reason": reason,
                            "updated_at": datetime.utcnow()
                        }
                    },
                    return_document=True
                )

                logger.info(
                    f"Ticket {ticket_id}: Admin changed fee from {old_fee_percentage}% to {new_fee_percentage}% "
                    f"(holds updated)"
                )

            except Exception as e:
                logger.error(f"Ticket {ticket_id}: Error updating holds during admin fee change: {e}")
                raise ValueError(f"Failed to update holds: {str(e)}")

        else:
            # Not claimed yet - just update fee
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "fee_percentage": float(new_fee_percentage),
                        "fee_amount": float(new_fee),
                        "receiving_amount": float(new_receiving),
                        "admin_changed_fee_at": datetime.utcnow(),
                        "admin_changed_fee_by": admin_id,
                        "admin_change_fee_reason": reason,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

            logger.info(f"Ticket {ticket_id}: Admin changed fee from {old_fee_percentage}% to {new_fee_percentage}% (no holds)")

        # Log the action
        await TicketActionService.log_action(
            ticket_id, admin_id, "fee.force_changed_by_admin",
            {"old_fee_percentage": float(old_fee_percentage), "new_fee_percentage": float(new_fee_percentage), "reason": reason}
        )

        return result

    @staticmethod
    async def request_unclaim(ticket_id: str, discord_user_id: str) -> dict:
        """Request to unclaim ticket and refund hold"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify requester is involved in ticket (client or exchanger)
        ticket_discord_id = ticket.get("discord_user_id", str(ticket["user_id"]))
        exchanger_discord_id = ticket.get("exchanger_discord_id")

        is_client = ticket_discord_id == discord_user_id
        is_exchanger = exchanger_discord_id and exchanger_discord_id == discord_user_id

        if not (is_client or is_exchanger):
            raise ValueError("Only client or exchanger can request unclaim")

        if ticket["status"] != "claimed" and ticket["status"] != "client_sent":
            raise ValueError(f"Can only unclaim tickets that are claimed (current: {ticket['status']})")

        pending_unclaim = {
            "requester_id": discord_user_id,
            "requested_at": datetime.utcnow(),
            "approved_by": []
        }

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "pending_unclaim": pending_unclaim,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Unclaim requested")

        return result

    @staticmethod
    async def approve_unclaim(ticket_id: str, discord_user_id: str) -> dict:
        """Approve unclaim - refunds hold and reopens ticket"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        pending = ticket.get("pending_unclaim")
        if not pending:
            raise ValueError("No pending unclaim request")

        if pending["requester_id"] == discord_user_id:
            raise ValueError("You cannot approve your own request")

        pending["approved_by"].append(discord_user_id)

        if len(pending["approved_by"]) >= 1:
            # Refund ALL holds (multi-currency support)
            # Check for both old single hold_id and new hold_ids array
            hold_ids_to_refund = []

            if ticket.get("hold_id"):
                hold_ids_to_refund.append(str(ticket["hold_id"]))

            if ticket.get("hold_ids"):
                hold_ids_to_refund.extend(ticket["hold_ids"])

            # Refund all holds
            for hold_id in hold_ids_to_refund:
                try:
                    await HoldService.refund_hold(hold_id)
                    logger.info(f"Ticket {ticket_id}: Refunded hold {hold_id}")
                except Exception as e:
                    logger.error(f"Ticket {ticket_id}: Failed to refund hold {hold_id}: {e}")

            # Reopen ticket and clear all claim-related fields
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "status": "open",
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {
                        "assigned_to": "",
                        "exchanger_discord_id": "",
                        "hold_id": "",
                        "hold_ids": "",
                        "claimed_at": "",
                        "client_sent_at": "",
                        "pending_unclaim": ""
                    }
                },
                return_document=True
            )

            logger.info(f"Ticket {ticket_id}: Unclaimed successfully, {len(hold_ids_to_refund)} hold(s) refunded")
        else:
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "pending_unclaim": pending,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

        return result

    @staticmethod
    async def request_close(ticket_id: str, discord_user_id: str, reason: str = "") -> dict:
        """Request to close ticket with transcripts"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Verify requester is involved in ticket (client or exchanger)
        ticket_discord_id = ticket.get("discord_user_id", str(ticket.get("user_id", "")))
        exchanger_discord_id = ticket.get("exchanger_discord_id")

        is_client = ticket_discord_id == discord_user_id
        is_exchanger = exchanger_discord_id and exchanger_discord_id == discord_user_id

        if not (is_client or is_exchanger):
            raise ValueError("Only client or exchanger can request close")

        pending_close = {
            "requester_id": discord_user_id,
            "reason": reason,
            "requested_at": datetime.utcnow(),
            "approved_by": []
        }

        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "pending_close": pending_close,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Close requested")

        return result

    @staticmethod
    async def approve_close(ticket_id: str, discord_user_id: str) -> dict:
        """Approve close request - generates transcripts and closes ticket"""
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        pending = ticket.get("pending_close")
        if not pending:
            raise ValueError("No pending close request")

        if pending["requester_id"] == discord_user_id:
            raise ValueError("You cannot approve your own request")

        pending["approved_by"].append(discord_user_id)

        if len(pending["approved_by"]) >= 1:
            # Generate transcript
            from app.services.transcript_service import TranscriptService
            from app.services.server_fee_service import ServerFeeService

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
                    "closed_reason": pending.get("reason", ""),
                    "transcript_html": transcript["html"],
                    "transcript_text": transcript["text"],
                    "transcript_generated_at": transcript["generated_at"],
                    "client_vouch_template": client_vouch,
                    "exchanger_vouch_template": exchanger_vouch,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {"pending_close": ""}
            }

            # Add server fee info if collected
            if fee_result:
                update_data["$set"]["server_fee_collected"] = fee_result.get("amount_usd", 0)
                update_data["$set"]["server_fee_status"] = fee_result.get("status", "collected")

            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                update_data,
                return_document=True
            )

            logger.info(f"Ticket {ticket_id}: Completed successfully with transcript")

            # Trigger completion notifications for bot to process
            from app.services.notification_service import NotificationService

            try:
                await NotificationService.trigger_completion_notifications(ticket_id)
                logger.info(f"Ticket {ticket_id}: Completion notifications triggered")
            except Exception as e:
                logger.error(f"Ticket {ticket_id}: Failed to trigger notifications: {e}")
                # Don't fail the completion if notifications fail
        else:
            result = await tickets.find_one_and_update(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "pending_close": pending,
                        "updated_at": datetime.utcnow()
                    }
                },
                return_document=True
            )

        return result

    @staticmethod
    async def process_internal_payout(
        ticket_id: str,
        discord_user_id: str,
        client_address: str,
        selected_currency: str = None
    ) -> dict:
        """
        Process internal payout - send crypto from EXCHANGER's deposit wallet to client.
        Uses exchanger's private key to send the held funds directly.

        Args:
            ticket_id: Ticket ID
            discord_user_id: Discord user initiating payout
            client_address: Client's wallet address to send to
            selected_currency: Optional currency to use (if None, uses ticket's receive_crypto)
        """
        from decimal import Decimal as D
        from app.services.crypto_handler_service import CryptoHandlerService
        from app.core.database import get_db_collection

        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Allow both client and exchanger to initiate payout
        # Client provides their address, Exchanger can also manually trigger
        ticket_discord_id = ticket.get("discord_user_id", str(ticket.get("user_id", "")))
        exchanger_discord_id = ticket.get("exchanger_discord_id")

        is_client = ticket_discord_id == discord_user_id
        is_exchanger = exchanger_discord_id and exchanger_discord_id == discord_user_id

        if not (is_client or is_exchanger):
            raise ValueError("Only the client or exchanger can initiate payout")

        if ticket["status"] != "client_sent":
            raise ValueError(f"Can only process payout after client sends funds (current: {ticket['status']})")

        # Get crypto and amount
        # Use selected_currency if provided, otherwise use ticket's receive_crypto
        receive_crypto = selected_currency or ticket.get("receive_crypto")
        receiving_amount_usd = D(str(ticket.get("receiving_amount", 0)))

        if not receive_crypto:
            raise ValueError("This ticket is not receiving cryptocurrency")

        if receiving_amount_usd <= 0:
            raise ValueError("Invalid receiving amount")

        logger.info(f"Ticket {ticket_id}: Initiating internal payout of ${receiving_amount_usd} worth of {receive_crypto} to {client_address}")

        # CRITICAL: Sync exchanger's deposit balance with blockchain BEFORE sending
        # This ensures we have the accurate on-chain balance, not just cached database value
        # Wallet withdrawal does this - internal payout must too!
        try:
            from app.services.exchanger_service import ExchangerService
            await ExchangerService.sync_deposit_balance(exchanger_discord_id, receive_crypto)
            logger.info(f"Ticket {ticket_id}: Synced {receive_crypto} balance before internal payout")
        except Exception as sync_err:
            logger.warning(f"Ticket {ticket_id}: Failed to sync {receive_crypto} balance: {sync_err}")
            # Continue anyway - we'll try with cached balance

        # Get exchanger's deposit wallet for this crypto
        deposits_db = await get_db_collection("exchanger_deposits")
        deposit = await deposits_db.find_one({
            "user_id": exchanger_discord_id,
            "currency": receive_crypto
        })

        if not deposit:
            raise ValueError(f"Exchanger does not have a {receive_crypto} deposit wallet")

        # Check for address field (could be "address" or "wallet_address")
        exchanger_address = deposit.get("address") or deposit.get("wallet_address")
        if not exchanger_address:
            raise ValueError(f"Exchanger's {receive_crypto} wallet has no address")

        if not deposit.get("encrypted_private_key"):
            raise ValueError(f"Exchanger's {receive_crypto} wallet has no private key - cannot send funds")

        # IMPORTANT: Calculate amount based on receiving_amount_usd (what client gets after fees)
        # NOT based on crypto_held (which is the full ticket amount held)
        # Example: $8 ticket, 50% fee = $4 client receives, but crypto_held might be for $8
        from app.services.price_service import price_service
        price_usd = await price_service.get_price_usd(receive_crypto)
        if not price_usd:
            raise ValueError(f"Cannot get price for {receive_crypto}")

        amount_crypto = receiving_amount_usd / D(str(price_usd))
        logger.info(f"Ticket {ticket_id}: Client should receive {amount_crypto} {receive_crypto} (${receiving_amount_usd} at ${price_usd}/{receive_crypto})")

        if amount_crypto <= 0:
            raise ValueError(f"Invalid amount to send: {amount_crypto}")

        # For UTXO coins (BTC, LTC, DOGE), we need to subtract network fee from send amount
        # Otherwise Tatum will reject the transaction (not enough coins for amount + fee)
        # Use same network fee estimates as exchanger withdrawal
        network_fees = {
            "BTC": D("0.000005"),
            "ETH": D("0.001"),
            "USDC-ETH": D("0.001"),
            "USDT-ETH": D("0.001"),
            "SOL": D("0.000005"),
            "USDC-SOL": D("0.000005"),
            "USDT-SOL": D("0.000005"),
            "LTC": D("0.001"),  # Increased from 0.0000025 to meet LTC network relay fee requirements
            "XRP": D("0.00001"),
            "BNB": D("0.0005"),
            "TRX": D("1"),
            "MATIC": D("0.01"),
            "AVAX": D("0.001"),
            "DOGE": D("2")
        }
        network_fee = network_fees.get(receive_crypto, D("0.0001"))

        # Check if amount is large enough to cover fee
        if amount_crypto <= network_fee:
            raise ValueError(f"Amount too small. Network fee for {receive_crypto} is {network_fee}")

        # Calculate send amount (what client receives) = amount - network_fee
        # This matches how wallet withdrawal works
        send_amount = amount_crypto - network_fee

        # Check exchanger's TOTAL balance (including held funds)
        # For internal payout, we ALLOW using held funds since only the CLIENT can enter their address
        # This prevents exchanger from withdrawing held funds to scam, but allows paying client securely
        exchanger_balance = D(deposit.get("balance", "0"))
        exchanger_held = D(deposit.get("held", "0"))
        exchanger_fee_reserved = D(deposit.get("fee_reserved", "0"))

        # Check if we have enough balance for the full amount (before subtracting fee)
        if exchanger_balance < amount_crypto:
            raise ValueError(
                f"Insufficient balance in exchanger's {receive_crypto} wallet. "
                f"Need {amount_crypto} {receive_crypto} (send: {send_amount}, fee: {network_fee}), "
                f"but only {exchanger_balance} {receive_crypto} total balance (held: {exchanger_held}, fee_reserved: {exchanger_fee_reserved})."
            )

        logger.info(f"Ticket {ticket_id}: Sending {send_amount} {receive_crypto} (fee: {network_fee}) from exchanger's wallet {exchanger_address[:10]}... (using held funds)")

        # Use TatumService (same as wallet withdrawal) for consistent behavior
        # Decrypt private key
        from app.core.encryption import get_encryption_service
        encryption = get_encryption_service()
        private_key = encryption.decrypt_private_key(deposit["encrypted_private_key"])

        # Send transaction using TatumService (positional args: blockchain, from_address, private_key, to_address, amount)
        from app.services.tatum_service import TatumService
        tatum_service = TatumService()
        success, message, tx_hash = await tatum_service.send_transaction(
            receive_crypto,  # blockchain
            exchanger_address,  # from_address
            private_key,  # private_key
            client_address,  # to_address
            float(send_amount)  # amount - what client receives after network fee
        )

        if not success:
            raise ValueError(f"Failed to send crypto: {message}")

        # Update ticket with TX hash
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "payout_pending",
                    "payout_type": "internal",
                    "payout_address": client_address,
                    "payout_tx_hash": tx_hash,
                    "payout_amount_crypto": str(amount_crypto),
                    "payout_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: Internal payout sent from exchanger's wallet - TX: {tx_hash}")

        return {
            "tx_hash": tx_hash,
            "tx_url": None,
            "asset": receive_crypto,
            "amount": str(amount_crypto),
            "ticket": result
        }

    @staticmethod
    async def process_external_payout(
        ticket_id: str,
        discord_user_id: str,
        client_address: str,
        tx_hash: str
    ) -> dict:
        """
        Process external payout - exchanger sends from their own wallet,
        submits TXID for verification
        """
        tickets = get_tickets_collection()

        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        if ticket["status"] != "client_sent":
            raise ValueError(f"Can only process payout after client sends funds (current: {ticket['status']})")

        receive_crypto = ticket.get("receive_crypto")

        # Try to verify TX on blockchain
        verification_status = "unverified"
        verification_message = ""

        try:
            from app.services.crypto_handler_service import CryptoHandlerService

            # Try to verify the transaction (method may not be implemented yet)
            if hasattr(CryptoHandlerService, 'verify_transaction'):
                is_confirmed = await CryptoHandlerService.verify_transaction(
                    asset=receive_crypto,
                    tx_hash=tx_hash,
                    to_address=client_address,
                    min_confirmations=1
                )

                if is_confirmed:
                    verification_status = "verified"
                    verification_message = "Transaction verified with 1+ confirmations"
                    logger.info(f"Ticket {ticket_id}: TX {tx_hash} verified on blockchain")
                else:
                    verification_status = "pending_confirmation"
                    verification_message = "Transaction found but awaiting confirmations"
                    logger.info(f"Ticket {ticket_id}: TX {tx_hash} found but not confirmed yet")
            else:
                verification_status = "unverified"
                verification_message = "Awaiting manual verification"
                logger.info(f"Ticket {ticket_id}: TX verification not available, marked as unverified")
        except Exception as e:
            verification_status = "unverified"
            verification_message = "Awaiting manual verification"
            logger.warning(f"Ticket {ticket_id}: Could not verify TX {tx_hash}: {e}")

        # Update ticket to payout_pending (awaiting client confirmation)
        result = await tickets.find_one_and_update(
            {"_id": ObjectId(ticket_id)},
            {
                "$set": {
                    "status": "payout_pending",
                    "payout_type": "external",
                    "payout_address": client_address,
                    "payout_tx_hash": tx_hash,
                    "payout_verification_status": verification_status,
                    "payout_verification_message": verification_message,
                    "payout_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        logger.info(f"Ticket {ticket_id}: External payout submitted - TXID: {tx_hash} (status: {verification_status})")

        return result
