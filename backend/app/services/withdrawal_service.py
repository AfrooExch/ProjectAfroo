"""
Withdrawal Service - Automated withdrawals from Afroo Wallets
Handles sending crypto from custodial wallets to external addresses via Tatum
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
from decimal import Decimal
import logging

from app.core.database import get_db_collection
from app.core.validators import CryptoValidators
from app.services.afroo_wallet_service import AfrooWalletService
from app.services.crypto_handler_service import CryptoHandlerService
from app.services.fee_collection_service import FeeCollectionService

logger = logging.getLogger(__name__)


class WithdrawalService:
    """Service for automated crypto withdrawals"""

    # Withdrawal fee structure (can be configured per asset)
    WITHDRAWAL_FEE_STRUCTURE = {
        "BTC": {"type": "fixed", "amount": 0.0001},
        "ETH": {"type": "fixed", "amount": 0.001},
        "LTC": {"type": "fixed", "amount": 0.001},
        "SOL": {"type": "fixed", "amount": 0.01},
        "USDT-SOL": {"type": "fixed", "amount": 0.5},
        "USDT-ETH": {"type": "fixed", "amount": 1.0},
        "USDC-SOL": {"type": "fixed", "amount": 0.5},
        "USDC-ETH": {"type": "fixed", "amount": 1.0}
    }

    # Minimum withdrawal amounts
    MIN_WITHDRAWAL_AMOUNTS = {
        "BTC": 0.0001,
        "ETH": 0.001,
        "LTC": 0.01,
        "SOL": 0.1,
        "USDT-SOL": 5.0,
        "USDT-ETH": 10.0,
        "USDC-SOL": 5.0,
        "USDC-ETH": 10.0
    }

    @staticmethod
    async def calculate_withdrawal_fee(asset: str, amount: float) -> Dict:
        """
        Calculate withdrawal fee for asset.

        Args:
            asset: Asset code
            amount: Withdrawal amount

        Returns:
            Dict with fee breakdown
        """
        fee_config = WithdrawalService.WITHDRAWAL_FEE_STRUCTURE.get(
            asset,
            {"type": "percentage", "rate": 0.001}  # Default 0.1%
        )

        if fee_config["type"] == "fixed":
            network_fee = fee_config["amount"]
            platform_fee = amount * 0.001  # 0.1% platform fee
        else:
            rate = fee_config.get("rate", 0.001)
            network_fee = amount * rate
            platform_fee = amount * 0.001

        total_fee = network_fee + platform_fee
        total_deducted = amount + total_fee
        net_amount = amount  # Amount user actually receives

        return {
            "asset": asset,
            "withdrawal_amount": amount,
            "network_fee": network_fee,
            "platform_fee": platform_fee,
            "total_fee": total_fee,
            "total_deducted": total_deducted,
            "net_amount": net_amount
        }

    @staticmethod
    async def initiate_withdrawal(
        user_id: str,
        asset: str,
        amount: float,
        to_address: str,
        memo: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Initiate automated withdrawal from Afroo wallet.

        Args:
            user_id: User ID
            asset: Asset code
            amount: Amount to withdraw
            to_address: External destination address
            memo: Optional memo/tag for currencies that need it

        Returns:
            Tuple of (success, message, withdrawal_data)
        """
        try:
            # Validate address
            if not CryptoValidators.validate_address(to_address, asset):
                return False, f"Invalid {asset} address format", None

            # Check minimum withdrawal
            min_amount = WithdrawalService.MIN_WITHDRAWAL_AMOUNTS.get(asset, 0.0001)
            if amount < min_amount:
                return False, f"Amount below minimum: {amount} < {min_amount} {asset}", None

            # Validate amount
            is_valid, error_msg = CryptoValidators.validate_amount(amount, asset)
            if not is_valid:
                return False, error_msg, None

            # Calculate fees
            fee_info = await WithdrawalService.calculate_withdrawal_fee(asset, amount)

            # Check user balance
            balance_info = await AfrooWalletService.get_balance(user_id, asset)
            if balance_info["available_balance"] < fee_info["total_deducted"]:
                return False, (
                    f"Insufficient balance: need {fee_info['total_deducted']}, "
                    f"have {balance_info['available_balance']}"
                ), None

            # Get user's Afroo wallet
            wallet = await AfrooWalletService.get_or_create_wallet(user_id, asset)

            # Create withdrawal record
            withdrawals_db = await get_db_collection("withdrawals")

            withdrawal_dict = {
                "user_id": ObjectId(user_id),
                "wallet_id": ObjectId(wallet["wallet_id"]),
                "asset": asset,
                "amount": amount,
                "network_fee": fee_info["network_fee"],
                "platform_fee": fee_info["platform_fee"],
                "total_fee": fee_info["total_fee"],
                "total_deducted": fee_info["total_deducted"],
                "from_address": wallet["address"],
                "to_address": to_address,
                "memo": memo,
                "status": "pending",  # pending → processing → completed/failed
                "created_at": datetime.utcnow()
            }

            result = await withdrawals_db.insert_one(withdrawal_dict)
            withdrawal_id = str(result.inserted_id)

            try:
                # Debit user's Afroo wallet
                await AfrooWalletService.debit(
                    user_id=user_id,
                    asset=asset,
                    amount=fee_info["total_deducted"],
                    destination="withdrawal",
                    reference_id=withdrawal_id
                )

                # Send transaction via Tatum
                # Get wallet's encrypted private key
                wallets_db = await get_db_collection("afroo_wallets")
                wallet_doc = await wallets_db.find_one({"_id": ObjectId(wallet["wallet_id"])})

                if not wallet_doc or not wallet_doc.get("encrypted_private_key"):
                    raise ValueError("Wallet private key not found")

                # Send blockchain transaction
                success, tx_hash_or_error = await CryptoHandlerService.send_transaction(
                    asset=asset,
                    from_address=wallet["address"],
                    to_address=to_address,
                    amount=amount,
                    encrypted_private_key=wallet_doc["encrypted_private_key"]
                )

                if not success:
                    # Transaction failed - refund user
                    await AfrooWalletService.credit(
                        user_id=user_id,
                        asset=asset,
                        amount=fee_info["total_deducted"],
                        source="withdrawal_refund",
                        reference_id=withdrawal_id
                    )

                    await withdrawals_db.update_one(
                        {"_id": ObjectId(withdrawal_id)},
                        {
                            "$set": {
                                "status": "failed",
                                "error": tx_hash_or_error,
                                "failed_at": datetime.utcnow()
                            }
                        }
                    )

                    return False, f"Transaction failed: {tx_hash_or_error}", None

                # Transaction sent successfully
                tx_hash = tx_hash_or_error

                # Collect platform fee (network fee goes to blockchain)
                platform_fee_usd = fee_info["platform_fee"] * await WithdrawalService._get_usd_price(asset)
                await FeeCollectionService.collect_fee(
                    transaction_type="withdrawal",
                    transaction_id=withdrawal_id,
                    user_id=user_id,
                    asset=asset,
                    amount_units=fee_info["platform_fee"],
                    amount_usd=platform_fee_usd
                )

                # Update withdrawal record
                await withdrawals_db.update_one(
                    {"_id": ObjectId(withdrawal_id)},
                    {
                        "$set": {
                            "tx_hash": tx_hash,
                            "status": "processing",
                            "sent_at": datetime.utcnow()
                        }
                    }
                )

                logger.info(
                    f"Withdrawal initiated: {withdrawal_id} - {amount} {asset} "
                    f"to {to_address[:8]}... tx={tx_hash}"
                )

                return True, "Withdrawal initiated successfully", {
                    "withdrawal_id": withdrawal_id,
                    "tx_hash": tx_hash,
                    "amount": amount,
                    "asset": asset,
                    "to_address": to_address,
                    "network_fee": fee_info["network_fee"],
                    "platform_fee": fee_info["platform_fee"],
                    "total_fee": fee_info["total_fee"],
                    "status": "processing"
                }

            except Exception as e:
                # Mark withdrawal as failed
                await withdrawals_db.update_one(
                    {"_id": ObjectId(withdrawal_id)},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "failed_at": datetime.utcnow()
                        }
                    }
                )

                logger.error(f"Withdrawal {withdrawal_id} failed: {e}", exc_info=True)
                return False, str(e), None

        except Exception as e:
            logger.error(f"Failed to initiate withdrawal: {e}", exc_info=True)
            return False, str(e), None

    @staticmethod
    async def update_withdrawal_status(withdrawal_id: str) -> bool:
        """
        Update withdrawal status by checking blockchain confirmation.
        Called by webhook handler or periodic checker.

        Args:
            withdrawal_id: Withdrawal record ID

        Returns:
            Success status
        """
        try:
            withdrawals_db = await get_db_collection("withdrawals")

            withdrawal = await withdrawals_db.find_one({"_id": ObjectId(withdrawal_id)})
            if not withdrawal:
                logger.error(f"Withdrawal {withdrawal_id} not found")
                return False

            if withdrawal["status"] not in ["processing"]:
                return True  # Already completed or failed

            tx_hash = withdrawal.get("tx_hash")
            if not tx_hash:
                logger.warning(f"Withdrawal {withdrawal_id} has no tx_hash")
                return False

            # Get transaction details from blockchain
            tx_data = await CryptoHandlerService.get_transaction(
                asset=withdrawal["asset"],
                tx_hash=tx_hash
            )

            if not tx_data:
                logger.warning(f"Transaction {tx_hash} not found on blockchain yet")
                return False

            # Check confirmations
            confirmations = tx_data.get("confirmations", 0)
            min_confirmations = {
                "BTC": 2,
                "LTC": 2,
                "ETH": 12,
                "SOL": 1
            }.get(withdrawal["asset"], 1)

            if confirmations >= min_confirmations:
                # Update to completed
                await withdrawals_db.update_one(
                    {"_id": ObjectId(withdrawal_id)},
                    {
                        "$set": {
                            "status": "completed",
                            "confirmations": confirmations,
                            "completed_at": datetime.utcnow()
                        }
                    }
                )

                logger.info(
                    f"Withdrawal completed: {withdrawal_id} - "
                    f"{confirmations} confirmations"
                )

                return True

            else:
                # Update confirmations count
                await withdrawals_db.update_one(
                    {"_id": ObjectId(withdrawal_id)},
                    {
                        "$set": {
                            "confirmations": confirmations,
                            "last_checked": datetime.utcnow()
                        }
                    }
                )

                return True

        except Exception as e:
            logger.error(f"Failed to update withdrawal status: {e}", exc_info=True)
            return False

    @staticmethod
    async def cancel_withdrawal(withdrawal_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Cancel pending withdrawal (before blockchain send).

        Args:
            withdrawal_id: Withdrawal ID
            user_id: User ID (for authorization)

        Returns:
            Tuple of (success, message)
        """
        try:
            withdrawals_db = await get_db_collection("withdrawals")

            withdrawal = await withdrawals_db.find_one({"_id": ObjectId(withdrawal_id)})
            if not withdrawal:
                return False, "Withdrawal not found"

            # Check ownership
            if str(withdrawal["user_id"]) != user_id:
                return False, "Not authorized"

            # Can only cancel pending withdrawals
            if withdrawal["status"] != "pending":
                return False, f"Cannot cancel {withdrawal['status']} withdrawal"

            # Refund user
            await AfrooWalletService.credit(
                user_id=user_id,
                asset=withdrawal["asset"],
                amount=withdrawal["total_deducted"],
                source="withdrawal_cancel",
                reference_id=withdrawal_id
            )

            # Update status
            await withdrawals_db.update_one(
                {"_id": ObjectId(withdrawal_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Withdrawal cancelled: {withdrawal_id}")
            return True, "Withdrawal cancelled successfully"

        except Exception as e:
            logger.error(f"Failed to cancel withdrawal: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def get_withdrawal_history(
        user_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get user withdrawal history.

        Args:
            user_id: User ID
            limit: Maximum records

        Returns:
            List of withdrawal records
        """
        withdrawals_db = await get_db_collection("withdrawals")

        cursor = withdrawals_db.find({
            "user_id": ObjectId(user_id)
        }).sort("created_at", -1).limit(limit)

        withdrawals = await cursor.to_list(length=limit)

        # Serialize ObjectIds
        for withdrawal in withdrawals:
            withdrawal["_id"] = str(withdrawal["_id"])
            withdrawal["user_id"] = str(withdrawal["user_id"])
            withdrawal["wallet_id"] = str(withdrawal["wallet_id"])

        return withdrawals

    @staticmethod
    async def get_withdrawal_details(withdrawal_id: str) -> Optional[Dict]:
        """
        Get detailed withdrawal information.

        Args:
            withdrawal_id: Withdrawal ID

        Returns:
            Withdrawal details or None
        """
        withdrawals_db = await get_db_collection("withdrawals")

        withdrawal = await withdrawals_db.find_one({"_id": ObjectId(withdrawal_id)})
        if not withdrawal:
            return None

        withdrawal["_id"] = str(withdrawal["_id"])
        withdrawal["user_id"] = str(withdrawal["user_id"])
        withdrawal["wallet_id"] = str(withdrawal["wallet_id"])

        return withdrawal

    @staticmethod
    async def _get_usd_price(asset: str) -> float:
        """
        Get USD price for asset.
        TODO: Integrate with real price API.
        """
        rates = {
            "BTC": 100000.0,
            "ETH": 3500.0,
            "LTC": 120.0,
            "SOL": 218.0,
            "USDT-SOL": 1.0,
            "USDC-SOL": 1.0,
            "USDT-ETH": 1.0,
            "USDC-ETH": 1.0
        }

        base_asset = asset.split("-")[0] if "-" in asset else asset
        return rates.get(base_asset, 1.0)


# Background task to update pending withdrawal statuses
async def update_pending_withdrawals():
    """
    Update status for all processing withdrawals.
    Should be called periodically by background task scheduler.
    """
    try:
        withdrawals_db = await get_db_collection("withdrawals")

        # Get all processing withdrawals
        cursor = withdrawals_db.find({"status": "processing"})
        withdrawals = await cursor.to_list(length=1000)

        updated_count = 0
        for withdrawal in withdrawals:
            success = await WithdrawalService.update_withdrawal_status(str(withdrawal["_id"]))
            if success:
                updated_count += 1

        logger.info(f"Updated {updated_count}/{len(withdrawals)} pending withdrawals")

        return {"checked": len(withdrawals), "updated": updated_count}

    except Exception as e:
        logger.error(f"Failed to update pending withdrawals: {e}", exc_info=True)
        return {"error": str(e)}
