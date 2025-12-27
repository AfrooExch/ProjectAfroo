"""
ChangeNow Service - External swap provider integration
Integrates with ChangeNow API v2 for crypto-to-crypto exchanges
Documentation: https://documenter.getpostman.com/view/8180765/SVfTPnbB
"""

from typing import Optional, Dict, Tuple
from datetime import datetime
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChangeNowService:
    """Service for ChangeNow API integration"""

    API_URL = "https://api.changenow.io/v2"

    # No static asset map needed - we parse dynamically from CODE-NETWORK format

    @staticmethod
    async def get_available_currencies() -> list:
        """
        Get list of available currencies from ChangeNow.

        Returns:
            List of currency objects
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{ChangeNowService.API_URL}/exchange/currencies",
                    params={"active": True},
                    timeout=15.0
                )

                if response.status_code == 200:
                    return response.json()

                logger.error(f"ChangeNow currencies fetch failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Failed to fetch ChangeNow currencies: {e}")
            return []

    @staticmethod
    async def get_exchange_range(
        from_currency: str,
        to_currency: str
    ) -> Optional[Dict]:
        """
        Get min/max exchange amounts for currency pair.

        Args:
            from_currency: Source currency code (e.g., "BTC", "USDT-ETH")
            to_currency: Destination currency code

        Returns:
            Dict with minAmount and maxAmount or None
        """
        try:
            from_ticker, from_network = ChangeNowService._parse_asset_code(from_currency)
            to_ticker, to_network = ChangeNowService._parse_asset_code(to_currency)

            params = {
                "fromCurrency": from_ticker,
                "toCurrency": to_ticker,
                "flow": "standard"
            }

            # Only add network params if they exist
            if from_network:
                params["fromNetwork"] = from_network
            if to_network:
                params["toNetwork"] = to_network

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{ChangeNowService.API_URL}/exchange/range",
                    params=params,
                    timeout=15.0
                )

                if response.status_code == 200:
                    return response.json()

                logger.warning(
                    f"ChangeNow range fetch failed: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to get exchange range: {e}")
            return None

    @staticmethod
    async def get_estimated_amount(
        from_currency: str,
        to_currency: str,
        from_amount: float
    ) -> Optional[Dict]:
        """
        Get estimated exchange amount.

        Args:
            from_currency: Source currency code (e.g., "BTC", "USDT-ETH")
            to_currency: Destination currency code
            from_amount: Amount to exchange

        Returns:
            Dict with estimated amount and rate
        """
        try:
            if not settings.CHANGENOW_API_KEY:
                logger.error("ChangeNow API key not configured")
                return None

            from_ticker, from_network = ChangeNowService._parse_asset_code(from_currency)
            to_ticker, to_network = ChangeNowService._parse_asset_code(to_currency)

            params = {
                "fromCurrency": from_ticker,
                "toCurrency": to_ticker,
                "fromAmount": from_amount,
                "flow": "standard"
            }

            # Only add network params if they exist
            if from_network:
                params["fromNetwork"] = from_network
            if to_network:
                params["toNetwork"] = to_network

            async with httpx.AsyncClient() as client:
                headers = {"x-changenow-api-key": settings.CHANGENOW_API_KEY}

                response = await client.get(
                    f"{ChangeNowService.API_URL}/exchange/estimated-amount",
                    params=params,
                    headers=headers,
                    timeout=15.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # Calculate rate manually from amounts for accuracy
                    to_amount = float(data.get("toAmount", 0))
                    estimated_rate = to_amount / from_amount if from_amount > 0 else 0

                    return {
                        "estimated_amount": to_amount,
                        "estimated_rate": estimated_rate,
                        "network_fee": float(data.get("networkFee", 0)),
                        "service_fee": float(data.get("serviceFee", 0)),
                        "valid_until": data.get("validUntil")
                    }

                logger.error(
                    f"ChangeNow estimate failed: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to get estimated amount: {e}")
            return None

    @staticmethod
    async def create_exchange(
        from_currency: str,
        to_currency: str,
        from_amount: float,
        to_address: str,
        refund_address: Optional[str] = None,
        extra_id: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Create exchange transaction on ChangeNow.

        Args:
            from_currency: Source currency code (e.g., "BTC", "USDT-ETH")
            to_currency: Destination currency code
            from_amount: Amount to exchange
            to_address: Destination wallet address
            refund_address: Refund address if exchange fails
            extra_id: Extra ID for currencies that need it (XRP, XLM, etc.)

        Returns:
            Tuple of (success, exchange_data, error_message)
        """
        try:
            if not settings.CHANGENOW_API_KEY:
                return False, None, "ChangeNow API key not configured"

            from_ticker, from_network = ChangeNowService._parse_asset_code(from_currency)
            to_ticker, to_network = ChangeNowService._parse_asset_code(to_currency)

            payload = {
                # Short field names (required by v2 API)
                "from": from_ticker,
                "to": to_ticker,
                "amount": str(from_amount),
                "address": to_address,
                # Detailed field names (also included)
                "fromCurrency": from_ticker,
                "toCurrency": to_ticker,
                "fromAmount": str(from_amount),
                "toAddress": to_address,
                "flow": "standard",
                "type": "direct"
            }

            # Only add network params if they exist
            if from_network:
                payload["fromNetwork"] = from_network
            if to_network:
                payload["toNetwork"] = to_network

            if refund_address:
                payload["refundAddress"] = refund_address

            if extra_id:
                payload["extraId"] = extra_id

            # Log payload for debugging
            logger.info(f"ChangeNOW create_exchange payload: {payload}")

            async with httpx.AsyncClient() as client:
                headers = {
                    "x-changenow-api-key": settings.CHANGENOW_API_KEY,
                    "Content-Type": "application/json"
                }

                response = await client.post(
                    f"{ChangeNowService.API_URL}/exchange",
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )

                # Log response for debugging
                logger.info(f"ChangeNOW create_exchange response: {response.status_code} - {response.text}")

                if response.status_code in [200, 201]:
                    data = response.json()

                    # V2 API uses expectedAmountFrom/To in create response
                    expected_from = data.get("expectedAmountFrom", 0)
                    expected_to = data.get("expectedAmountTo", 0)

                    exchange_data = {
                        "exchange_id": data.get("id"),
                        "deposit_address": data.get("payinAddress"),
                        "deposit_extra_id": data.get("payinExtraId"),
                        "payout_address": data.get("payoutAddress"),
                        "payout_extra_id": data.get("payoutExtraId"),
                        "from_currency": data.get("fromCurrency"),
                        "to_currency": data.get("toCurrency"),
                        "from_amount": float(expected_from) if expected_from else 0,
                        "to_amount": float(expected_to) if expected_to else 0,
                        "status": data.get("status"),
                        "created_at": data.get("createdAt")
                    }

                    logger.info(
                        f"ChangeNow exchange created: {exchange_data['exchange_id']} "
                        f"{from_currency}→{to_currency}"
                    )

                    return True, exchange_data, None

                else:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("message", response.text)
                    logger.error(
                        f"ChangeNow exchange creation failed: {response.status_code} - {error_msg}"
                    )
                    return False, None, error_msg

        except Exception as e:
            logger.error(f"Failed to create ChangeNow exchange: {e}", exc_info=True)
            return False, None, str(e)

    @staticmethod
    async def get_exchange_status(exchange_id: str) -> Optional[Dict]:
        """
        Get exchange transaction status.

        Args:
            exchange_id: ChangeNow exchange ID

        Returns:
            Dict with exchange status or None
        """
        try:
            if not settings.CHANGENOW_API_KEY:
                logger.error("ChangeNow API key not configured")
                return None

            async with httpx.AsyncClient() as client:
                headers = {"x-changenow-api-key": settings.CHANGENOW_API_KEY}

                response = await client.get(
                    f"{ChangeNowService.API_URL}/exchange/by-id",
                    params={"id": exchange_id},
                    headers=headers,
                    timeout=15.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # V2 API field names
                    amount_from = data.get("amountFrom")
                    amount_to = data.get("amountTo")

                    return {
                        "exchange_id": data.get("id"),
                        "status": data.get("status"),
                        "from_currency": data.get("fromCurrency"),
                        "to_currency": data.get("toCurrency"),
                        "from_amount": float(amount_from) if amount_from else 0,
                        "toAmount": float(amount_to) if amount_to else 0,  # Keep as toAmount for compatibility
                        "deposit_received": data.get("depositReceivedAt"),
                        "payoutHash": data.get("payoutHash"),  # Check if exists in V2
                        "payoutLink": data.get("payoutLink"),  # Check if exists in V2
                        "updated_at": data.get("updatedAt"),
                        "created_at": data.get("createdAt")
                    }

                logger.error(
                    f"ChangeNow status check failed: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to get exchange status: {e}")
            return None

    @staticmethod
    def _parse_asset_code(asset_code: str) -> tuple[str, Optional[str]]:
        """
        Parse asset code into ticker and network.

        Examples:
            "BTC" -> ("btc", None)
            "USDT-ETH" -> ("usdt", "eth")
            "USDC-SOL" -> ("usdc", "sol")

        Args:
            asset_code: Asset code (e.g., "BTC", "USDT-ETH")

        Returns:
            Tuple of (ticker, network) - network is None for single-chain assets
        """
        if "-" in asset_code:
            parts = asset_code.split("-", 1)
            ticker = parts[0].lower()
            network = parts[1].lower()
            return ticker, network
        else:
            return asset_code.lower(), None

    @staticmethod
    def parse_changenow_status(status: str) -> str:
        """
        Parse ChangeNow status to Afroo status.

        ChangeNow V2 API statuses:
        - new: Waiting for deposit
        - waiting: Deposit received, processing
        - confirming: Waiting for confirmations
        - exchanging: Exchange in progress
        - sending: Sending to destination
        - finished: Completed
        - failed: Failed
        - refunded: Refunded
        - verifying: Under verification
        - expired: Expired

        Args:
            status: ChangeNow status

        Returns:
            Afroo status (pending, waiting, confirming, exchanging, sending, verifying, completed, failed, expired)
        """
        status_map = {
            "new": "pending",
            "waiting": "waiting",
            "confirming": "confirming",
            "exchanging": "exchanging",
            "sending": "sending",
            "finished": "completed",
            "failed": "failed",
            "refunded": "failed",
            "verifying": "verifying",
            "expired": "expired"
        }

        return status_map.get(status, "unknown")
