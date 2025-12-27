"""
Fee Collection Service - Platform fee management
Auto-sends fees to admin wallets immediately, with fallback to hold list
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_db_collection, get_audit_logs_collection
from app.core.config import settings

logger = logging.getLogger(__name__)


class FeeCollectionService:
    """Service for fee collection operations"""

    # Fee configuration (from V3)
    FEE_RATE = 0.02  # 2%
    MIN_FEE_USD = 0.50  # $0.50 minimum

    # Auto-send configuration
    MIN_AUTO_SEND_USD = 1.00  # Only auto-send fees >= $1.00
    ADMIN_WALLETS = {}  # Will be loaded from config/database

    # USD conversion rates (fallback)
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
    async def calculate_fee(
        asset: str,
        amount_units: float,
        amount_usd: float
    ) -> Tuple[float, float]:
        """
        Calculate platform fee.

        Returns:
            (fee_units, fee_usd)
        """
        # Calculate 2% fee
        fee_usd = amount_usd * FeeCollectionService.FEE_RATE

        # Apply minimum
        fee_usd = max(fee_usd, FeeCollectionService.MIN_FEE_USD)

        # Convert to units
        fee_units = await FeeCollectionService._convert_usd_to_units(asset, fee_usd)

        return fee_units, fee_usd

    @staticmethod
    async def _convert_usd_to_units(asset: str, usd_amount: float) -> float:
        """Convert USD to crypto units"""
        # Get base asset for multi-network tokens
        base_asset = asset.split("-")[0] if "-" in asset else asset

        # Get rate (would use real price API in production)
        rate = FeeCollectionService.FALLBACK_RATES.get(base_asset, 1.0)

        return usd_amount / rate

    @staticmethod
    async def auto_send_fee(
        transaction_type: str,
        transaction_id: str,
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Auto-send fee to admin wallet immediately.

        If auto-send fails (low value, insufficient network fee, errors),
        stores in hold list (platform_fees with collected=false) for manual collection.

        Args:
            transaction_type: Type of transaction (ticket, afroo_wallet_send, swap)
            transaction_id: ID of source transaction
            user_id: User who generated the fee
            asset: Asset type
            amount_units: Fee amount in crypto units
            amount_usd: Fee amount in USD equivalent

        Returns:
            (success, message, fee_id)
        """
        try:
            # Check if fee meets minimum for auto-send
            if amount_usd < FeeCollectionService.MIN_AUTO_SEND_USD:
                logger.info(
                    f"Fee below auto-send minimum (${amount_usd:.2f} < $1.00). "
                    f"Adding to hold list for batch collection."
                )
                return await FeeCollectionService._add_to_hold_list(
                    transaction_type, transaction_id, user_id,
                    asset, amount_units, amount_usd,
                    reason="Below minimum auto-send amount"
                )

            # Get admin wallet address for this asset
            admin_wallet = await FeeCollectionService._get_admin_wallet(asset)
            if not admin_wallet:
                logger.warning(f"No admin wallet configured for {asset}. Adding to hold list.")
                return await FeeCollectionService._add_to_hold_list(
                    transaction_type, transaction_id, user_id,
                    asset, amount_units, amount_usd,
                    reason="No admin wallet configured"
                )

            # Check if we have sufficient network fee for sending
            # (e.g., USDC-SOL requires SOL for network fee)
            network_fee_check = await FeeCollectionService._check_network_fee(asset, amount_units)
            if not network_fee_check["sufficient"]:
                logger.warning(
                    f"Insufficient network fee to send {asset}: {network_fee_check['reason']}. "
                    f"Adding to hold list."
                )
                return await FeeCollectionService._add_to_hold_list(
                    transaction_type, transaction_id, user_id,
                    asset, amount_units, amount_usd,
                    reason=f"Insufficient network fee: {network_fee_check['reason']}"
                )

            # Attempt to send fee to admin wallet
            send_result = await FeeCollectionService._send_to_admin_wallet(
                asset=asset,
                amount_units=amount_units,
                admin_wallet=admin_wallet,
                transaction_type=transaction_type,
                reference_id=transaction_id
            )

            if send_result["success"]:
                # Record successful auto-send
                fee_id = await FeeCollectionService._record_collected_fee(
                    transaction_type, transaction_id, user_id,
                    asset, amount_units, amount_usd,
                    tx_hash=send_result.get("tx_hash")
                )

                logger.info(
                    f"Fee auto-sent successfully: {amount_units} {asset} "
                    f"(${amount_usd:.2f}) to admin wallet. TX: {send_result.get('tx_hash')}"
                )

                return True, "Fee sent to admin wallet", fee_id

            else:
                # Send failed, add to hold list
                logger.warning(f"Failed to send fee: {send_result['error']}. Adding to hold list.")
                return await FeeCollectionService._add_to_hold_list(
                    transaction_type, transaction_id, user_id,
                    asset, amount_units, amount_usd,
                    reason=f"Send failed: {send_result['error']}"
                )

        except Exception as e:
            logger.error(f"Error in auto-send fee: {e}", exc_info=True)
            # Add to hold list on any error
            return await FeeCollectionService._add_to_hold_list(
                transaction_type, transaction_id, user_id,
                asset, amount_units, amount_usd,
                reason=f"Exception: {str(e)}"
            )

    @staticmethod
    async def _add_to_hold_list(
        transaction_type: str,
        transaction_id: str,
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float,
        reason: str = ""
    ) -> Tuple[bool, str, str]:
        """Add fee to hold list for manual collection later"""
        fees_db = await get_db_collection("platform_fees")

        now = datetime.utcnow()
        month = now.strftime("%Y-%m")
        year = now.year

        fee_dict = {
            "transaction_type": transaction_type,
            "transaction_id": ObjectId(transaction_id) if transaction_id else None,
            "user_id": ObjectId(user_id),
            "asset": asset,
            "amount_units": amount_units,
            "amount_usd": amount_usd,

            # Hold list status
            "collected": False,
            "collected_at": None,
            "auto_send_attempted": True,
            "auto_send_failed_reason": reason,

            "month": month,
            "year": year,
            "created_at": now
        }

        result = await fees_db.insert_one(fee_dict)
        fee_id = str(result.inserted_id)

        logger.info(
            f"Fee added to hold list: {amount_units} {asset} (${amount_usd:.2f}). "
            f"Reason: {reason}"
        )

        return False, f"Fee added to hold list: {reason}", fee_id

    @staticmethod
    async def _get_admin_wallet(asset: str) -> Optional[str]:
        """Get admin wallet address for asset"""
        # Try to get from database first
        admin_wallets_db = await get_db_collection("admin_wallets")
        admin_wallet = await admin_wallets_db.find_one({"asset": asset, "active": True})

        if admin_wallet:
            return admin_wallet["address"]

        # Fallback to environment config
        # TODO: Add admin wallet addresses to config
        return None

    @staticmethod
    async def _check_network_fee(asset: str, amount: float) -> Dict:
        """Check if platform has sufficient network fee to send"""
        # For tokens like USDC-SOL or USDT-SOL, need SOL for network fee
        base_asset = asset.split("-")[0] if "-" in asset else asset
        network = asset.split("-")[1] if "-" in asset else None

        if network == "SOL":
            # Check if we have SOL for network fee
            platform_sol_balance = await FeeCollectionService._get_platform_balance("SOL")
            min_network_fee = 0.000005  # ~$0.001 in SOL

            if platform_sol_balance < min_network_fee:
                return {
                    "sufficient": False,
                    "reason": f"Need SOL for network fee (have {platform_sol_balance}, need {min_network_fee})"
                }

        elif network == "ETH":
            # Check if we have ETH for gas
            platform_eth_balance = await FeeCollectionService._get_platform_balance("ETH")
            min_gas_fee = 0.0001  # ~$0.35 in ETH

            if platform_eth_balance < min_gas_fee:
                return {
                    "sufficient": False,
                    "reason": f"Need ETH for gas (have {platform_eth_balance}, need {min_gas_fee})"
                }

        return {"sufficient": True, "reason": ""}

    @staticmethod
    async def _get_platform_balance(asset: str) -> float:
        """Get platform hot wallet balance"""
        # TODO: Implement actual balance checking from hot wallet
        # For now, return a placeholder
        return 1.0

    @staticmethod
    async def _send_to_admin_wallet(
        asset: str,
        amount_units: float,
        admin_wallet: str,
        transaction_type: str,
        reference_id: Optional[str] = None
    ) -> Dict:
        """Send fee to admin wallet via blockchain"""
        try:
            # Import crypto handler service
            from app.services.crypto_handler_service import CryptoHandlerService

            # Send from platform hot wallet to admin wallet
            # TODO: This requires platform hot wallet integration
            # For now, we'll simulate or mark as needing manual send

            logger.info(
                f"Sending {amount_units} {asset} to admin wallet {admin_wallet}..."
            )

            # In production, this would call:
            # tx_hash = await CryptoHandlerService.send_transaction(
            #     asset=asset,
            #     to_address=admin_wallet,
            #     amount=amount_units,
            #     memo=f"Platform fee - {transaction_type}"
            # )

            # For now, mark as manual send required
            return {
                "success": False,
                "error": "Platform hot wallet integration pending - add to hold list"
            }

        except Exception as e:
            logger.error(f"Error sending to admin wallet: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def _record_collected_fee(
        transaction_type: str,
        transaction_id: str,
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float,
        tx_hash: Optional[str] = None
    ) -> str:
        """Record successfully collected fee"""
        fees_db = await get_db_collection("platform_fees")

        now = datetime.utcnow()
        month = now.strftime("%Y-%m")
        year = now.year

        fee_dict = {
            "transaction_type": transaction_type,
            "transaction_id": ObjectId(transaction_id) if transaction_id else None,
            "user_id": ObjectId(user_id),
            "asset": asset,
            "amount_units": amount_units,
            "amount_usd": amount_usd,

            # Already collected
            "collected": True,
            "collected_at": now,
            "collection_tx_hash": tx_hash,
            "auto_sent": True,

            "month": month,
            "year": year,
            "created_at": now
        }

        result = await fees_db.insert_one(fee_dict)
        return str(result.inserted_id)

    @staticmethod
    async def collect_fee(
        transaction_type: str,
        transaction_id: str,
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float
    ) -> dict:
        """
        Collect platform fee - AUTO-SENDS to admin wallet.

        Deprecated: Use auto_send_fee() instead.
        This method now calls auto_send_fee for backward compatibility.
        """
        success, message, fee_id = await FeeCollectionService.auto_send_fee(
            transaction_type, transaction_id, user_id,
            asset, amount_units, amount_usd
        )

        return {
            "success": success,
            "message": message,
            "fee_id": fee_id,
            "auto_sent": success
        }

    @staticmethod
    async def _old_collect_fee_to_database(
        transaction_type: str,
        transaction_id: str,
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float
    ) -> dict:
        """
        OLD METHOD: Store in database for later admin collection.
        Kept for reference but not used anymore.
        """
        fees_db = await get_db_collection("platform_fees")

        now = datetime.utcnow()
        month = now.strftime("%Y-%m")
        year = now.year

        fee_dict = {
            "transaction_type": transaction_type,
            "transaction_id": ObjectId(transaction_id),
            "user_id": ObjectId(user_id),

            "asset": asset,
            "amount_units": amount_units,
            "amount_usd": amount_usd,

            # Collection status
            "collected": False,
            "collected_at": None,
            "collection_tx_hash": None,

            # Aggregation
            "month": month,
            "year": year,

            "created_at": now
        }

        result = await fees_db.insert_one(fee_dict)
        fee_dict["_id"] = result.inserted_id

        logger.info(
            f"Fee collected: type={transaction_type} user={user_id} "
            f"asset={asset} amount={amount_units} usd=${amount_usd}"
        )

        return fee_dict

    @staticmethod
    async def get_uncollected_fees(asset: Optional[str] = None) -> List[dict]:
        """Get uncollected fees, optionally filtered by asset"""
        fees_db = await get_db_collection("platform_fees")

        query = {"collected": False}
        if asset:
            query["asset"] = asset

        cursor = fees_db.find(query).sort("created_at", 1)
        return await cursor.to_list(length=1000)

    @staticmethod
    async def get_fee_summary(
        asset: Optional[str] = None,
        collected: Optional[bool] = None
    ) -> Dict:
        """Get fee summary statistics"""
        fees_db = await get_db_collection("platform_fees")

        query = {}
        if asset:
            query["asset"] = asset
        if collected is not None:
            query["collected"] = collected

        fees = await fees_db.find(query).to_list(length=10000)

        # Group by asset
        summary = {}
        for fee in fees:
            asset_key = fee["asset"]
            if asset_key not in summary:
                summary[asset_key] = {
                    "asset": asset_key,
                    "total_units": 0.0,
                    "total_usd": 0.0,
                    "count": 0
                }

            summary[asset_key]["total_units"] += fee["amount_units"]
            summary[asset_key]["total_usd"] += fee["amount_usd"]
            summary[asset_key]["count"] += 1

        return {
            "by_asset": list(summary.values()),
            "total_usd": sum(s["total_usd"] for s in summary.values()),
            "total_fees": len(fees)
        }

    @staticmethod
    async def mark_fees_collected(
        fee_ids: List[str],
        tx_hash: str
    ) -> int:
        """Mark fees as collected (admin withdrew to owner wallet)"""
        fees_db = await get_db_collection("platform_fees")

        object_ids = [ObjectId(fid) for fid in fee_ids]

        result = await fees_db.update_many(
            {"_id": {"$in": object_ids}},
            {
                "$set": {
                    "collected": True,
                    "collected_at": datetime.utcnow(),
                    "collection_tx_hash": tx_hash
                }
            }
        )

        logger.info(f"Marked {result.modified_count} fees as collected, tx={tx_hash}")

        return result.modified_count

    @staticmethod
    async def get_monthly_report(month: str) -> Dict:
        """Get fee report for specific month (format: YYYY-MM)"""
        fees_db = await get_db_collection("platform_fees")

        fees = await fees_db.find({"month": month}).to_list(length=10000)

        # Aggregate
        total_usd = sum(f["amount_usd"] for f in fees)
        by_asset = {}

        for fee in fees:
            asset = fee["asset"]
            if asset not in by_asset:
                by_asset[asset] = {
                    "asset": asset,
                    "total_units": 0.0,
                    "total_usd": 0.0,
                    "count": 0
                }

            by_asset[asset]["total_units"] += fee["amount_units"]
            by_asset[asset]["total_usd"] += fee["amount_usd"]
            by_asset[asset]["count"] += 1

        return {
            "month": month,
            "total_usd": total_usd,
            "total_fees": len(fees),
            "by_asset": list(by_asset.values())
        }
