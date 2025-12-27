"""
Balance Sync Service - Periodic blockchain balance reconciliation
Ensures database balances match actual blockchain balances
Detects and handles drift, provides alerts for discrepancies
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
from decimal import Decimal
import logging
import asyncio

from app.core.database import get_db_collection
from app.services.crypto_handler_service import CryptoHandlerService
from app.core.config import settings

logger = logging.getLogger(__name__)


class BalanceSyncService:
    """Service for syncing blockchain balances with database"""

    # Drift tolerance (1% or 0.0001 units, whichever is larger)
    DRIFT_TOLERANCE_PERCENT = 0.01
    DRIFT_TOLERANCE_MIN_UNITS = 0.0001

    # Sync intervals
    SYNC_INTERVAL_MINUTES = 30  # How often to sync all wallets
    CRITICAL_DRIFT_THRESHOLD = 0.05  # 5% drift triggers immediate alert

    @staticmethod
    async def sync_all_deposit_wallets(force: bool = False) -> Dict:
        """
        Sync all exchanger deposit wallets.

        Args:
            force: Force sync even if recently synced

        Returns:
            Dict with sync results
        """
        try:
            deposits_db = await get_db_collection("exchanger_deposits")

            # Get all active deposits
            query = {"balance_units": {"$gt": 0}}
            if not force:
                # Skip recently synced (within last 30 min)
                recent_cutoff = datetime.utcnow() - timedelta(
                    minutes=BalanceSyncService.SYNC_INTERVAL_MINUTES
                )
                query["last_synced"] = {"$lt": recent_cutoff}

            cursor = deposits_db.find(query)
            deposits = await cursor.to_list(length=10000)

            results = {
                "total_checked": len(deposits),
                "synced": 0,
                "drifts_detected": 0,
                "critical_drifts": 0,
                "errors": 0,
                "drifts": []
            }

            for deposit in deposits:
                success, drift_info = await BalanceSyncService._sync_deposit_wallet(
                    deposit_id=str(deposit["_id"]),
                    user_id=str(deposit["user_id"]),
                    asset=deposit["asset"],
                    address=deposit["address"],
                    db_balance=deposit["balance_units"]
                )

                if success:
                    results["synced"] += 1
                    if drift_info and drift_info.get("has_drift"):
                        results["drifts_detected"] += 1
                        results["drifts"].append(drift_info)

                        if drift_info.get("is_critical"):
                            results["critical_drifts"] += 1
                else:
                    results["errors"] += 1

            logger.info(
                f"Deposit wallet sync complete: {results['synced']}/{results['total_checked']} synced, "
                f"{results['drifts_detected']} drifts detected"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to sync deposit wallets: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    async def sync_all_afroo_wallets(force: bool = False) -> Dict:
        """
        Sync all Afroo custodial wallets.

        Args:
            force: Force sync even if recently synced

        Returns:
            Dict with sync results
        """
        try:
            wallets_db = await get_db_collection("afroo_wallets")

            # Get all wallets with balance
            query = {"balance_units": {"$gt": 0}}
            if not force:
                recent_cutoff = datetime.utcnow() - timedelta(
                    minutes=BalanceSyncService.SYNC_INTERVAL_MINUTES
                )
                query["last_synced"] = {"$lt": recent_cutoff}

            cursor = wallets_db.find(query)
            wallets = await cursor.to_list(length=10000)

            results = {
                "total_checked": len(wallets),
                "synced": 0,
                "drifts_detected": 0,
                "critical_drifts": 0,
                "errors": 0,
                "drifts": []
            }

            for wallet in wallets:
                success, drift_info = await BalanceSyncService._sync_afroo_wallet(
                    wallet_id=str(wallet["_id"]),
                    user_id=str(wallet["user_id"]),
                    asset=wallet["asset"],
                    address=wallet["address"],
                    db_balance=wallet["balance_units"]
                )

                if success:
                    results["synced"] += 1
                    if drift_info and drift_info.get("has_drift"):
                        results["drifts_detected"] += 1
                        results["drifts"].append(drift_info)

                        if drift_info.get("is_critical"):
                            results["critical_drifts"] += 1
                else:
                    results["errors"] += 1

            logger.info(
                f"Afroo wallet sync complete: {results['synced']}/{results['total_checked']} synced, "
                f"{results['drifts_detected']} drifts detected"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to sync Afroo wallets: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    async def sync_deposit_wallet(deposit_id: str) -> Tuple[bool, Optional[Dict]]:
        """
        Sync single deposit wallet.

        Args:
            deposit_id: Deposit record ID

        Returns:
            Tuple of (success, drift_info)
        """
        try:
            deposits_db = await get_db_collection("exchanger_deposits")

            deposit = await deposits_db.find_one({"_id": ObjectId(deposit_id)})
            if not deposit:
                return False, None

            return await BalanceSyncService._sync_deposit_wallet(
                deposit_id=deposit_id,
                user_id=str(deposit["user_id"]),
                asset=deposit["asset"],
                address=deposit["address"],
                db_balance=deposit["balance_units"]
            )

        except Exception as e:
            logger.error(f"Failed to sync deposit wallet {deposit_id}: {e}")
            return False, None

    @staticmethod
    async def sync_afroo_wallet(wallet_id: str) -> Tuple[bool, Optional[Dict]]:
        """
        Sync single Afroo wallet.

        Args:
            wallet_id: Wallet record ID

        Returns:
            Tuple of (success, drift_info)
        """
        try:
            wallets_db = await get_db_collection("afroo_wallets")

            wallet = await wallets_db.find_one({"_id": ObjectId(wallet_id)})
            if not wallet:
                return False, None

            return await BalanceSyncService._sync_afroo_wallet(
                wallet_id=wallet_id,
                user_id=str(wallet["user_id"]),
                asset=wallet["asset"],
                address=wallet["address"],
                db_balance=wallet["balance_units"]
            )

        except Exception as e:
            logger.error(f"Failed to sync Afroo wallet {wallet_id}: {e}")
            return False, None

    @staticmethod
    async def _sync_deposit_wallet(
        deposit_id: str,
        user_id: str,
        asset: str,
        address: str,
        db_balance: float
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Sync deposit wallet with blockchain.

        Args:
            deposit_id: Deposit record ID
            user_id: User ID
            asset: Asset code
            address: Blockchain address
            db_balance: Current database balance

        Returns:
            Tuple of (success, drift_info)
        """
        try:
            # Get blockchain balance
            balance_data = await CryptoHandlerService.get_balance(asset, address)
            blockchain_balance = balance_data["confirmed"]

            # Calculate drift
            drift = blockchain_balance - db_balance
            drift_percent = abs(drift / db_balance) if db_balance > 0 else 0

            # Check if drift exceeds tolerance
            tolerance = max(
                BalanceSyncService.DRIFT_TOLERANCE_MIN_UNITS,
                db_balance * BalanceSyncService.DRIFT_TOLERANCE_PERCENT
            )

            has_drift = abs(drift) > tolerance
            is_critical = drift_percent > BalanceSyncService.CRITICAL_DRIFT_THRESHOLD

            # Update database
            deposits_db = await get_db_collection("exchanger_deposits")
            await deposits_db.update_one(
                {"_id": ObjectId(deposit_id)},
                {
                    "$set": {
                        "balance_units": blockchain_balance,
                        "last_synced": datetime.utcnow(),
                        "last_sync_drift": drift
                    }
                }
            )

            # Record sync
            drift_info = None
            if has_drift:
                drift_info = await BalanceSyncService._record_balance_sync(
                    wallet_type="deposit",
                    wallet_id=deposit_id,
                    user_id=user_id,
                    asset=asset,
                    address=address,
                    db_balance=db_balance,
                    blockchain_balance=blockchain_balance,
                    drift=drift,
                    drift_percent=drift_percent,
                    is_critical=is_critical
                )

                if is_critical:
                    logger.warning(
                        f"CRITICAL DRIFT in deposit wallet {deposit_id}: "
                        f"{asset} {address[:8]}... "
                        f"DB={db_balance} Blockchain={blockchain_balance} "
                        f"Drift={drift} ({drift_percent*100:.2f}%)"
                    )
                else:
                    logger.info(
                        f"Drift detected in deposit wallet {deposit_id}: "
                        f"{asset} drift={drift}"
                    )

            return True, drift_info

        except Exception as e:
            logger.error(
                f"Failed to sync deposit wallet {deposit_id}: {e}",
                exc_info=True
            )
            return False, None

    @staticmethod
    async def _sync_afroo_wallet(
        wallet_id: str,
        user_id: str,
        asset: str,
        address: str,
        db_balance: float
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Sync Afroo wallet with blockchain.

        Args:
            wallet_id: Wallet record ID
            user_id: User ID
            asset: Asset code
            address: Blockchain address
            db_balance: Current database balance

        Returns:
            Tuple of (success, drift_info)
        """
        try:
            # Get blockchain balance
            balance_data = await CryptoHandlerService.get_balance(asset, address)
            blockchain_balance = balance_data["confirmed"]

            # Calculate drift
            drift = blockchain_balance - db_balance
            drift_percent = abs(drift / db_balance) if db_balance > 0 else 0

            # Check if drift exceeds tolerance
            tolerance = max(
                BalanceSyncService.DRIFT_TOLERANCE_MIN_UNITS,
                db_balance * BalanceSyncService.DRIFT_TOLERANCE_PERCENT
            )

            has_drift = abs(drift) > tolerance
            is_critical = drift_percent > BalanceSyncService.CRITICAL_DRIFT_THRESHOLD

            # Update database
            wallets_db = await get_db_collection("afroo_wallets")
            await wallets_db.update_one(
                {"_id": ObjectId(wallet_id)},
                {
                    "$set": {
                        "balance_units": blockchain_balance,
                        "last_synced": datetime.utcnow(),
                        "last_sync_drift": drift
                    }
                }
            )

            # Record sync
            drift_info = None
            if has_drift:
                drift_info = await BalanceSyncService._record_balance_sync(
                    wallet_type="afroo",
                    wallet_id=wallet_id,
                    user_id=user_id,
                    asset=asset,
                    address=address,
                    db_balance=db_balance,
                    blockchain_balance=blockchain_balance,
                    drift=drift,
                    drift_percent=drift_percent,
                    is_critical=is_critical
                )

                if is_critical:
                    logger.warning(
                        f"CRITICAL DRIFT in Afroo wallet {wallet_id}: "
                        f"{asset} {address[:8]}... "
                        f"DB={db_balance} Blockchain={blockchain_balance} "
                        f"Drift={drift} ({drift_percent*100:.2f}%)"
                    )

            return True, drift_info

        except Exception as e:
            logger.error(
                f"Failed to sync Afroo wallet {wallet_id}: {e}",
                exc_info=True
            )
            return False, None

    @staticmethod
    async def _record_balance_sync(
        wallet_type: str,
        wallet_id: str,
        user_id: str,
        asset: str,
        address: str,
        db_balance: float,
        blockchain_balance: float,
        drift: float,
        drift_percent: float,
        is_critical: bool
    ) -> Dict:
        """Record balance sync in database"""
        sync_db = await get_db_collection("balance_sync_records")

        sync_record = {
            "wallet_type": wallet_type,
            "wallet_id": ObjectId(wallet_id),
            "user_id": ObjectId(user_id),
            "asset": asset,
            "address": address,
            "db_balance": db_balance,
            "blockchain_balance": blockchain_balance,
            "drift": drift,
            "drift_percent": drift_percent,
            "is_critical": is_critical,
            "synced_at": datetime.utcnow()
        }

        result = await sync_db.insert_one(sync_record)

        return {
            "has_drift": True,
            "is_critical": is_critical,
            "drift": drift,
            "drift_percent": drift_percent,
            "wallet_type": wallet_type,
            "wallet_id": wallet_id,
            "asset": asset,
            "address": address,
            "db_balance": db_balance,
            "blockchain_balance": blockchain_balance
        }

    @staticmethod
    async def get_sync_history(
        wallet_id: Optional[str] = None,
        user_id: Optional[str] = None,
        asset: Optional[str] = None,
        critical_only: bool = False,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get balance sync history.

        Args:
            wallet_id: Filter by wallet
            user_id: Filter by user
            asset: Filter by asset
            critical_only: Only show critical drifts
            limit: Maximum records

        Returns:
            List of sync records
        """
        sync_db = await get_db_collection("balance_sync_records")

        query = {}
        if wallet_id:
            query["wallet_id"] = ObjectId(wallet_id)
        if user_id:
            query["user_id"] = ObjectId(user_id)
        if asset:
            query["asset"] = asset
        if critical_only:
            query["is_critical"] = True

        cursor = sync_db.find(query).sort("synced_at", -1).limit(limit)
        records = await cursor.to_list(length=limit)

        # Serialize ObjectIds
        for record in records:
            record["_id"] = str(record["_id"])
            record["wallet_id"] = str(record["wallet_id"])
            record["user_id"] = str(record["user_id"])

        return records


# Background sync task (to be called by scheduler)
async def run_periodic_balance_sync():
    """
    Background task that runs periodic balance syncs.
    Should be called by a task scheduler (e.g., APScheduler).
    """
    logger.info("Starting periodic balance sync...")

    # Sync deposit wallets
    deposit_results = await BalanceSyncService.sync_all_deposit_wallets()

    # Sync Afroo wallets
    afroo_results = await BalanceSyncService.sync_all_afroo_wallets()

    # Log summary
    total_synced = deposit_results.get("synced", 0) + afroo_results.get("synced", 0)
    total_drifts = (
        deposit_results.get("drifts_detected", 0) +
        afroo_results.get("drifts_detected", 0)
    )
    total_critical = (
        deposit_results.get("critical_drifts", 0) +
        afroo_results.get("critical_drifts", 0)
    )

    logger.info(
        f"Periodic balance sync complete: {total_synced} wallets synced, "
        f"{total_drifts} drifts detected, {total_critical} critical"
    )

    return {
        "deposit_wallets": deposit_results,
        "afroo_wallets": afroo_results,
        "summary": {
            "total_synced": total_synced,
            "total_drifts": total_drifts,
            "total_critical": total_critical
        }
    }
