"""
Exchange Service - Business logic for exchange operations
"""

from typing import Optional, List
from datetime import datetime, timedelta
from bson import ObjectId

from app.core.database import (
    get_exchanges_collection,
    get_users_collection,
    get_audit_logs_collection
)
from app.models.exchange import Exchange, ExchangeCreate


class ExchangeService:
    """Service for exchange operations"""

    # Fee configuration
    PLATFORM_FEE_PERCENT = 1.0
    DEFAULT_EXPIRY_HOURS = 24

    @staticmethod
    async def create_exchange(
        creator_id: str,
        exchange_data: ExchangeCreate
    ) -> dict:
        """Create new exchange"""
        exchanges = get_exchanges_collection()

        # Calculate fees
        platform_fee_amount = exchange_data.send_amount * (ExchangeService.PLATFORM_FEE_PERCENT / 100)

        # Calculate exchange rate
        exchange_rate = exchange_data.receive_amount / exchange_data.send_amount

        exchange_dict = {
            "creator_id": ObjectId(creator_id),
            "exchanger_id": None,
            "partner_id": None,
            "type": "crypto_to_crypto",
            "status": "pending",

            # Sender side
            "send_currency": exchange_data.send_currency.upper(),
            "send_amount": exchange_data.send_amount,
            "send_wallet_id": None,
            "send_tx_hash": None,

            # Receiver side
            "receive_currency": exchange_data.receive_currency.upper(),
            "receive_amount": exchange_data.receive_amount,
            "receive_wallet_id": None,
            "receive_tx_hash": None,

            # Rates & fees
            "exchange_rate": exchange_rate,
            "platform_fee_percent": ExchangeService.PLATFORM_FEE_PERCENT,
            "platform_fee_amount": platform_fee_amount,

            # Metadata
            "notes": exchange_data.notes,
            "risk_score": 0,
            "requires_kyc": False,

            # Timestamps
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=ExchangeService.DEFAULT_EXPIRY_HOURS),
            "updated_at": datetime.utcnow()
        }

        result = await exchanges.insert_one(exchange_dict)
        exchange_dict["_id"] = result.inserted_id

        # Log creation
        await ExchangeService.log_action(
            str(result.inserted_id),
            creator_id,
            "exchange.created",
            {"amount": exchange_data.send_amount, "currency": exchange_data.send_currency}
        )

        return exchange_dict

    @staticmethod
    async def accept_exchange(exchange_id: str, exchanger_id: str) -> dict:
        """Accept an exchange as exchanger"""
        exchanges = get_exchanges_collection()

        # Check if exchange is still pending
        exchange = await exchanges.find_one({"_id": ObjectId(exchange_id)})
        if not exchange:
            raise ValueError("Exchange not found")

        if exchange["status"] != "pending":
            raise ValueError("Exchange is not in pending status")

        if str(exchange["creator_id"]) == exchanger_id:
            raise ValueError("Cannot accept your own exchange")

        # Update exchange
        result = await exchanges.find_one_and_update(
            {"_id": ObjectId(exchange_id)},
            {
                "$set": {
                    "exchanger_id": ObjectId(exchanger_id),
                    "status": "active",
                    "accepted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        await ExchangeService.log_action(
            exchange_id,
            exchanger_id,
            "exchange.accepted",
            {}
        )

        return result

    @staticmethod
    async def cancel_exchange(exchange_id: str, user_id: str) -> dict:
        """Cancel an exchange"""
        from app.services.stats_tracking_service import StatsTrackingService

        exchanges = get_exchanges_collection()

        exchange = await exchanges.find_one({"_id": ObjectId(exchange_id)})
        if not exchange:
            raise ValueError("Exchange not found")

        # Only creator can cancel pending exchanges
        if exchange["status"] == "pending" and str(exchange["creator_id"]) != user_id:
            raise ValueError("Only creator can cancel pending exchange")

        if exchange["status"] not in ["pending", "active"]:
            raise ValueError("Cannot cancel exchange in current status")

        result = await exchanges.find_one_and_update(
            {"_id": ObjectId(exchange_id)},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        # Track cancellation stats
        if result:
            amount_usd = result.get("receive_amount", 0) or result.get("send_amount", 0)
            await StatsTrackingService.track_exchange_cancel(user_id, amount_usd)

        await ExchangeService.log_action(
            exchange_id,
            user_id,
            "exchange.cancelled",
            {}
        )

        return result

    @staticmethod
    async def complete_exchange(exchange_id: str) -> dict:
        """Mark exchange as completed"""
        from app.services.stats_tracking_service import StatsTrackingService

        exchanges = get_exchanges_collection()

        result = await exchanges.find_one_and_update(
            {"_id": ObjectId(exchange_id)},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        if result:
            # Update user reputation scores
            await ExchangeService.update_reputation_after_completion(result)

            # Track exchange completion stats
            client_id = str(result.get("creator_id"))
            exchanger_id = str(result.get("exchanger_id")) if result.get("exchanger_id") else None
            amount_usd = result.get("receive_amount", 0) or result.get("send_amount", 0)

            # Calculate platform fee (1% of exchange amount)
            fee_amount_usd = amount_usd * (ExchangeService.PLATFORM_FEE_PERCENT / 100)

            await StatsTrackingService.track_exchange_completion(
                client_id=client_id,
                exchanger_id=exchanger_id,
                amount_usd=amount_usd,
                fee_amount_usd=fee_amount_usd,
                ticket_id=None
            )

        await ExchangeService.log_action(
            exchange_id,
            "system",
            "exchange.completed",
            {}
        )

        return result

    @staticmethod
    async def list_exchanges(
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """List exchanges with filters"""
        exchanges = get_exchanges_collection()

        query = {}
        if user_id:
            query["$or"] = [
                {"creator_id": ObjectId(user_id)},
                {"exchanger_id": ObjectId(user_id)}
            ]
        if status:
            query["status"] = status

        cursor = exchanges.find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    async def update_reputation_after_completion(exchange: dict):
        """Update user reputation scores after successful exchange"""
        users = get_users_collection()

        # Increase reputation for both parties
        await users.update_one(
            {"_id": exchange["creator_id"]},
            {"$inc": {"reputation_score": 1}}
        )

        if exchange.get("exchanger_id"):
            await users.update_one(
                {"_id": exchange["exchanger_id"]},
                {"$inc": {"reputation_score": 1}}
            )

    @staticmethod
    async def log_action(exchange_id: str, user_id: str, action: str, details: dict):
        """Log exchange action"""
        audit_logs = get_audit_logs_collection()

        await audit_logs.insert_one({
            "user_id": ObjectId(user_id) if user_id != "system" else None,
            "actor_type": "user" if user_id != "system" else "system",
            "action": action,
            "resource_type": "exchange",
            "resource_id": ObjectId(exchange_id),
            "details": details,
            "created_at": datetime.utcnow()
        })
