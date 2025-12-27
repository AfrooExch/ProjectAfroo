"""
Afroo Swap Service - V4 instant exchange system
Provides instant crypto-to-crypto swaps using ChangeNow external provider
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_db_collection
from app.services.changenow_service import ChangeNowService
from app.services.afroo_wallet_service import AfrooWalletService
from app.services.crypto_handler_service import CryptoHandlerService
from app.services.fee_collection_service import FeeCollectionService

logger = logging.getLogger(__name__)


class AfrooSwapService:
    """Service for instant swap operations via ChangeNow"""

    # Platform swap fee - disabled since ChangeNOW takes commission for us
    PLATFORM_SWAP_FEE_RATE = 0.0  # 0%

    @staticmethod
    async def get_swap_quote(
        from_asset: str,
        to_asset: str,
        amount: float
    ) -> Dict:
        """
        Get swap quote from ChangeNow with fees.

        Args:
            from_asset: Source asset code
            to_asset: Destination asset code
            amount: Amount to swap

        Returns:
            Dict with quote details
        """
        try:
            # Check exchange range
            range_data = await ChangeNowService.get_exchange_range(from_asset, to_asset)
            if not range_data:
                raise ValueError(f"Exchange pair {from_asset}→{to_asset} not available")

            # Handle null values from ChangeNOW API
            min_amount = float(range_data.get("minAmount") or 0)
            max_amount_raw = range_data.get("maxAmount")
            max_amount = float(max_amount_raw) if max_amount_raw is not None else None

            if amount < min_amount:
                raise ValueError(
                    f"Amount below minimum: {amount} < {min_amount} {from_asset}"
                )

            if max_amount is not None and amount > max_amount:
                raise ValueError(
                    f"Amount above maximum: {amount} > {max_amount} {from_asset}"
                )

            # Get estimate from ChangeNow
            estimate = await ChangeNowService.get_estimated_amount(
                from_asset,
                to_asset,
                amount
            )

            if not estimate:
                raise ValueError("Failed to get exchange estimate")

            # Calculate platform fee
            platform_fee_units = amount * AfrooSwapService.PLATFORM_SWAP_FEE_RATE

            # Calculate Afroo platform fee in USD for fee collection
            from_asset_usd_price = await AfrooSwapService._get_usd_price(from_asset)
            platform_fee_usd = platform_fee_units * from_asset_usd_price

            total_deducted = amount + platform_fee_units

            return {
                "from_asset": from_asset,
                "to_asset": to_asset,
                "input_amount": amount,
                "estimated_output": estimate["estimated_amount"],
                "exchange_rate": estimate["estimated_rate"],
                "changenow_network_fee": estimate["network_fee"],
                "changenow_service_fee": estimate["service_fee"],
                "platform_fee_units": platform_fee_units,
                "platform_fee_usd": platform_fee_usd,
                "platform_fee_percent": AfrooSwapService.PLATFORM_SWAP_FEE_RATE * 100,
                "total_deducted": total_deducted,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "valid_until": estimate.get("valid_until"),
                "provider": "ChangeNow"
            }

        except Exception as e:
            logger.error(f"Failed to get swap quote: {e}", exc_info=True)
            raise

    @staticmethod
    async def execute_swap(
        user_id: str,
        from_asset: str,
        to_asset: str,
        amount: float,
        destination_address: str,
        refund_address: Optional[str] = None,
        slippage_tolerance: float = 0.01  # 1%
    ) -> Dict:
        """
        Execute instant swap via ChangeNow - creates exchange order.

        Flow:
        1. Get quote from ChangeNow
        2. Create ChangeNow exchange order
        3. Return ChangeNow deposit address (user sends to this)
        4. ChangeNow processes and sends to user's destination address
        5. Monitor and update status

        Args:
            user_id: User ID
            from_asset: Source asset
            to_asset: Destination asset
            amount: Amount to swap
            destination_address: Where user wants to receive swapped crypto
            refund_address: Where to refund if swap fails (optional)
            slippage_tolerance: Max acceptable slippage

        Returns:
            Dict with swap details including ChangeNow deposit address
        """
        try:
            # Get quote
            quote = await AfrooSwapService.get_swap_quote(from_asset, to_asset, amount)

            # Create ChangeNow exchange
            # User will send to ChangeNOW deposit address (shown in ticket with QR)
            # ChangeNOW will send swapped funds to destination_address
            success, exchange_data, error_msg = await ChangeNowService.create_exchange(
                from_currency=from_asset,
                to_currency=to_asset,
                from_amount=amount,
                to_address=destination_address,
                refund_address=refund_address
            )

            if not success:
                raise ValueError(f"ChangeNow exchange creation failed: {error_msg}")

            # Create swap record
            swaps_db = await get_db_collection("afroo_swaps")

            swap_dict = {
                "user_id": ObjectId(user_id),
                "from_asset": from_asset,
                "to_asset": to_asset,
                "input_amount": amount,
                "estimated_output": quote["estimated_output"],
                "exchange_rate": quote["exchange_rate"],
                "platform_fee_units": quote["platform_fee_units"],
                "platform_fee_usd": quote["platform_fee_usd"],
                "changenow_network_fee": quote["changenow_network_fee"],
                "changenow_service_fee": quote["changenow_service_fee"],
                "total_deducted": quote["total_deducted"],
                "changenow_exchange_id": exchange_data["exchange_id"],
                "changenow_deposit_address": exchange_data["deposit_address"],
                "destination_address": destination_address,
                "refund_address": refund_address,
                "status": "pending",  # pending → processing → completed/failed
                "changenow_status": exchange_data["status"],
                "created_at": datetime.utcnow()
            }

            result = await swaps_db.insert_one(swap_dict)
            swap_id = str(result.inserted_id)

            logger.info(
                f"Swap ticket created: user={user_id} {from_asset}→{to_asset} "
                f"amount={amount} changenow_id={exchange_data['exchange_id']}"
            )

            return {
                "_id": swap_id,
                "swap_id": swap_id,
                "changenow_exchange_id": exchange_data["exchange_id"],
                "changenow_deposit_address": exchange_data["deposit_address"],
                "from_asset": from_asset,
                "to_asset": to_asset,
                "input_amount": amount,
                "estimated_output": quote["estimated_output"],
                "exchange_rate": quote["exchange_rate"],
                "destination_address": destination_address,
                "refund_address": refund_address,
                "status": "pending",
                "message": f"Send {amount} {from_asset} to ChangeNow deposit address"
            }

        except Exception as e:
            logger.error(f"Swap execution failed: {e}", exc_info=True)
            raise

    @staticmethod
    async def update_swap_status(swap_id: str) -> bool:
        """
        Update swap status from ChangeNow.
        Called by webhook handler or periodic checker.

        Args:
            swap_id: Afroo swap ID

        Returns:
            Success status
        """
        try:
            swaps_db = await get_db_collection("afroo_swaps")

            swap = await swaps_db.find_one({"_id": ObjectId(swap_id)})
            if not swap:
                logger.error(f"Swap {swap_id} not found")
                return False

            changenow_id = swap.get("changenow_exchange_id")
            if not changenow_id:
                logger.error(f"Swap {swap_id} has no ChangeNow exchange ID")
                return False

            # Get status from ChangeNow
            exchange_status = await ChangeNowService.get_exchange_status(changenow_id)
            if not exchange_status:
                logger.warning(f"Failed to get ChangeNow status for {changenow_id}")
                return False

            changenow_status = exchange_status["status"]
            afroo_status = ChangeNowService.parse_changenow_status(changenow_status)

            # Update database
            update_dict = {
                "changenow_status": changenow_status,
                "status": afroo_status,
                "last_status_check": datetime.utcnow()
            }

            # If completed - ChangeNOW already sent to user's destination address
            if afroo_status == "completed" and swap["status"] != "completed":
                from app.services.stats_tracking_service import StatsTrackingService

                actual_output = exchange_status.get("toAmount", swap["estimated_output"])
                payout_hash = exchange_status.get("payoutHash")

                update_dict["actual_output"] = actual_output
                update_dict["completed_at"] = datetime.utcnow()
                update_dict["payout_hash"] = payout_hash
                update_dict["payout_link"] = exchange_status.get("payoutLink")
                update_dict["notification_pending"] = True  # Mark for bot notification

                # Track swap completion stats with USD value
                from_asset_usd_price = await AfrooSwapService._get_usd_price(swap["from_asset"])
                swap_value_usd = swap["input_amount"] * from_asset_usd_price

                await StatsTrackingService.track_swap_completion(
                    user_id=str(swap["user_id"]),
                    from_amount=swap["input_amount"],
                    to_amount=actual_output,
                    from_asset=swap["from_asset"],
                    to_asset=swap["to_asset"],
                    amount_usd=swap_value_usd
                )

                logger.info(
                    f"Swap completed: {swap_id} - User received {actual_output} "
                    f"{swap['to_asset']} at {swap.get('destination_address', 'N/A')} (tx: {payout_hash})"
                )

            # If failed - no refund needed (user never sent funds to us)
            elif afroo_status == "failed" and swap["status"] not in ["failed", "refunded"]:
                from app.services.stats_tracking_service import StatsTrackingService

                update_dict["failed_at"] = datetime.utcnow()
                update_dict["status"] = "failed"

                # Track swap failure stats
                await StatsTrackingService.track_swap_failure(str(swap["user_id"]))

                logger.warning(
                    f"Swap failed: {swap_id} - {changenow_status}"
                )

            await swaps_db.update_one(
                {"_id": ObjectId(swap_id)},
                {"$set": update_dict}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update swap status {swap_id}: {e}", exc_info=True)
            return False

    @staticmethod
    async def get_swap_history(
        user_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get user swap history"""
        swaps_db = await get_db_collection("afroo_swaps")

        cursor = swaps_db.find({
            "user_id": ObjectId(user_id)
        }).sort("created_at", -1).limit(limit)

        swaps = await cursor.to_list(length=limit)

        # Serialize ObjectIds
        for swap in swaps:
            swap["_id"] = str(swap["_id"])
            swap["user_id"] = str(swap["user_id"])

        return swaps

    @staticmethod
    async def get_swap_details(swap_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get detailed swap information.

        Args:
            swap_id: Swap ID
            user_id: User ID for ownership verification (optional)

        Returns:
            Swap details or None
        """
        swaps_db = await get_db_collection("afroo_swaps")

        # Build query with optional user_id filter
        query = {"_id": ObjectId(swap_id)}
        if user_id:
            query["user_id"] = ObjectId(user_id)

        swap = await swaps_db.find_one(query)
        if not swap:
            return None

        # Get latest ChangeNow status
        if swap.get("changenow_exchange_id"):
            exchange_status = await ChangeNowService.get_exchange_status(
                swap["changenow_exchange_id"]
            )
            if exchange_status:
                swap["changenow_latest_status"] = exchange_status

        swap["_id"] = str(swap["_id"])
        swap["user_id"] = str(swap["user_id"])

        return swap

    @staticmethod
    async def _get_usd_price(asset: str) -> float:
        """
        Get USD price for asset.
        TODO: Integrate with real price API (Tatum or CoinGecko).
        """
        # Current market rates (keep in sync with bot modal)
        rates = {
            "BTC": 90000.0,
            "ETH": 3200.0,
            "LTC": 85.0,
            "SOL": 150.0,
            "USDT-SOL": 1.0,
            "USDC-SOL": 1.0,
            "USDT-ETH": 1.0,
            "USDC-ETH": 1.0
        }

        base_asset = asset.split("-")[0] if "-" in asset else asset
        return rates.get(base_asset, 1.0)


# Background task to update pending swap statuses
async def update_pending_swaps():
    """
    Update status for all pending/processing swaps.
    Should be called periodically by background task scheduler.
    """
    try:
        swaps_db = await get_db_collection("afroo_swaps")

        # Get all swaps that are not completed, failed, or expired
        cursor = swaps_db.find({
            "status": {"$in": ["pending", "waiting", "confirming", "exchanging", "sending", "verifying", "processing"]}
        })

        swaps = await cursor.to_list(length=1000)

        updated_count = 0
        for swap in swaps:
            success = await AfrooSwapService.update_swap_status(str(swap["_id"]))
            if success:
                updated_count += 1

        logger.info(f"Updated {updated_count}/{len(swaps)} pending swaps")

        return {"checked": len(swaps), "updated": updated_count}

    except Exception as e:
        logger.error(f"Failed to update pending swaps: {e}", exc_info=True)
        return {"error": str(e)}
