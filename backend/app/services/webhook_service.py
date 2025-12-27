"""
Webhook Service - Tatum blockchain event handling
Processes incoming blockchain transactions and credits deposits
"""

from typing import Optional, Dict
from datetime import datetime
from bson import ObjectId
import logging
import hmac
import hashlib

from app.core.database import get_db_collection
from app.services.exchanger_deposit_service import ExchangerDepositService
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for processing Tatum webhooks"""

    # Asset mapping from blockchain to our internal format
    ASSET_MAPPING = {
        "bitcoin": "BTC",
        "litecoin": "LTC",
        "solana": "SOL",
        "ethereum": "ETH",
    }

    # Token contract addresses
    TOKEN_CONTRACTS = {
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT-SOL",  # USDT on Solana
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC-SOL",  # USDC on Solana
        "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT-ETH",  # USDT on Ethereum
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC-ETH",  # USDC on Ethereum
    }

    @staticmethod
    def verify_signature(payload: bytes, signature: str) -> bool:
        """Verify webhook signature from Tatum"""
        if not settings.TATUM_WEBHOOK_SECRET:
            logger.warning("No webhook secret configured, skipping verification")
            return True

        expected = hmac.new(
            settings.TATUM_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    @staticmethod
    async def process_incoming_transaction(webhook_data: dict) -> dict:
        """
        Process incoming blockchain transaction.
        Credits exchanger deposit if it's to a platform wallet.
        """
        try:
            # Extract transaction data
            blockchain = webhook_data.get("chain")
            tx_hash = webhook_data.get("txId")
            to_address = webhook_data.get("to")
            amount = float(webhook_data.get("amount", 0))
            confirmations = webhook_data.get("confirmations", 0)
            token_address = webhook_data.get("tokenAddress")

            # Determine asset
            asset = await WebhookService._determine_asset(
                blockchain, token_address
            )

            if not asset:
                logger.warning(f"Unknown asset: blockchain={blockchain} token={token_address}")
                return {"status": "ignored", "reason": "unknown_asset"}

            # Check if this is to a platform wallet
            user_id = await WebhookService._find_deposit_owner(to_address, asset)

            if not user_id:
                logger.info(f"Transaction not to platform wallet: {tx_hash}")
                return {"status": "ignored", "reason": "not_platform_wallet"}

            # Check confirmations
            min_confirmations = WebhookService._get_min_confirmations(asset)
            if confirmations < min_confirmations:
                logger.info(
                    f"Insufficient confirmations: {confirmations}/{min_confirmations}"
                )
                return {
                    "status": "pending",
                    "confirmations": confirmations,
                    "required": min_confirmations
                }

            # Check if already processed
            if await WebhookService._is_transaction_processed(tx_hash):
                logger.info(f"Transaction already processed: {tx_hash}")
                return {"status": "duplicate"}

            # Get USD value
            amount_usd = await WebhookService._get_usd_value(asset, amount)

            # Credit deposit
            result = await ExchangerDepositService.credit_deposit(
                user_id=user_id,
                asset=asset,
                amount_units=amount,
                amount_usd=amount_usd,
                tx_hash=tx_hash
            )

            # Record transaction
            await WebhookService._record_transaction(
                user_id=user_id,
                asset=asset,
                amount_units=amount,
                amount_usd=amount_usd,
                tx_hash=tx_hash,
                from_address=webhook_data.get("from"),
                to_address=to_address,
                confirmations=confirmations
            )

            logger.info(
                f"Deposit credited: user={user_id} asset={asset} "
                f"amount={amount} tx={tx_hash}"
            )

            return {
                "status": "credited",
                "user_id": user_id,
                "asset": asset,
                "amount_units": amount,
                "amount_usd": amount_usd,
                "tx_hash": tx_hash
            }

        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            raise

    @staticmethod
    async def _determine_asset(
        blockchain: str,
        token_address: Optional[str]
    ) -> Optional[str]:
        """Determine asset from blockchain and token address"""
        # Token (USDT/USDC)
        if token_address:
            token_lower = token_address.lower()
            for contract, asset in WebhookService.TOKEN_CONTRACTS.items():
                if contract.lower() == token_lower:
                    return asset

        # Native asset (BTC, LTC, SOL, ETH)
        blockchain_lower = blockchain.lower() if blockchain else ""
        return WebhookService.ASSET_MAPPING.get(blockchain_lower)

    @staticmethod
    async def _find_deposit_owner(address: str, asset: str) -> Optional[str]:
        """Find exchanger who owns this deposit address"""
        deposits_db = await get_db_collection("exchanger_deposits")

        deposit = await deposits_db.find_one({
            "address": address,
            "asset": asset
        })

        return str(deposit["user_id"]) if deposit else None

    @staticmethod
    def _get_min_confirmations(asset: str) -> int:
        """Get minimum confirmations required for asset"""
        confirmations_map = {
            "BTC": 1,
            "LTC": 1,
            "SOL": 1,
            "ETH": 12,
            "USDT-SOL": 1,
            "USDC-SOL": 1,
            "USDT-ETH": 12,
            "USDC-ETH": 12
        }
        return confirmations_map.get(asset, 1)

    @staticmethod
    async def _is_transaction_processed(tx_hash: str) -> bool:
        """Check if transaction already processed"""
        txs_db = await get_db_collection("blockchain_transactions")

        tx = await txs_db.find_one({"tx_hash": tx_hash})
        return tx is not None

    @staticmethod
    async def _get_usd_value(asset: str, amount: float) -> float:
        """Get USD value of amount"""
        # TODO: Integrate with price API
        # For now use fallback rates from config
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
        rate = rates.get(base_asset, 1.0)

        return amount * rate

    @staticmethod
    async def _record_transaction(
        user_id: str,
        asset: str,
        amount_units: float,
        amount_usd: float,
        tx_hash: str,
        from_address: str,
        to_address: str,
        confirmations: int
    ):
        """Record transaction in database"""
        txs_db = await get_db_collection("blockchain_transactions")

        tx_dict = {
            "user_id": ObjectId(user_id),
            "type": "deposit",
            "asset": asset,
            "amount_units": amount_units,
            "amount_usd": amount_usd,
            "tx_hash": tx_hash,
            "from_address": from_address,
            "to_address": to_address,
            "confirmations": confirmations,
            "status": "confirmed",
            "created_at": datetime.utcnow(),
            "confirmed_at": datetime.utcnow()
        }

        await txs_db.insert_one(tx_dict)
