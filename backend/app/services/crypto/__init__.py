"""
Crypto currency handlers
Each handler provides chain-specific logic for different cryptocurrencies
"""

from app.services.crypto.base_handler import BaseCryptoHandler
from app.services.crypto.btc_handler import BTCHandler
from app.services.crypto.ltc_handler import LTCHandler
from app.services.crypto.eth_handler import ETHHandler
from app.services.crypto.sol_handler import SOLHandler
from app.services.crypto.xrp_handler import XRPHandler
from app.services.crypto.bnb_handler import BNBHandler
from app.services.crypto.trx_handler import TRXHandler
from app.services.crypto.matic_handler import MATICHandler
from app.services.crypto.avax_handler import AVAXHandler
from app.services.crypto.doge_handler import DOGEHandler
from app.services.crypto.usdc_sol_handler import USDCSOLHandler
from app.services.crypto.usdc_eth_handler import USDCETHHandler
from app.services.crypto.usdt_sol_handler import USDTSOLHandler
from app.services.crypto.usdt_eth_handler import USDTETHHandler

# Handler registry
HANDLERS = {
    "BTC": BTCHandler(),
    "LTC": LTCHandler(),
    "ETH": ETHHandler(),
    "SOL": SOLHandler(),
    "XRP": XRPHandler(),
    "BNB": BNBHandler(),
    "TRX": TRXHandler(),
    "MATIC": MATICHandler(),
    "AVAX": AVAXHandler(),
    "DOGE": DOGEHandler(),
    "USDC-SOL": USDCSOLHandler(),
    "USDC-ETH": USDCETHHandler(),
    "USDT-SOL": USDTSOLHandler(),
    "USDT-ETH": USDTETHHandler(),
}


def get_crypto_handler(currency: str) -> BaseCryptoHandler:
    """Get handler for a specific currency"""
    currency_upper = currency.upper()
    handler = HANDLERS.get(currency_upper)

    if not handler:
        raise ValueError(f"Unsupported currency: {currency}")

    return handler


__all__ = [
    "BaseCryptoHandler",
    "get_crypto_handler",
    "HANDLERS",
]
