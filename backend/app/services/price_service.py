"""
Price Service - Fetch cryptocurrency prices in USD
Uses CoinGecko API for real-time pricing
"""

import aiohttp
import logging
from typing import Dict, Optional
from decimal import Decimal
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# Map currency codes to CoinGecko IDs
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "LTC": "litecoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "USDT": "tether",
    "USDT-SOL": "tether",
    "USDT-ETH": "tether",
    "USDC": "usd-coin",
    "USDC-SOL": "usd-coin",
    "USDC-ETH": "usd-coin",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "TRX": "tron",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "DOGE": "dogecoin"
}


class PriceService:
    """Service for fetching cryptocurrency prices"""

    # Simple in-memory cache (5 minute expiry)
    _price_cache: Dict[str, tuple[Decimal, datetime]] = {}
    _cache_duration = timedelta(minutes=5)

    @classmethod
    async def get_prices_batch(cls, currencies: list[str]) -> Dict[str, Optional[Decimal]]:
        """
        Batch fetch prices for multiple currencies to avoid rate limiting

        Args:
            currencies: List of currency codes

        Returns:
            Dict mapping currency code to price
        """
        try:
            # Check which currencies need fetching (not in cache or expired)
            to_fetch = []
            results = {}

            for currency in currencies:
                currency = currency.upper()
                if currency in cls._price_cache:
                    price, cached_at = cls._price_cache[currency]
                    if datetime.utcnow() - cached_at < cls._cache_duration:
                        results[currency] = price
                        continue
                to_fetch.append(currency)

            if not to_fetch:
                return results

            # Get unique CoinGecko IDs for currencies that need fetching
            coin_ids = []
            currency_to_coin_id = {}
            for currency in to_fetch:
                coin_id = COINGECKO_IDS.get(currency)
                if coin_id:
                    if coin_id not in coin_ids:
                        coin_ids.append(coin_id)
                    currency_to_coin_id[currency] = coin_id

            if not coin_ids:
                return results

            # Batch fetch from CoinGecko (max 250 IDs per request)
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": ",".join(coin_ids),
                "vs_currencies": "usd"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 429:
                        logger.warning("CoinGecko rate limit hit - using cached values where available")
                        # Return whatever we have cached
                        for currency in to_fetch:
                            results[currency] = None
                        return results

                    if resp.status != 200:
                        logger.error(f"CoinGecko API error: {resp.status}")
                        for currency in to_fetch:
                            results[currency] = None
                        return results

                    data = await resp.json()

                    # Map prices back to currencies
                    for currency in to_fetch:
                        coin_id = currency_to_coin_id.get(currency)
                        if coin_id:
                            price_usd = data.get(coin_id, {}).get("usd")
                            if price_usd is not None:
                                price = Decimal(str(price_usd))
                                cls._price_cache[currency] = (price, datetime.utcnow())
                                results[currency] = price
                            else:
                                results[currency] = None
                        else:
                            results[currency] = None

            return results

        except asyncio.TimeoutError:
            logger.warning("Timeout fetching batch prices")
            return {c: None for c in currencies}
        except Exception as e:
            logger.error(f"Failed to fetch batch prices: {e}")
            return {c: None for c in currencies}

    @classmethod
    async def get_price_usd(cls, currency: str) -> Optional[Decimal]:
        """
        Get current USD price for cryptocurrency

        Args:
            currency: Currency code (BTC, ETH, etc.)

        Returns:
            Price in USD or None if unavailable
        """
        try:
            currency = currency.upper()

            # Check cache first
            if currency in cls._price_cache:
                price, cached_at = cls._price_cache[currency]
                if datetime.utcnow() - cached_at < cls._cache_duration:
                    return price

            # Use batch fetch for single currency
            result = await cls.get_prices_batch([currency])
            return result.get(currency)

        except Exception as e:
            logger.error(f"Failed to fetch price for {currency}: {e}")
            return None

    @classmethod
    async def convert_to_usd(cls, amount: str, currency: str) -> Optional[str]:
        """
        Convert crypto amount to USD value

        Args:
            amount: Amount in crypto
            currency: Currency code

        Returns:
            USD value as string or None
        """
        try:
            price = await cls.get_price_usd(currency)
            if price is None:
                return None

            amount_decimal = Decimal(str(amount))
            usd_value = amount_decimal * price

            # Format to 2 decimal places
            return f"{usd_value:.2f}"

        except Exception as e:
            logger.error(f"Failed to convert {amount} {currency} to USD: {e}")
            return None

    @classmethod
    def clear_cache(cls):
        """Clear price cache (for testing)"""
        cls._price_cache.clear()


# Global instance
price_service = PriceService()
