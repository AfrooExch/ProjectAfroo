"""
Exchanger Deposit Service - V3 deposit system
Handles exchanger deposits, balance tracking, and claim limits
"""

from typing import Optional, Dict, List
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import (
    get_db_collection,
    get_audit_logs_collection
)
from app.core.config import settings
from app.models.exchanger_deposit import ExchangerDepositCreate

logger = logging.getLogger(__name__)


class ExchangerDepositService:
    """Service for exchanger deposit operations"""

    # Config values (from V3)
    CLAIM_LIMIT_MULTIPLIER = 1.0
    HOLD_MULTIPLIER = 1.0

    @staticmethod
    async def create_deposit_wallet(user_id: str, asset: str) -> dict:
        """
        Create exchanger deposit wallet.
        Returns platform deposit address for this asset.
        """
        db = await get_db_collection("exchanger_deposits")

        # Check if already exists
        existing = await db.find_one({
            "user_id": ObjectId(user_id),
            "asset": asset
        })

        if existing:
            return existing

        # Get platform wallet address for this asset from environment variables
        try:
            address = settings.get_admin_wallet(asset)
        except ValueError as e:
            raise ValueError(f"Asset {asset} not supported: {e}")

        # Create deposit record
        deposit_dict = {
            "user_id": ObjectId(user_id),
            "asset": asset,
            "address": address,  # Platform wallet

            # Balances
            "balance_units": 0.0,
            "held_units": 0.0,
            "fee_reserved_units": 0.0,

            # USD tracking
            "balance_usd": 0.0,
            "total_committed_usd": 0.0,
            "claim_limit_usd": 0.0,

            # Compensation balance (permanent, not affected by blockchain sync)
            "compensation_balance_usd": 0.0,

            # Monitoring
            "last_balance_check": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await db.insert_one(deposit_dict)
        deposit_dict["_id"] = result.inserted_id

        # Log creation
        await ExchangerDepositService.log_action(
            user_id,
            "deposit_wallet.created",
            {"asset": asset, "address": address}
        )

        return deposit_dict

    @staticmethod
    async def get_deposit(user_id: str, asset: str) -> Optional[dict]:
        """Get exchanger deposit by user and asset"""
        db = await get_db_collection("exchanger_deposits")

        return await db.find_one({
            "user_id": ObjectId(user_id),
            "asset": asset
        })

    @staticmethod
    async def list_deposits(user_id: str) -> List[dict]:
        """List all deposits for exchanger"""
        db = await get_db_collection("exchanger_deposits")

        cursor = db.find({"user_id": ObjectId(user_id)})
        return await cursor.to_list(length=100)

    @staticmethod
    async def get_balance(user_id: str, asset: str) -> Optional[dict]:
        """Get deposit balance with calculated values"""
        deposit = await ExchangerDepositService.get_deposit(user_id, asset)

        if not deposit:
            return None

        # Calculate available
        available = max(0.0,
            deposit["balance_units"] -
            deposit.get("held_units", 0.0) -
            deposit.get("fee_reserved_units", 0.0)
        )

        return {
            "asset": deposit["asset"],
            "balance_units": deposit["balance_units"],
            "held_units": deposit.get("held_units", 0.0),
            "fee_reserved_units": deposit.get("fee_reserved_units", 0.0),
            "available_units": available,
            "balance_usd": deposit.get("balance_usd", 0.0),
            "compensation_balance_usd": deposit.get("compensation_balance_usd", 0.0),
            "total_committed_usd": deposit.get("total_committed_usd", 0.0),
            "claim_limit_usd": deposit.get("claim_limit_usd", 0.0),
            "address": deposit["address"]
        }

    @staticmethod
    async def credit_deposit(
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float,
        tx_hash: str
    ) -> dict:
        """
        Credit exchanger deposit from blockchain confirmation.
        Called by webhook handler.
        """
        db = await get_db_collection("exchanger_deposits")

        # Update balance
        result = await db.find_one_and_update(
            {"user_id": ObjectId(user_id), "asset": asset},
            {
                "$inc": {
                    "balance_units": amount_units,
                    "balance_usd": amount_usd
                },
                "$set": {
                    "claim_limit_usd": f"$balance_usd * {ExchangerDepositService.CLAIM_LIMIT_MULTIPLIER}",
                    "updated_at": datetime.utcnow(),
                    "last_balance_check": datetime.utcnow()
                }
            },
            return_document=True
        )

        # Recalculate claim limit
        new_claim_limit = result["balance_usd"] * ExchangerDepositService.CLAIM_LIMIT_MULTIPLIER
        await db.update_one(
            {"_id": result["_id"]},
            {"$set": {"claim_limit_usd": new_claim_limit}}
        )

        # Log deposit
        await ExchangerDepositService.log_action(
            user_id,
            "deposit.credited",
            {
                "asset": asset,
                "amount_units": amount_units,
                "amount_usd": amount_usd,
                "tx_hash": tx_hash
            }
        )

        logger.info(f"Credited deposit: user={user_id} asset={asset} amount={amount_units} tx={tx_hash}")

        return result

    @staticmethod
    async def check_claim_limit(
        user_id: str,
        new_ticket_usd: float
    ) -> tuple[bool, str, float]:
        """
        Check if exchanger can claim ticket based on deposit limits.

        Returns:
            (can_claim, reason, remaining_limit)
        """
        db = await get_db_collection("exchanger_deposits")

        # Get all deposits for user
        deposits = await db.find({"user_id": ObjectId(user_id)}).to_list(length=100)

        if not deposits:
            return False, "No deposits found", 0.0

        # Calculate totals (include compensation balance for claim limit)
        total_balance_usd = sum(d.get("balance_usd", 0.0) for d in deposits)
        total_compensation_usd = sum(d.get("compensation_balance_usd", 0.0) for d in deposits)
        total_committed_usd = sum(d.get("total_committed_usd", 0.0) for d in deposits)
        # Claim limit includes both real deposits and compensation balance
        claim_limit_usd = (total_balance_usd + total_compensation_usd) * ExchangerDepositService.CLAIM_LIMIT_MULTIPLIER

        # Check if within limit
        new_total_committed = total_committed_usd + new_ticket_usd

        if new_total_committed > claim_limit_usd:
            remaining = claim_limit_usd - total_committed_usd
            return False, f"Would exceed claim limit (${new_total_committed:.2f} > ${claim_limit_usd:.2f})", remaining

        remaining = claim_limit_usd - new_total_committed
        return True, f"Within limits (${new_total_committed:.2f} <= ${claim_limit_usd:.2f})", remaining

    @staticmethod
    async def check_available_balance(
        user_id: str,
        asset: str,
        required_amount: float
    ) -> tuple[bool, str, float]:
        """
        Check if exchanger has sufficient available balance.

        Returns:
            (has_balance, reason, available)
        """
        deposit = await ExchangerDepositService.get_deposit(user_id, asset)

        if not deposit:
            return False, f"No {asset} deposit wallet found", 0.0

        available = max(0.0,
            deposit["balance_units"] -
            deposit.get("held_units", 0.0) -
            deposit.get("fee_reserved_units", 0.0)
        )

        if available < required_amount:
            return False, f"Insufficient available balance ({available:.8f} < {required_amount:.8f})", available

        return True, f"Sufficient balance ({available:.8f} >= {required_amount:.8f})", available

    @staticmethod
    async def log_action(user_id: str, action: str, details: dict):
        """Log exchanger deposit action"""
        audit_logs = get_audit_logs_collection()

        await audit_logs.insert_one({
            "user_id": ObjectId(user_id),
            "actor_type": "system",
            "action": action,
            "resource_type": "exchanger_deposit",
            "resource_id": ObjectId(user_id),
            "details": details,
            "created_at": datetime.utcnow()
        })
