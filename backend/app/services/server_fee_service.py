"""
Server Fee Service - Handles server fee collection from completed exchanges
Collects min $0.50 or 2% from exchangers per completed ticket
"""

from typing import Dict
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_tickets_collection, get_db_collection
from app.services.hold_service import HoldService

logger = logging.getLogger(__name__)


class ServerFeeService:
    """Service for server fee collection"""

    # Server fee configuration
    MIN_FEE_USD = 0.50  # Minimum $0.50
    FEE_PERCENTAGE = 2.0  # 2% of exchange amount

    @staticmethod
    def calculate_server_fee(exchange_amount_usd: float) -> float:
        """
        Calculate server fee: min $0.50 or 2% of exchange amount (whichever is greater)

        Args:
            exchange_amount_usd: The exchange amount in USD

        Returns:
            Server fee amount in USD
        """
        percentage_fee = exchange_amount_usd * (ServerFeeService.FEE_PERCENTAGE / 100)

        # Return whichever is greater: min fee or percentage fee
        return max(ServerFeeService.MIN_FEE_USD, percentage_fee)

    @staticmethod
    async def collect_server_fee(ticket_id: str, exchanger_user_id: str) -> Dict:
        """
        Collect server fee from exchanger when ticket is completed

        Args:
            ticket_id: Ticket ID
            exchanger_user_id: Exchanger's MongoDB user ID (ObjectId as string)

        Returns:
            Fee collection result dict

        Raises:
            ValueError: If insufficient balance or other validation errors
        """
        deposits = await get_db_collection("exchanger_deposits")
        tickets = get_tickets_collection()
        server_fees = await get_db_collection("server_fees")

        # Get ticket to determine exchange amount and asset
        ticket = await tickets.find_one({"_id": ObjectId(ticket_id)})
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Calculate server fee
        exchange_amount_usd = ticket.get("amount_usd", 0)
        server_fee_usd = ServerFeeService.calculate_server_fee(exchange_amount_usd)

        # Get asset type from ticket
        receive_crypto = ticket.get("receive_crypto", "USD")
        asset = receive_crypto if receive_crypto != "USD" else "USDT"  # Default to USDT if fiat

        # Get exchanger's deposit wallet
        deposit = await deposits.find_one({
            "user_id": ObjectId(exchanger_user_id),
            "asset": asset
        })

        if not deposit:
            raise ValueError(f"Exchanger deposit wallet not found for asset {asset}")

        # Check available balance (balance - held)
        balance_usd = deposit.get("balance_usd", 0)
        held_usd = deposit.get("held_units", 0)
        available_usd = balance_usd - held_usd

        if available_usd < server_fee_usd:
            # Mark as pending collection - block withdrawals until paid
            fee_record = {
                "ticket_id": ObjectId(ticket_id),
                "exchanger_id": ObjectId(exchanger_user_id),
                "amount_usd": server_fee_usd,
                "asset": asset,
                "status": "pending_collection",
                "reason": "Insufficient balance at completion time",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            await server_fees.insert_one(fee_record)

            logger.warning(
                f"Server fee collection failed for ticket {ticket_id}: "
                f"Insufficient balance. Fee ${server_fee_usd:.2f} marked as pending_collection"
            )

            return {
                "status": "pending_collection",
                "fee_id": str(fee_record["_id"]),
                "amount_usd": server_fee_usd,
                "message": "Fee marked as pending - will be collected before next withdrawal"
            }

        # Deduct fee from exchanger's balance
        result = await deposits.find_one_and_update(
            {
                "user_id": ObjectId(exchanger_user_id),
                "asset": asset
            },
            {
                "$inc": {
                    "balance_usd": -server_fee_usd,
                    "balance": -(server_fee_usd / deposit.get("price_usd", 1.0))  # Deduct in asset units
                },
                "$set": {
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        # Record successful fee collection
        fee_record = {
            "ticket_id": ObjectId(ticket_id),
            "exchanger_id": ObjectId(exchanger_user_id),
            "amount_usd": server_fee_usd,
            "asset": asset,
            "status": "collected",
            "collected_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        fee_result = await server_fees.insert_one(fee_record)

        logger.info(
            f"Server fee collected for ticket {ticket_id}: "
            f"${server_fee_usd:.2f} from exchanger {exchanger_user_id}"
        )

        # TODO: Send fee to admin wallet
        # For now, just mark as collected in database
        # Admin can manually withdraw accumulated fees

        return {
            "status": "collected",
            "fee_id": str(fee_result.inserted_id),
            "amount_usd": server_fee_usd,
            "asset": asset,
            "exchanger_new_balance_usd": result.get("balance_usd", 0)
        }

    @staticmethod
    async def get_pending_fees(exchanger_user_id: str) -> Dict:
        """
        Get all pending fees for an exchanger

        Args:
            exchanger_user_id: Exchanger's MongoDB user ID (ObjectId as string)

        Returns:
            Dict with pending fees list and total amount
        """
        server_fees = await get_db_collection("server_fees")

        # Get all pending fees
        cursor = server_fees.find({
            "exchanger_id": ObjectId(exchanger_user_id),
            "status": "pending_collection"
        })

        pending_fees = await cursor.to_list(length=100)

        total_pending_usd = sum(fee.get("amount_usd", 0) for fee in pending_fees)

        return {
            "pending_fees": [
                {
                    "fee_id": str(fee["_id"]),
                    "ticket_id": str(fee["ticket_id"]),
                    "amount_usd": fee.get("amount_usd", 0),
                    "asset": fee.get("asset", ""),
                    "created_at": fee.get("created_at")
                }
                for fee in pending_fees
            ],
            "total_pending_usd": total_pending_usd,
            "count": len(pending_fees)
        }

    @staticmethod
    async def collect_pending_fees(exchanger_user_id: str) -> Dict:
        """
        Collect all pending fees from exchanger
        Called automatically when exchanger tries to withdraw or has sufficient balance

        Args:
            exchanger_user_id: Exchanger's MongoDB user ID (ObjectId as string)

        Returns:
            Collection result with fees collected
        """
        server_fees = await get_db_collection("server_fees")
        deposits = await get_db_collection("exchanger_deposits")

        # Get all pending fees
        pending_info = await ServerFeeService.get_pending_fees(exchanger_user_id)

        if pending_info["count"] == 0:
            return {
                "status": "no_pending_fees",
                "fees_collected": 0,
                "total_collected_usd": 0
            }

        # Group pending fees by asset
        fees_by_asset = {}
        for fee in pending_info["pending_fees"]:
            asset = fee["asset"]
            if asset not in fees_by_asset:
                fees_by_asset[asset] = []
            fees_by_asset[asset].append(fee)

        collected_fees = []
        failed_fees = []

        # Collect fees for each asset
        for asset, fees in fees_by_asset.items():
            total_fee_usd = sum(f["amount_usd"] for f in fees)

            # Get deposit balance
            deposit = await deposits.find_one({
                "user_id": ObjectId(exchanger_user_id),
                "asset": asset
            })

            if not deposit:
                # Mark all fees for this asset as failed
                for fee in fees:
                    failed_fees.append(fee)
                continue

            balance_usd = deposit.get("balance_usd", 0)
            held_usd = deposit.get("held_units", 0)
            available_usd = balance_usd - held_usd

            if available_usd < total_fee_usd:
                # Insufficient balance for this asset
                for fee in fees:
                    failed_fees.append(fee)
                continue

            # Deduct fees
            await deposits.update_one(
                {
                    "user_id": ObjectId(exchanger_user_id),
                    "asset": asset
                },
                {
                    "$inc": {
                        "balance_usd": -total_fee_usd,
                        "balance": -(total_fee_usd / deposit.get("price_usd", 1.0))
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Mark fees as collected
            for fee in fees:
                await server_fees.update_one(
                    {"_id": ObjectId(fee["fee_id"])},
                    {
                        "$set": {
                            "status": "collected",
                            "collected_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                collected_fees.append(fee)

        logger.info(
            f"Pending fees collection for exchanger {exchanger_user_id}: "
            f"{len(collected_fees)} collected, {len(failed_fees)} failed"
        )

        return {
            "status": "completed",
            "fees_collected": len(collected_fees),
            "fees_failed": len(failed_fees),
            "total_collected_usd": sum(f["amount_usd"] for f in collected_fees),
            "total_failed_usd": sum(f["amount_usd"] for f in failed_fees)
        }

    @staticmethod
    async def can_withdraw(exchanger_user_id: str) -> tuple[bool, str]:
        """
        Check if exchanger can withdraw funds (no pending fees)

        Args:
            exchanger_user_id: Exchanger's MongoDB user ID (ObjectId as string)

        Returns:
            Tuple of (can_withdraw: bool, reason: str)
        """
        pending_info = await ServerFeeService.get_pending_fees(exchanger_user_id)

        if pending_info["count"] > 0:
            return (
                False,
                f"You have ${pending_info['total_pending_usd']:.2f} in pending server fees. "
                f"Please deposit funds to cover these fees before withdrawing."
            )

        return (True, "")
