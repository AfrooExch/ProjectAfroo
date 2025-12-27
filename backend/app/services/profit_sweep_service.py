"""
Profit Sweep Service - Automated fee collection
Sweeps accumulated fees from exchange and wallet operations to admin wallets
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from decimal import Decimal
from bson import ObjectId
import logging

from app.core.database import get_db_collection
from app.core.config import settings
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)


class ProfitSweepService:
    """Service for sweeping accumulated fees to admin wallets"""

    # Minimum amounts to sweep (to avoid tiny transactions)
    MIN_SWEEP_AMOUNTS = {
        "BTC": Decimal("0.00004"),     # ~$4
        "LTC": Decimal("0.005"),       # ~$0.50
        "ETH": Decimal("0.0003"),      # ~$1
        "SOL": Decimal("0.005"),       # ~$0.50
        "USDC-SOL": Decimal("0.5"),    # $0.50
        "USDC-ETH": Decimal("0.5"),    # $0.50
        "USDT-SOL": Decimal("0.5"),    # $0.50
        "USDT-ETH": Decimal("0.5"),    # $0.50
        "XRP": Decimal("2.0"),         # ~$2
        "BNB": Decimal("0.002"),       # ~$1
        "TRX": Decimal("10.0"),        # ~$2
        "MATIC": Decimal("2.0"),       # ~$2
        "AVAX": Decimal("0.02"),       # ~$1
        "DOGE": Decimal("10.0"),       # ~$2
    }

    @staticmethod
    async def sweep_all_fees(
        sweep_type: str = "all",
        force: bool = False,
        dry_run: bool = False
    ) -> Dict:
        """
        Sweep all accumulated fees to admin wallets.

        Args:
            sweep_type: "exchange", "wallet", or "all"
            force: Skip minimum amount checks
            dry_run: Preview without executing

        Returns:
            Summary of sweep operations
        """
        results = {
            "sweep_type": sweep_type,
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "force": force,
            "exchange_fees": {},
            "wallet_fees": {},
            "total_swept_usd": 0.0,
            "errors": []
        }

        try:
            # Sweep exchange fees (from exchanger_deposits admin balances)
            if sweep_type in ["exchange", "all"]:
                exchange_results = await ProfitSweepService._sweep_exchange_fees(
                    force=force,
                    dry_run=dry_run
                )
                results["exchange_fees"] = exchange_results

            # Sweep wallet fees (from profit_holds)
            if sweep_type in ["wallet", "all"]:
                wallet_results = await ProfitSweepService._sweep_wallet_fees(
                    force=force,
                    dry_run=dry_run
                )
                results["wallet_fees"] = wallet_results

            # Calculate total USD swept
            total_usd = 0.0
            for currency_data in results["exchange_fees"].values():
                total_usd += currency_data.get("amount_usd", 0.0)
            for currency_data in results["wallet_fees"].values():
                total_usd += currency_data.get("amount_usd", 0.0)
            results["total_swept_usd"] = total_usd

            logger.info(
                f"Profit sweep completed: type={sweep_type} dry_run={dry_run} "
                f"total_usd=${total_usd:.2f}"
            )

        except Exception as e:
            logger.error(f"Error during profit sweep: {e}", exc_info=True)
            results["errors"].append(str(e))

        return results

    @staticmethod
    async def _sweep_exchange_fees(
        force: bool = False,
        dry_run: bool = False
    ) -> Dict:
        """
        Sweep exchange fees from ALL exchanger deposits with fee_reserved > 0.

        Steps:
        1. Query all exchanger_deposits where fee_reserved > 0
        2. For each exchanger/currency with fee_reserved > minimum:
           - Send fee amount from EXCHANGER'S wallet to admin wallet
           - Update exchanger's balance and fee_reserved
           - Record sweep transaction
        """
        deposits_db = await get_db_collection("exchanger_deposits")
        sweep_records_db = await get_db_collection("profit_sweeps")

        results = {}

        try:
            # Find all exchanger deposits with fees reserved (exclude admin's own accounting records)
            all_deposits = await deposits_db.find({
                "fee_reserved": {"$ne": "0"},
                "user_id": {"$ne": "admin"}  # Exclude admin's accounting records
            }).to_list(length=1000)

            logger.info(f"Found {len(all_deposits)} exchanger deposits with reserved fees")

            # Group by currency to aggregate totals
            currency_sweeps = {}

            for deposit in all_deposits:
                user_id = deposit.get("user_id")
                currency = deposit.get("currency")

                if not currency or not user_id:
                    continue

                fee_reserved = Decimal(str(deposit.get("fee_reserved", "0")))

                if fee_reserved <= 0:
                    continue

                # Add to currency totals
                if currency not in currency_sweeps:
                    currency_sweeps[currency] = {
                        "total_fee_reserved": Decimal("0"),
                        "exchangers": []
                    }

                currency_sweeps[currency]["total_fee_reserved"] += fee_reserved
                currency_sweeps[currency]["exchangers"].append({
                    "user_id": user_id,
                    "fee_reserved": fee_reserved,
                    "deposit": deposit
                })

            # Process each currency
            for currency, sweep_data in currency_sweeps.items():
                total_fee_reserved = sweep_data["total_fee_reserved"]
                exchangers = sweep_data["exchangers"]

                # Check minimum amount (total across all exchangers)
                min_amount = ProfitSweepService.MIN_SWEEP_AMOUNTS.get(currency, Decimal("0"))
                if not force and total_fee_reserved < min_amount:
                    results[currency] = {
                        "status": "skipped",
                        "reason": "below_minimum",
                        "available": float(total_fee_reserved),
                        "minimum": float(min_amount),
                        "exchanger_count": len(exchangers),
                        "amount_usd": 0.0
                    }
                    logger.debug(
                        f"Skipping {currency} sweep: {total_fee_reserved} < {min_amount} "
                        f"({len(exchangers)} exchangers)"
                    )
                    continue

                # Get admin wallet address
                try:
                    admin_address = settings.get_admin_wallet(currency)
                except ValueError as e:
                    results[currency] = {
                        "status": "error",
                        "reason": "no_admin_wallet",
                        "error": str(e),
                        "exchanger_count": len(exchangers),
                        "amount_usd": 0.0
                    }
                    logger.warning(f"No admin wallet configured for {currency}")
                    continue

                # Calculate USD value
                from app.services.price_service import PriceService
                price_usd = await PriceService.get_price_usd(currency)
                amount_usd = float(total_fee_reserved * price_usd) if price_usd else 0.0

                if dry_run:
                    results[currency] = {
                        "status": "dry_run",
                        "amount_crypto": float(total_fee_reserved),
                        "amount_usd": amount_usd,
                        "destination": admin_address,
                        "exchanger_count": len(exchangers),
                        "source": "exchanger_deposits"
                    }
                    logger.info(
                        f"[DRY RUN] Would sweep {currency}: {total_fee_reserved} (${amount_usd:.2f}) "
                        f"from {len(exchangers)} exchangers to {admin_address}"
                    )
                    continue

                # Execute sweep - send from each exchanger's wallet
                swept_count = 0
                swept_total = Decimal("0")
                sweep_tx_hashes = []
                errors = []

                for exchanger_data in exchangers:
                    exchanger_user_id = exchanger_data["user_id"]
                    fee_amount = exchanger_data["fee_reserved"]
                    deposit_doc = exchanger_data["deposit"]

                    try:
                        # Get encrypted private key
                        from app.core.encryption import get_encryption_service
                        encryption = get_encryption_service()
                        encrypted_key = deposit_doc.get("encrypted_private_key")

                        if not encrypted_key:
                            errors.append(f"{exchanger_user_id}: No private key")
                            continue

                        private_key = encryption.decrypt_private_key(encrypted_key)
                        wallet_address = deposit_doc.get("wallet_address")

                        # Send fee from exchanger's wallet to admin wallet
                        from app.services.tatum_service import TatumService
                        tatum_service = TatumService()

                        logger.info(
                            f"Sweeping {currency} fee from exchanger {exchanger_user_id}: "
                            f"{fee_amount} → {admin_address}"
                        )

                        success, message, tx_hash = await tatum_service.send_transaction(
                            currency,
                            wallet_address,
                            private_key,
                            admin_address,
                            float(fee_amount)
                        )

                        if success:
                            # Update exchanger's deposit: deduct from balance and fee_reserved
                            balance = Decimal(str(deposit_doc.get("balance", "0")))
                            new_balance = balance - fee_amount

                            await deposits_db.update_one(
                                {"_id": deposit_doc["_id"]},
                                {
                                    "$set": {
                                        "balance": str(new_balance),
                                        "fee_reserved": "0",  # Reset to 0
                                        "last_synced": datetime.utcnow()
                                    }
                                }
                            )

                            swept_count += 1
                            swept_total += fee_amount
                            sweep_tx_hashes.append(tx_hash)

                            logger.info(
                                f"Swept {fee_amount} {currency} from exchanger {exchanger_user_id} "
                                f"tx={tx_hash}"
                            )
                        else:
                            errors.append(f"{exchanger_user_id}: {message}")
                            logger.error(f"Failed to sweep from {exchanger_user_id}: {message}")

                    except Exception as e:
                        errors.append(f"{exchanger_user_id}: {str(e)}")
                        logger.error(
                            f"Error sweeping from exchanger {exchanger_user_id}: {e}",
                            exc_info=True
                        )

                # Record sweep transaction
                if swept_count > 0:
                    sweep_record = {
                        "sweep_type": "exchange_fees",
                        "currency": currency,
                        "amount_crypto": str(swept_total),
                        "amount_usd": float(swept_total * price_usd) if price_usd else 0.0,
                        "destination_address": admin_address,
                        "tx_hashes": sweep_tx_hashes,
                        "exchanger_count": swept_count,
                        "status": "completed",
                        "swept_at": datetime.utcnow(),
                        "created_at": datetime.utcnow(),
                        "errors": errors if errors else None
                    }
                    await sweep_records_db.insert_one(sweep_record)

                results[currency] = {
                    "status": "success" if swept_count > 0 else "failed",
                    "amount_crypto": float(swept_total),
                    "amount_usd": float(swept_total * price_usd) if price_usd else 0.0,
                    "tx_hashes": sweep_tx_hashes,
                    "destination": admin_address,
                    "exchanger_count": swept_count,
                    "total_exchangers": len(exchangers),
                    "source": "exchanger_deposits",
                    "errors": errors if errors else None
                }

                logger.info(
                    f"Exchange fee sweep for {currency}: {swept_total} (${amount_usd:.2f}) "
                    f"from {swept_count}/{len(exchangers)} exchangers"
                )

        except Exception as e:
            logger.error(f"Error in _sweep_exchange_fees: {e}", exc_info=True)
            raise

        return results

    @staticmethod
    async def _sweep_wallet_fees(
        force: bool = False,
        dry_run: bool = False
    ) -> Dict:
        """
        Sweep wallet fees from profit_holds collection.

        Steps:
        1. Query profit_holds with status="held"
        2. Group by currency
        3. For each currency with total > minimum:
           - Send aggregated funds to admin wallet
           - Record sweep transaction
           - Mark profit_holds as "swept"
        """
        profit_holds_db = await get_db_collection("profit_holds")
        sweep_records_db = await get_db_collection("profit_sweeps")

        results = {}

        try:
            # Get all held profit holds
            held_holds = await profit_holds_db.find({
                "status": "held"
            }).to_list(length=1000)

            logger.info(f"Found {len(held_holds)} held profit holds")

            # Group by currency
            currency_totals = {}
            currency_holds = {}

            for hold in held_holds:
                currency = hold.get("currency")
                amount_str = hold.get("amount", "0")
                amount = Decimal(amount_str)

                if currency not in currency_totals:
                    currency_totals[currency] = Decimal("0")
                    currency_holds[currency] = []

                currency_totals[currency] += amount
                currency_holds[currency].append(hold)

            logger.info(f"Grouped profit holds into {len(currency_totals)} currencies")

            # Sweep each currency
            for currency, total_amount in currency_totals.items():
                if total_amount <= 0:
                    continue

                # Check minimum amount
                min_amount = ProfitSweepService.MIN_SWEEP_AMOUNTS.get(currency, Decimal("0"))
                if not force and total_amount < min_amount:
                    results[currency] = {
                        "status": "skipped",
                        "reason": "below_minimum",
                        "available": float(total_amount),
                        "minimum": float(min_amount),
                        "hold_count": len(currency_holds[currency]),
                        "amount_usd": 0.0
                    }
                    logger.debug(
                        f"Skipping {currency} wallet fee sweep: {total_amount} < {min_amount}"
                    )
                    continue

                # Get admin wallet address
                try:
                    admin_address = settings.get_admin_wallet(currency)
                except ValueError as e:
                    results[currency] = {
                        "status": "error",
                        "reason": "no_admin_wallet",
                        "error": str(e),
                        "hold_count": len(currency_holds[currency]),
                        "amount_usd": 0.0
                    }
                    logger.warning(f"No admin wallet configured for {currency}")
                    continue

                # Calculate USD value
                from app.services.price_service import PriceService
                price_usd = await PriceService.get_price_usd(currency)
                amount_usd = float(total_amount * price_usd) if price_usd else 0.0

                if dry_run:
                    results[currency] = {
                        "status": "dry_run",
                        "amount_crypto": float(total_amount),
                        "amount_usd": amount_usd,
                        "destination": admin_address,
                        "hold_count": len(currency_holds[currency]),
                        "source": "profit_holds"
                    }
                    logger.info(
                        f"[DRY RUN] Would sweep {currency} wallet fees: {total_amount} "
                        f"(${amount_usd:.2f}) from {len(currency_holds[currency])} holds "
                        f"to {admin_address}"
                    )
                    continue

                # Execute sweep
                try:
                    logger.info(
                        f"Sweeping {currency} wallet fees: {total_amount} (${amount_usd:.2f}) "
                        f"from {len(currency_holds[currency])} holds to {admin_address}"
                    )

                    # Note: Wallet fees in profit_holds are already extracted from user wallets
                    # They just need to be aggregated and sent to admin
                    # We'll use internal transfer since funds are in system wallet

                    # Send transaction
                    tx_result = await WalletService._send_crypto(
                        currency=currency,
                        to_address=admin_address,
                        amount=total_amount,
                        user_id="system",  # System wallet holds profit fees
                        memo=None
                    )

                    if tx_result["success"]:
                        tx_hash = tx_result.get("tx_hash", "")

                        # Mark all profit_holds as swept
                        hold_ids = [hold["_id"] for hold in currency_holds[currency]]
                        await profit_holds_db.update_many(
                            {"_id": {"$in": hold_ids}},
                            {
                                "$set": {
                                    "status": "swept",
                                    "swept_at": datetime.utcnow(),
                                    "sweep_tx_hash": tx_hash
                                }
                            }
                        )

                        # Record sweep transaction
                        sweep_record = {
                            "sweep_type": "wallet_fees",
                            "currency": currency,
                            "amount_crypto": str(total_amount),
                            "amount_usd": amount_usd,
                            "destination_address": admin_address,
                            "tx_hash": tx_hash,
                            "hold_count": len(currency_holds[currency]),
                            "hold_ids": [str(h["_id"]) for h in currency_holds[currency]],
                            "status": "completed",
                            "swept_at": datetime.utcnow(),
                            "created_at": datetime.utcnow()
                        }
                        await sweep_records_db.insert_one(sweep_record)

                        results[currency] = {
                            "status": "success",
                            "amount_crypto": float(total_amount),
                            "amount_usd": amount_usd,
                            "tx_hash": tx_hash,
                            "destination": admin_address,
                            "hold_count": len(currency_holds[currency]),
                            "source": "profit_holds"
                        }

                        logger.info(
                            f"Swept {currency} wallet fees: {total_amount} (${amount_usd:.2f}) "
                            f"from {len(currency_holds[currency])} holds tx={tx_hash}"
                        )

                    else:
                        error_msg = tx_result.get("message", "Unknown error")
                        results[currency] = {
                            "status": "failed",
                            "reason": "send_failed",
                            "error": error_msg,
                            "hold_count": len(currency_holds[currency]),
                            "amount_usd": 0.0
                        }
                        logger.error(
                            f"Failed to sweep {currency} wallet fees: {error_msg}"
                        )

                except Exception as send_error:
                    results[currency] = {
                        "status": "error",
                        "reason": "exception",
                        "error": str(send_error),
                        "hold_count": len(currency_holds[currency]),
                        "amount_usd": 0.0
                    }
                    logger.error(
                        f"Error sweeping {currency} wallet fees: {send_error}",
                        exc_info=True
                    )

        except Exception as e:
            logger.error(f"Error in _sweep_wallet_fees: {e}", exc_info=True)
            raise

        return results

    @staticmethod
    async def get_pending_profits() -> Dict:
        """
        Get summary of profits pending collection.

        Returns:
            Summary by currency and source (exchange/wallet)
        """
        deposits_db = await get_db_collection("exchanger_deposits")
        profit_holds_db = await get_db_collection("profit_holds")

        summary = {
            "exchange_fees": {},
            "wallet_fees": {},
            "total_usd": 0.0,
            "by_currency": {}
        }

        try:
            # Get exchange fees from admin deposits
            admin_deposits = await deposits_db.find({
                "user_id": "admin"
            }).to_list(length=100)

            for deposit in admin_deposits:
                currency = deposit.get("currency")
                balance = Decimal(str(deposit.get("balance", "0")))
                held = Decimal(str(deposit.get("held", "0")))
                fee_reserved = Decimal(str(deposit.get("fee_reserved", "0")))
                available = balance - held - fee_reserved

                if available > 0:
                    from app.services.price_service import PriceService
                    price_usd = await PriceService.get_price_usd(currency)
                    amount_usd = float(available * price_usd) if price_usd else 0.0

                    summary["exchange_fees"][currency] = {
                        "amount_crypto": float(available),
                        "amount_usd": amount_usd
                    }
                    summary["total_usd"] += amount_usd

                    if currency not in summary["by_currency"]:
                        summary["by_currency"][currency] = {
                            "exchange": 0.0,
                            "wallet": 0.0,
                            "total": 0.0
                        }
                    summary["by_currency"][currency]["exchange"] = float(available)
                    summary["by_currency"][currency]["total"] += float(available)

            # Get wallet fees from profit_holds
            held_holds = await profit_holds_db.find({
                "status": "held"
            }).to_list(length=1000)

            currency_totals = {}
            for hold in held_holds:
                currency = hold.get("currency")
                amount = Decimal(hold.get("amount", "0"))

                if currency not in currency_totals:
                    currency_totals[currency] = Decimal("0")
                currency_totals[currency] += amount

            for currency, total in currency_totals.items():
                if total > 0:
                    from app.services.price_service import PriceService
                    price_usd = await PriceService.get_price_usd(currency)
                    amount_usd = float(total * price_usd) if price_usd else 0.0

                    summary["wallet_fees"][currency] = {
                        "amount_crypto": float(total),
                        "amount_usd": amount_usd
                    }
                    summary["total_usd"] += amount_usd

                    if currency not in summary["by_currency"]:
                        summary["by_currency"][currency] = {
                            "exchange": 0.0,
                            "wallet": 0.0,
                            "total": 0.0
                        }
                    summary["by_currency"][currency]["wallet"] = float(total)
                    summary["by_currency"][currency]["total"] += float(total)

        except Exception as e:
            logger.error(f"Error getting pending profits: {e}", exc_info=True)

        return summary

    @staticmethod
    async def get_sweep_history(limit: int = 50) -> List[Dict]:
        """
        Get recent sweep transaction history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of sweep records
        """
        sweep_records_db = await get_db_collection("profit_sweeps")

        try:
            records = await sweep_records_db.find().sort(
                "created_at", -1
            ).limit(limit).to_list(length=limit)

            # Convert ObjectId to string
            for record in records:
                record["_id"] = str(record["_id"])
                if "swept_at" in record:
                    record["swept_at"] = record["swept_at"].isoformat()
                if "created_at" in record:
                    record["created_at"] = record["created_at"].isoformat()

            return records

        except Exception as e:
            logger.error(f"Error getting sweep history: {e}", exc_info=True)
            return []
