"""
Afroo Wallet Service - V4 custodial wallet system
Provides internal wallets for users to store crypto on platform
"""

from typing import Optional, Dict, List
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_db_collection

logger = logging.getLogger(__name__)


class AfrooWalletService:
    """Service for Afroo custodial wallet operations"""

    # Supported assets
    SUPPORTED_ASSETS = [
        "BTC", "ETH", "LTC", "SOL",
        "USDT-SOL", "USDT-ETH",
        "USDC-SOL", "USDC-ETH"
    ]

    # Transaction fees (for sends/withdrawals)
    TRANSACTION_FEE_RATE = 0.005  # 0.5%
    MIN_TRANSACTION_FEE_USD = 0.10  # $0.10 minimum

    # USD conversion rates (fallback - should use real-time prices)
    FALLBACK_RATES = {
        "BTC": 100000.0,
        "ETH": 3500.0,
        "LTC": 120.0,
        "SOL": 218.0,
        "USDT": 1.0,
        "USDC": 1.0,
        "USDT-SOL": 1.0,
        "USDT-ETH": 1.0,
        "USDC-SOL": 1.0,
        "USDC-ETH": 1.0
    }

    @staticmethod
    async def create_wallet(user_id: str, asset: str) -> dict:
        """
        Create Afroo wallet for user.
        Internal wallet - no blockchain address generated.
        """
        if asset not in AfrooWalletService.SUPPORTED_ASSETS:
            raise ValueError(f"Asset {asset} not supported")

        wallets_db = await get_db_collection("afroo_wallets")

        # Check if already exists
        existing = await wallets_db.find_one({
            "user_id": ObjectId(user_id),
            "asset": asset
        })

        if existing:
            return existing

        # Create wallet
        wallet_dict = {
            "user_id": ObjectId(user_id),
            "asset": asset,
            "balance": 0.0,
            "locked_balance": 0.0,  # For pending swaps/trades
            "total_deposited": 0.0,
            "total_withdrawn": 0.0,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await wallets_db.insert_one(wallet_dict)
        wallet_dict["_id"] = result.inserted_id

        logger.info(f"Afroo wallet created: user={user_id} asset={asset}")

        return wallet_dict

    @staticmethod
    async def get_wallet(user_id: str, asset: str) -> Optional[dict]:
        """Get Afroo wallet"""
        wallets_db = await get_db_collection("afroo_wallets")

        return await wallets_db.find_one({
            "user_id": ObjectId(user_id),
            "asset": asset
        })

    @staticmethod
    async def list_wallets(user_id: str) -> List[dict]:
        """List all Afroo wallets for user"""
        wallets_db = await get_db_collection("afroo_wallets")

        cursor = wallets_db.find({"user_id": ObjectId(user_id)})
        return await cursor.to_list(length=100)

    @staticmethod
    async def get_balance(user_id: str, asset: str) -> dict:
        """Get wallet balance with availability"""
        wallet = await AfrooWalletService.get_wallet(user_id, asset)

        if not wallet:
            return {
                "asset": asset,
                "balance": 0.0,
                "locked_balance": 0.0,
                "available_balance": 0.0
            }

        available = wallet["balance"] - wallet.get("locked_balance", 0.0)

        return {
            "asset": asset,
            "balance": wallet["balance"],
            "locked_balance": wallet.get("locked_balance", 0.0),
            "available_balance": max(0.0, available)
        }

    @staticmethod
    async def credit(
        user_id: str,
        asset: str,
        amount: float,
        source: str,
        reference_id: Optional[str] = None
    ) -> dict:
        """
        Credit Afroo wallet.
        Used for: deposits, swap credits, internal transfers
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        wallets_db = await get_db_collection("afroo_wallets")

        # Ensure wallet exists
        wallet = await AfrooWalletService.get_wallet(user_id, asset)
        if not wallet:
            wallet = await AfrooWalletService.create_wallet(user_id, asset)

        # Update balance
        result = await wallets_db.find_one_and_update(
            {"_id": wallet["_id"]},
            {
                "$inc": {
                    "balance": amount,
                    "total_deposited": amount
                },
                "$set": {"updated_at": datetime.utcnow()}
            },
            return_document=True
        )

        # Record transaction
        await AfrooWalletService._record_transaction(
            user_id=user_id,
            asset=asset,
            amount=amount,
            type="credit",
            source=source,
            reference_id=reference_id
        )

        logger.info(
            f"Afroo wallet credited: user={user_id} asset={asset} "
            f"amount={amount} source={source}"
        )

        return result

    @staticmethod
    async def calculate_transaction_fee(asset: str, amount_units: float) -> dict:
        """
        Calculate transaction fee for Afroo Wallet sends.

        Fee: 0.5% of amount, minimum $0.10 USD equivalent

        Returns:
            {
                "fee_units": float,
                "fee_usd": float,
                "amount_after_fee": float
            }
        """
        # Get base asset for multi-network tokens
        base_asset = asset.split("-")[0] if "-" in asset else asset

        # Get USD value of amount
        rate = AfrooWalletService.FALLBACK_RATES.get(base_asset, 1.0)
        amount_usd = amount_units * rate

        # Calculate 0.5% fee
        fee_usd = amount_usd * AfrooWalletService.TRANSACTION_FEE_RATE

        # Apply minimum
        fee_usd = max(fee_usd, AfrooWalletService.MIN_TRANSACTION_FEE_USD)

        # Convert fee back to units
        fee_units = fee_usd / rate

        return {
            "fee_units": fee_units,
            "fee_usd": fee_usd,
            "amount_after_fee": amount_units - fee_units
        }

    @staticmethod
    async def debit(
        user_id: str,
        asset: str,
        amount: float,
        destination: str,
        reference_id: Optional[str] = None,
        charge_fee: bool = True
    ) -> dict:
        """
        Debit Afroo wallet.
        Used for: withdrawals, swap debits, internal transfers

        Args:
            charge_fee: If True, charges 0.5% transaction fee (min $0.10)
                       Set to False for internal transfers (free)
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Calculate fee if applicable
        fee_info = None
        total_debit = amount

        if charge_fee and destination not in ["internal_transfer", "swap"]:
            fee_info = await AfrooWalletService.calculate_transaction_fee(asset, amount)
            total_debit = amount + fee_info["fee_units"]

        # Check balance (including fee)
        balance_info = await AfrooWalletService.get_balance(user_id, asset)
        if balance_info["available_balance"] < total_debit:
            if fee_info:
                raise ValueError(
                    f"Insufficient balance: need {total_debit} (amount {amount} + fee {fee_info['fee_units']}) "
                    f"but have {balance_info['available_balance']}"
                )
            else:
                raise ValueError(
                    f"Insufficient balance: {balance_info['available_balance']} < {total_debit}"
                )

        wallets_db = await get_db_collection("afroo_wallets")
        wallet = await AfrooWalletService.get_wallet(user_id, asset)

        # Update balance (deduct amount + fee)
        result = await wallets_db.find_one_and_update(
            {"_id": wallet["_id"]},
            {
                "$inc": {
                    "balance": -total_debit,
                    "total_withdrawn": amount  # Track only the send amount, not fee
                },
                "$set": {"updated_at": datetime.utcnow()}
            },
            return_document=True
        )

        # Record transaction
        await AfrooWalletService._record_transaction(
            user_id=user_id,
            asset=asset,
            amount=amount,
            type="debit",
            destination=destination,
            reference_id=reference_id,
            fee_units=fee_info["fee_units"] if fee_info else 0.0,
            fee_usd=fee_info["fee_usd"] if fee_info else 0.0
        )

        # Collect platform fee if charged
        if fee_info:
            await AfrooWalletService._collect_platform_fee(
                user_id=user_id,
                asset=asset,
                fee_units=fee_info["fee_units"],
                fee_usd=fee_info["fee_usd"],
                transaction_type="afroo_wallet_send",
                reference_id=reference_id
            )

        logger.info(
            f"Afroo wallet debited: user={user_id} asset={asset} "
            f"amount={amount} fee={fee_info['fee_units'] if fee_info else 0} "
            f"destination={destination}"
        )

        return {
            **result,
            "fee_charged": fee_info is not None,
            "fee_info": fee_info
        }

    @staticmethod
    async def internal_transfer(
        from_user_id: str,
        to_user_id: str,
        asset: str,
        amount: float
    ) -> dict:
        """
        Internal transfer between Afroo wallets.
        No blockchain transaction - instant and FREE (no fees).
        """
        # Debit sender (NO FEE for internal transfers)
        await AfrooWalletService.debit(
            user_id=from_user_id,
            asset=asset,
            amount=amount,
            destination="internal_transfer",
            reference_id=to_user_id,
            charge_fee=False  # FREE for internal transfers
        )

        # Credit receiver
        await AfrooWalletService.credit(
            user_id=to_user_id,
            asset=asset,
            amount=amount,
            source="internal_transfer",
            reference_id=from_user_id
        )

        logger.info(
            f"Internal transfer: from={from_user_id} to={to_user_id} "
            f"asset={asset} amount={amount}"
        )

        return {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "asset": asset,
            "amount": amount,
            "timestamp": datetime.utcnow()
        }

    @staticmethod
    async def _record_transaction(
        user_id: str,
        asset: str,
        amount: float,
        type: str,
        source: Optional[str] = None,
        destination: Optional[str] = None,
        reference_id: Optional[str] = None,
        fee_units: float = 0.0,
        fee_usd: float = 0.0
    ):
        """Record wallet transaction"""
        txs_db = await get_db_collection("afroo_wallet_transactions")

        tx_dict = {
            "user_id": ObjectId(user_id),
            "asset": asset,
            "amount": amount,
            "type": type,
            "source": source,
            "destination": destination,
            "reference_id": reference_id,
            "fee_units": fee_units,
            "fee_usd": fee_usd,
            "created_at": datetime.utcnow()
        }

        await txs_db.insert_one(tx_dict)

    @staticmethod
    async def _collect_platform_fee(
        user_id: str,
        asset: str,
        fee_units: float,
        fee_usd: float,
        transaction_type: str,
        reference_id: Optional[str] = None
    ):
        """Record platform fee collection for admin"""
        fees_db = await get_db_collection("platform_fees")

        now = datetime.utcnow()
        month = now.strftime("%Y-%m")
        year = now.year

        fee_dict = {
            "transaction_type": transaction_type,
            "transaction_id": reference_id,
            "user_id": ObjectId(user_id),
            "asset": asset,
            "amount_units": fee_units,
            "amount_usd": fee_usd,
            "collected": False,  # Admin collects later
            "collected_at": None,
            "month": month,
            "year": year,
            "created_at": now
        }

        await fees_db.insert_one(fee_dict)

        logger.info(
            f"Platform fee recorded: user={user_id} asset={asset} "
            f"fee_units={fee_units} fee_usd={fee_usd} type={transaction_type}"
        )
