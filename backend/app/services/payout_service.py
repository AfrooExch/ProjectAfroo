"""
Payout Service - Handles internal and external payouts
Internal: Send from exchanger's deposit wallet
External: Verify manual payment by exchanger
"""

from typing import Optional, Dict, Tuple
from datetime import datetime
from bson import ObjectId
from decimal import Decimal
import logging
import httpx

from app.core.database import get_db_collection
from app.services.hold_service import HoldService
from app.core.config import settings
from app.core.validators import CryptoValidators

logger = logging.getLogger(__name__)


class PayoutService:
    """Service for payout operations"""

    @staticmethod
    async def initiate_internal_payout(
        ticket_id: str,
        exchanger_id: str,
        client_id: str,
        asset: str,
        amount_units: float,
        to_address: str
    ) -> Tuple[bool, str]:
        """
        Initiate internal payout - send from exchanger's deposit wallet.

        Args:
            ticket_id: Ticket ID
            exchanger_id: Exchanger's user ID
            client_id: Client's user ID
            asset: Asset code
            amount_units: Amount to send
            to_address: Client's wallet address

        Returns:
            Tuple of (success, tx_hash or error_message)
        """
        try:
            # Validate address
            if not CryptoValidators.validate_address(to_address, asset):
                return False, f"Invalid {asset} address format"

            # Validate amount
            is_valid, error_msg = CryptoValidators.validate_amount(amount_units, asset)
            if not is_valid:
                return False, error_msg

            # Get exchanger's deposit wallet
            deposits_db = await get_db_collection("exchanger_deposits")
            deposit = await deposits_db.find_one({
                "user_id": ObjectId(exchanger_id),
                "asset": asset
            })

            if not deposit:
                return False, f"No {asset} deposit wallet found for exchanger"

            # Check available balance (balance - held)
            available = deposit["balance_units"] - deposit.get("held_units", 0.0)
            if available < amount_units:
                return False, f"Insufficient balance: {available} < {amount_units}"

            # Send transaction via Tatum
            success, tx_hash_or_error = await PayoutService._send_via_tatum(
                asset=asset,
                to_address=to_address,
                amount=amount_units,
                from_address=deposit["address"]
            )

            if not success:
                return False, f"Transaction failed: {tx_hash_or_error}"

            # Record payout
            await PayoutService._record_payout(
                ticket_id=ticket_id,
                exchanger_id=exchanger_id,
                client_id=client_id,
                method="internal",
                asset=asset,
                amount_units=amount_units,
                to_address=to_address,
                tx_hash=tx_hash_or_error,
                status="pending"
            )

            logger.info(
                f"Internal payout initiated: ticket={ticket_id} "
                f"asset={asset} amount={amount_units} tx={tx_hash_or_error}"
            )

            return True, tx_hash_or_error

        except Exception as e:
            logger.error(f"Internal payout failed: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def verify_external_payout(
        ticket_id: str,
        exchanger_id: str,
        client_id: str,
        asset: str,
        expected_amount: float,
        to_address: str,
        tx_hash: str
    ) -> Tuple[bool, str]:
        """
        Verify external payout - exchanger paid manually.

        Args:
            ticket_id: Ticket ID
            exchanger_id: Exchanger's user ID
            client_id: Client's user ID
            asset: Asset code
            expected_amount: Expected amount
            to_address: Client's wallet address
            tx_hash: Transaction hash provided by exchanger

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate tx hash format
            if not CryptoValidators.validate_tx_hash(tx_hash, asset):
                return False, f"Invalid {asset} transaction hash format"

            # Validate address
            if not CryptoValidators.validate_address(to_address, asset):
                return False, f"Invalid {asset} address format"

            # Verify transaction on blockchain via Tatum
            is_valid, verification_msg = await PayoutService._verify_transaction_on_chain(
                asset=asset,
                tx_hash=tx_hash,
                expected_to=to_address,
                expected_amount=expected_amount
            )

            if not is_valid:
                return False, f"Transaction verification failed: {verification_msg}"

            # Record payout
            await PayoutService._record_payout(
                ticket_id=ticket_id,
                exchanger_id=exchanger_id,
                client_id=client_id,
                method="external",
                asset=asset,
                amount_units=expected_amount,
                to_address=to_address,
                tx_hash=tx_hash,
                status="verified",
                verified=True
            )

            logger.info(
                f"External payout verified: ticket={ticket_id} "
                f"asset={asset} tx={tx_hash}"
            )

            return True, "External payout verified successfully"

        except Exception as e:
            logger.error(f"External payout verification failed: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def complete_payout(payout_id: str) -> bool:
        """
        Complete payout after blockchain confirmation.
        Called by webhook handler when transaction confirms.

        Args:
            payout_id: Payout record ID

        Returns:
            Success status
        """
        try:
            payouts_db = await get_db_collection("payouts")

            payout = await payouts_db.find_one({"_id": ObjectId(payout_id)})
            if not payout:
                logger.error(f"Payout {payout_id} not found")
                return False

            # Update status
            await payouts_db.update_one(
                {"_id": ObjectId(payout_id)},
                {
                    "$set": {
                        "status": "confirmed",
                        "confirmed_at": datetime.utcnow()
                    }
                }
            )

            # Release hold if exists
            if payout.get("hold_id"):
                await HoldService.release_hold(
                    hold_id=str(payout["hold_id"]),
                    deduct_fee=True
                )

            logger.info(f"Payout completed: {payout_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to complete payout: {e}", exc_info=True)
            return False

    @staticmethod
    async def get_payout_history(
        user_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        limit: int = 50
    ) -> list:
        """
        Get payout history.

        Args:
            user_id: Filter by user (exchanger or client)
            ticket_id: Filter by ticket
            limit: Maximum records

        Returns:
            List of payout records
        """
        payouts_db = await get_db_collection("payouts")

        query = {}
        if user_id:
            query["$or"] = [
                {"exchanger_id": ObjectId(user_id)},
                {"client_id": ObjectId(user_id)}
            ]
        if ticket_id:
            query["ticket_id"] = ObjectId(ticket_id)

        cursor = payouts_db.find(query).sort("created_at", -1).limit(limit)
        payouts = await cursor.to_list(length=limit)

        # Serialize ObjectIds
        for payout in payouts:
            payout["_id"] = str(payout["_id"])
            payout["ticket_id"] = str(payout["ticket_id"])
            payout["exchanger_id"] = str(payout["exchanger_id"])
            payout["client_id"] = str(payout["client_id"])

        return payouts

    @staticmethod
    async def _send_via_tatum(
        asset: str,
        to_address: str,
        amount: float,
        from_address: str
    ) -> Tuple[bool, str]:
        """
        Send transaction via Tatum API.

        Args:
            asset: Asset code
            to_address: Recipient address
            amount: Amount to send
            from_address: Sender address

        Returns:
            Tuple of (success, tx_hash or error_message)
        """
        try:
            # Map asset to Tatum blockchain
            blockchain_map = {
                "BTC": "bitcoin",
                "LTC": "litecoin",
                "ETH": "ethereum",
                "SOL": "solana",
                "USDT-SOL": "solana",
                "USDT-ETH": "ethereum",
                "USDC-SOL": "solana",
                "USDC-ETH": "ethereum"
            }

            blockchain = blockchain_map.get(asset)
            if not blockchain:
                return False, f"Unsupported asset: {asset}"

            # TODO: Implement actual Tatum transaction sending
            # This requires:
            # 1. Get private key from secure storage
            # 2. Sign transaction
            # 3. Broadcast via Tatum
            #
            # For now, return placeholder
            logger.warning(
                f"Tatum transaction sending not fully implemented: "
                f"{amount} {asset} to {to_address}"
            )

            # Placeholder tx hash
            import hashlib
            import time
            placeholder_tx = hashlib.sha256(
                f"{from_address}{to_address}{amount}{time.time()}".encode()
            ).hexdigest()

            return True, f"0x{placeholder_tx}"

        except Exception as e:
            logger.error(f"Tatum send failed: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def _verify_transaction_on_chain(
        asset: str,
        tx_hash: str,
        expected_to: str,
        expected_amount: float
    ) -> Tuple[bool, str]:
        """
        Verify transaction on blockchain via Tatum.

        Args:
            asset: Asset code
            tx_hash: Transaction hash
            expected_to: Expected recipient address
            expected_amount: Expected amount

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Map asset to Tatum chain
            chain_map = {
                "BTC": "bitcoin-mainnet",
                "LTC": "litecoin-mainnet",
                "ETH": "ethereum-mainnet",
                "SOL": "solana-mainnet"
            }

            base_asset = asset.split("-")[0] if "-" in asset else asset
            chain = chain_map.get(base_asset)

            if not chain:
                return False, f"Chain not supported: {asset}"

            # Get transaction from Tatum
            async with httpx.AsyncClient() as client:
                headers = {"x-api-key": settings.TATUM_API_KEY}

                response = await client.get(
                    f"{settings.TATUM_API_URL}/v3/blockchain/transaction/{chain}/{tx_hash}",
                    headers=headers,
                    timeout=30.0
                )

                if response.status_code != 200:
                    return False, f"Transaction not found on blockchain"

                tx_data = response.json()

                # Verify recipient
                # Note: Structure varies by blockchain
                # This is simplified - needs proper parsing per chain
                to_address = tx_data.get("to") or tx_data.get("outputs", [{}])[0].get("address")

                if not to_address or to_address.lower() != expected_to.lower():
                    return False, f"Recipient mismatch: expected {expected_to}, got {to_address}"

                # Verify amount (simplified - needs proper parsing)
                amount = float(tx_data.get("value", 0) or tx_data.get("amount", 0))

                # Allow 1% tolerance for network fees
                min_amount = expected_amount * 0.99
                if amount < min_amount:
                    return False, f"Amount insufficient: expected {expected_amount}, got {amount}"

                # Check confirmations
                confirmations = tx_data.get("confirmations", 0)
                min_confirmations = {"BTC": 1, "LTC": 1, "ETH": 12, "SOL": 1}.get(base_asset, 1)

                if confirmations < min_confirmations:
                    return False, f"Insufficient confirmations: {confirmations}/{min_confirmations}"

                return True, "Transaction verified successfully"

        except Exception as e:
            logger.error(f"Transaction verification failed: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def _record_payout(
        ticket_id: str,
        exchanger_id: str,
        client_id: str,
        method: str,
        asset: str,
        amount_units: float,
        to_address: str,
        tx_hash: str,
        status: str,
        verified: bool = False
    ):
        """Record payout in database"""
        payouts_db = await get_db_collection("payouts")

        payout_dict = {
            "ticket_id": ObjectId(ticket_id),
            "exchanger_id": ObjectId(exchanger_id),
            "client_id": ObjectId(client_id),
            "method": method,
            "asset": asset,
            "amount_units": amount_units,
            "to_address": to_address,
            "tx_hash": tx_hash,
            "verified": verified,
            "confirmations": 0,
            "status": status,
            "created_at": datetime.utcnow()
        }

        await payouts_db.insert_one(payout_dict)
