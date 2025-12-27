"""Binance Coin (BNB) handler"""

from app.services.crypto.base_handler import BaseCryptoHandler


class BNBHandler(BaseCryptoHandler):
    """BNB cryptocurrency handler"""

    def get_chain(self) -> str:
        return "BSC"  # Binance Smart Chain

    def get_required_confirmations(self) -> int:
        return 15  # BSC requires 15 confirmations

    def format_address(self, address: str) -> str:
        address = address.strip()

        # Validate BNB address format (EVM-compatible)
        if not address.startswith("0x"):
            raise ValueError("Invalid BNB address format")

        if len(address) != 42:
            raise ValueError("Invalid BNB address length")

        return address.lower()

    def get_decimals(self) -> int:
        return 18

    def get_min_withdrawal(self) -> float:
        return 0.001  # 0.001 BNB minimum

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://bscscan.com/tx/{tx_hash}"
