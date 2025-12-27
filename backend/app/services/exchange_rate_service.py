"""
Exchange Rate Service - Provides USD to global currency conversions
Uses exchangerate-api.com for live rates
"""

from typing import Dict
import aiohttp
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Service for currency exchange rates"""

    # Cache rates for 1 hour
    _cache = {}
    _cache_time = None
    _cache_duration = timedelta(hours=1)

    # Top 10 global currencies (excluding USD)
    TOP_CURRENCIES = [
        "EUR",  # Euro
        "GBP",  # British Pound
        "JPY",  # Japanese Yen
        "CAD",  # Canadian Dollar
        "AUD",  # Australian Dollar
        "CHF",  # Swiss Franc
        "CNY",  # Chinese Yuan
        "INR",  # Indian Rupee
        "MXN",  # Mexican Peso
        "BRL",  # Brazilian Real
    ]

    CURRENCY_NAMES = {
        "EUR": "Euro",
        "GBP": "British Pound",
        "JPY": "Japanese Yen",
        "CAD": "Canadian Dollar",
        "AUD": "Australian Dollar",
        "CHF": "Swiss Franc",
        "CNY": "Chinese Yuan",
        "INR": "Indian Rupee",
        "MXN": "Mexican Peso",
        "BRL": "Brazilian Real",
    }

    @classmethod
    async def get_rates(cls) -> Dict[str, float]:
        """Get current USD exchange rates (cached)"""

        # Check cache
        if cls._cache_time and datetime.utcnow() - cls._cache_time < cls._cache_duration:
            return cls._cache

        # Fetch new rates
        try:
            async with aiohttp.ClientSession() as session:
                # Using exchangerate-api.com free tier (no API key needed for basic usage)
                url = "https://api.exchangerate-api.com/v4/latest/USD"

                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        rates = data.get("rates", {})

                        # Cache the rates
                        cls._cache = rates
                        cls._cache_time = datetime.utcnow()

                        logger.info(f"Fetched fresh exchange rates: {len(rates)} currencies")
                        return rates
                    else:
                        logger.error(f"Failed to fetch rates: {response.status}")

        except Exception as e:
            logger.error(f"Error fetching exchange rates: {e}")

        # Return cached rates if fetch failed
        if cls._cache:
            logger.warning("Using cached exchange rates due to fetch error")
            return cls._cache

        # Return empty dict if no cache available
        return {}

    @classmethod
    async def get_top_currencies(cls, amount_usd: float) -> Dict:
        """Get USD amount converted to top 10 global currencies"""

        rates = await cls.get_rates()

        if not rates:
            raise ValueError("Unable to fetch exchange rates")

        conversions = {}

        for currency in cls.TOP_CURRENCIES:
            if currency in rates:
                rate = rates[currency]
                converted_amount = amount_usd * rate

                conversions[currency] = {
                    "code": currency,
                    "name": cls.CURRENCY_NAMES.get(currency, currency),
                    "rate": rate,
                    "amount": round(converted_amount, 2),
                    "formatted": f"{converted_amount:,.2f} {currency}"
                }

        return {
            "amount_usd": amount_usd,
            "conversions": conversions,
            "timestamp": datetime.utcnow().isoformat()
        }

    @classmethod
    async def convert(cls, amount_usd: float, to_currency: str) -> Dict:
        """Convert specific USD amount to target currency"""

        rates = await cls.get_rates()

        if not rates:
            raise ValueError("Unable to fetch exchange rates")

        if to_currency not in rates:
            raise ValueError(f"Currency {to_currency} not supported")

        rate = rates[to_currency]
        converted_amount = amount_usd * rate

        return {
            "from_currency": "USD",
            "to_currency": to_currency,
            "amount_usd": amount_usd,
            "rate": rate,
            "converted_amount": round(converted_amount, 2),
            "formatted": f"{converted_amount:,.2f} {to_currency}",
            "timestamp": datetime.utcnow().isoformat()
        }
